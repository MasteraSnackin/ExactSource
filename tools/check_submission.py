#!/usr/bin/env python3
"""Validate ExactSource artefacts without reading benchmark golden workbooks."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import openpyxl

from exactsource.artifacts import ArtifactError, OutputLayout, Prediction
from exactsource.config import MODEL_NAME
from exactsource.metrics import build_run_metrics


class CheckFailure(RuntimeError):
    pass


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CheckFailure(f"cannot read JSON from {path}: {exc}") from exc


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CheckFailure(f"cannot read {path}: {exc}") from exc
    if raw and not raw.endswith(b"\n"):
        raise CheckFailure(f"{path} has no final newline")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CheckFailure(f"{path} is not UTF-8: {exc}") from exc

    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CheckFailure(f"{path}:{line_number} is invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise CheckFailure(f"{path}:{line_number} is not a JSON object")
        rows.append(row)
    return rows


def confined_relative_path(root: Path, value: object, *, field: str) -> Path:
    if not isinstance(value, str) or not value:
        raise CheckFailure(f"{field} must be a non-empty string")
    candidate = Path(value.replace("\\", "/"))
    if candidate.is_absolute():
        raise CheckFailure(f"{field} must be relative: {value!r}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CheckFailure(f"{field} escapes the submission directory: {value!r}") from exc
    return resolved


def task_ids(dataset_dir: Path) -> list[str]:
    dataset = read_json(dataset_dir / "dataset.json")
    if not isinstance(dataset, list):
        raise CheckFailure("dataset.json must contain a list")
    ids: list[str] = []
    for index, task in enumerate(dataset):
        if not isinstance(task, dict) or "id" not in task:
            raise CheckFailure(f"dataset task {index} has no id")
        ids.append(str(task["id"]))
    duplicates = sorted(key for key, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise CheckFailure(f"dataset contains duplicate ids: {duplicates[:5]}")
    return ids


def validate_workbook(path: Path) -> None:
    if not path.is_file():
        raise CheckFailure(f"missing output workbook: {path}")
    try:
        workbook = openpyxl.load_workbook(path, read_only=True, data_only=False)
        if not workbook.sheetnames:
            raise CheckFailure(f"workbook has no worksheets: {path}")
        workbook.close()
    except CheckFailure:
        raise
    except Exception as exc:
        raise CheckFailure(f"cannot open output workbook {path}: {exc}") from exc


def validate_trace(path: Path, task_id: str, status: str) -> int:
    records = read_jsonl(path)
    if not records:
        if status.startswith("error"):
            return 0
        raise CheckFailure(f"successful task has an empty trace: {task_id}")
    previous_step = 0
    for index, record in enumerate(records, start=1):
        if record.get("task_id") != task_id:
            raise CheckFailure(f"trace {path}:{index} carries the wrong task_id")
        step = record.get("step")
        if isinstance(step, bool) or not isinstance(step, int) or step <= previous_step:
            raise CheckFailure(f"trace steps are not strictly increasing in {path}")
        previous_step = step
        model = record.get("model")
        if model != MODEL_NAME:
            raise CheckFailure(
                f"trace {path}:{index} uses model {model!r}; expected {MODEL_NAME!r}"
            )
        if index < len(records) and (
            "task_status" in record or "task_latency_ms" in record or "runtime_error" in record
        ):
            raise CheckFailure(f"trace {path}:{index} carries task-terminal fields too early")

    terminal = records[-1]
    expected_task_status = "error" if status.startswith("error:") else "ok"
    if terminal.get("task_status") != expected_task_status:
        raise CheckFailure(f"trace {path} terminal task_status does not match its prediction")
    task_latency = terminal.get("task_latency_ms")
    if isinstance(task_latency, bool) or not isinstance(task_latency, int) or task_latency < 0:
        raise CheckFailure(f"trace {path} terminal task_latency_ms is invalid")
    if expected_task_status == "error":
        runtime_error = terminal.get("runtime_error")
        if not isinstance(runtime_error, str) or not runtime_error:
            raise CheckFailure(f"trace {path} failed without a terminal runtime_error")
    return len(records)


def validate_run_metrics(
    submission_dir: Path,
    predictions: list[dict[str, Any]],
) -> None:
    """Recompute trace-derived metrics and validate coordinator timing evidence.

    Wall time and latency for tasks with no model trace originate from the
    coordinator's monotonic clock and are structurally validated rather than
    independently reconstructable from trace records.
    """

    metrics_path = submission_dir / "run_metrics.json"
    metrics = read_json(metrics_path)
    if not isinstance(metrics, dict):
        raise CheckFailure("run_metrics.json must contain a JSON object")
    wall_time = metrics.get("run_wall_time_ms")
    try:
        task_latencies = metrics["latency_ms"]["task"]["by_task"]
    except (KeyError, TypeError):
        raise CheckFailure("run_metrics.json has no per-task latency evidence") from None
    if not isinstance(task_latencies, dict):
        raise CheckFailure("run_metrics.json per-task latency evidence must be an object")
    typed_predictions: list[Prediction] = []
    try:
        for prediction in predictions:
            typed_predictions.append(
                Prediction(
                    id=str(prediction.get("id", "")),
                    output=str(prediction.get("output", "")),
                    status=str(prediction.get("status", "")),
                )
            )
        expected = build_run_metrics(
            OutputLayout(submission_dir),
            typed_predictions,
            run_wall_time_ms=wall_time,
            task_latencies_ms=task_latencies,
        )
    except ArtifactError as exc:
        raise CheckFailure(f"invalid run_metrics.json evidence: {exc}") from exc
    if metrics != expected:
        raise CheckFailure(
            "run_metrics.json does not match predictions, traces and declared timing evidence"
        )


def validate(dataset_dir: Path, submission_dir: Path) -> dict[str, int]:
    expected_ids = task_ids(dataset_dir.resolve())
    predictions_path = submission_dir / "predictions.jsonl"
    predictions = read_jsonl(predictions_path)

    if len(predictions) != len(expected_ids):
        raise CheckFailure(f"expected {len(expected_ids)} predictions, found {len(predictions)}")

    layout = OutputLayout(submission_dir)
    for index, (prediction, expected_id) in enumerate(
        zip(predictions, expected_ids, strict=True),
        start=1,
    ):
        if set(prediction) != {"id", "output", "status"}:
            raise CheckFailure(f"prediction {index} has unexpected fields")
        if prediction["id"] != expected_id:
            raise CheckFailure(
                f"prediction {index} id is {prediction['id']!r}; expected {expected_id!r}"
            )
        if prediction["output"] != layout.relative_output(expected_id):
            raise CheckFailure(f"prediction {expected_id} has an unexpected output path")
        status = prediction["status"]
        if not isinstance(status, str) or not (status == "ok" or status.startswith("error:")):
            raise CheckFailure(f"prediction {expected_id} has an invalid status")

    trace_records = 0
    failures = 0
    for task_id, prediction in zip(expected_ids, predictions, strict=True):
        output = confined_relative_path(
            submission_dir, prediction.get("output"), field=f"prediction {task_id} output"
        )
        validate_workbook(output)

        trace_path = confined_relative_path(
            submission_dir,
            f"traces/{task_id}.jsonl",
            field=f"trace path for {task_id}",
        )
        status = prediction["status"]
        trace_records += validate_trace(trace_path, task_id, status)
        if status.startswith("error"):
            failures += 1

    log_path = submission_dir / "run.log"
    if not log_path.is_file() or not log_path.read_text(encoding="utf-8").strip():
        raise CheckFailure("run.log is missing or empty")
    validate_run_metrics(submission_dir, predictions)

    return {
        "tasks": len(expected_ids),
        "predictions": len(predictions),
        "workbooks": len(predictions),
        "trace_records": trace_records,
        "task_failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--submission-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        summary = validate(args.dataset_dir, args.submission_dir.resolve())
    except CheckFailure as exc:
        print(f"submission check failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
