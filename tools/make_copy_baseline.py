#!/usr/bin/env python3
"""Create a reproducible untouched-workbook baseline without model calls.

This is an evaluation control, not a submission solver. It deliberately uses the
same confined dataset loader and artefact writer as production, and never searches
for or opens a golden workbook.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from exactsource.artifacts import (
    Prediction,
    TraceRecorder,
    atomic_copy_workbook,
    atomic_write_text,
    prepare_output,
    validate_run,
    write_predictions,
    write_trace,
)
from exactsource.dataset import load_tasks

BASELINE_MODEL = "none:untouched-workbook-control"


def create_copy_baseline(data_dir: Path, out_dir: Path) -> dict[str, object]:
    started = time.monotonic()
    tasks = load_tasks(data_dir)
    layout = prepare_output(out_dir)
    predictions: list[Prediction] = []

    for task in tasks:
        atomic_copy_workbook(task.init_xlsx, layout.output_path(task.id))
        recorder = TraceRecorder(task.id)
        recorder.record(
            event="control_baseline",
            model=BASELINE_MODEL,
            status="ok",
            model_calls=0,
            input=str(task.init_xlsx.relative_to(data_dir.resolve())),
            output=layout.relative_output(task.id),
            note="Initial workbook copied without modification; no model was called.",
        )
        write_trace(layout, task.id, recorder)
        predictions.append(
            Prediction(
                id=task.id,
                output=layout.relative_output(task.id),
                status="control_copy",
            )
        )

    write_predictions(layout, predictions)
    verified = validate_run(layout, (task.id for task in tasks))
    elapsed_ms = max(0, round((time.monotonic() - started) * 1_000))
    summary: dict[str, object] = {
        "baseline": "untouched_workbook",
        "model_calls": 0,
        "tasks": len(verified),
        "elapsed_ms": elapsed_ms,
    }
    atomic_write_text(layout.log_path, json.dumps(summary, sort_keys=True) + "\n")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = create_copy_baseline(args.dataset_dir.resolve(), args.out_dir.resolve())
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
