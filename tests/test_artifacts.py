from __future__ import annotations

import hashlib
import json
from pathlib import Path

import openpyxl
import pytest

from exactsource.artifacts import (
    ArtifactError,
    Prediction,
    TraceRecorder,
    atomic_copy_workbook,
    atomic_write_jsonl,
    prepare_output,
    read_jsonl,
    safe_task_id,
    validate_run,
    validate_workbook,
    write_predictions,
    write_trace,
)


def _workbook(path: Path, value: object = "source") -> Path:
    workbook = openpyxl.Workbook()
    workbook.active["A1"] = value
    workbook.save(path)
    workbook.close()
    return path


def test_prepare_output_preserves_unrelated_files(tmp_path: Path) -> None:
    sentinel = tmp_path / "keep.txt"
    sentinel.write_text("leave me alone", encoding="utf-8")
    existing = tmp_path / "outputs" / "old.xlsx"
    existing.parent.mkdir()
    existing.write_bytes(b"old")

    layout = prepare_output(tmp_path)

    assert layout.outputs_dir.is_dir()
    assert layout.traces_dir.is_dir()
    assert layout.outputs_dir.stat().st_mode & 0o777 == 0o755
    assert layout.traces_dir.stat().st_mode & 0o777 == 0o755
    assert sentinel.read_text(encoding="utf-8") == "leave me alone"
    assert existing.read_bytes() == b"old"


@pytest.mark.parametrize(
    "task_id",
    ["../escape", "a/b", "", ".", " padded ", "control\n", "x" * 161],
)
def test_safe_task_id_rejects_unsafe_filename_components(task_id: str) -> None:
    with pytest.raises(ArtifactError, match="unsafe task id"):
        safe_task_id(task_id)


def test_safe_task_id_accepts_dataset_compatible_unicode_and_spaces() -> None:
    assert safe_task_id("Case 12 – résumé") == "Case 12 – résumé"


def test_atomic_copy_workbook_produces_a_readable_copy(tmp_path: Path) -> None:
    source = _workbook(tmp_path / "source.xlsx", 42)
    destination = tmp_path / "nested" / "copy.xlsx"

    atomic_copy_workbook(source, destination)
    validate_workbook(destination)
    assert destination.stat().st_mode & 0o777 == 0o644

    workbook = openpyxl.load_workbook(destination, data_only=False)
    assert workbook.active["A1"].value == 42
    workbook.close()


def test_validate_workbook_rejects_corrupt_files(tmp_path: Path) -> None:
    corrupt = tmp_path / "corrupt.xlsx"
    corrupt.write_text("not an xlsx", encoding="utf-8")

    with pytest.raises(ArtifactError, match="unreadable workbook"):
        validate_workbook(corrupt)


def test_trace_recorder_truncates_large_text_and_marks_it() -> None:
    recorder = TraceRecorder("51-12", text_limit=5)
    recorder.record(model="fixed", prompt="abcdefgh", response="ok")

    record = recorder.records[0]
    assert record["prompt"] == "abcgh"
    assert record["prompt_truncated"] is True
    assert record["prompt_truncation"] == "middle"
    assert record["prompt_original_chars"] == 8
    assert record["prompt_sha256"] == hashlib.sha256(b"abcdefgh").hexdigest()
    assert record["prompt_encoding"] == "text"
    assert record["step"] == 1
    assert record["task_id"] == "51-12"


def test_trace_recorder_retains_complete_executed_tool_evidence() -> None:
    recorder = TraceRecorder("51-12", text_limit=20)
    value = {"cells": [{"address": "A1", "value": "x" * 100}]}

    recorder.record(model="fixed", tool_output=value)

    record = recorder.records[0]
    assert record["tool_output"] == value
    assert "tool_output_truncated" not in record


def test_trace_recorder_retains_complete_model_response() -> None:
    recorder = TraceRecorder("51-12", text_limit=20)
    response = "x" * 100

    recorder.record(model="fixed", prompt="p" * 100, response=response)

    record = recorder.records[0]
    assert record["response"] == response
    assert record["prompt"] == "p" * 20
    assert record["prompt_truncated"] is True


def test_trace_prompt_truncation_preserves_distinct_head_and_tail() -> None:
    recorder = TraceRecorder("51-12", text_limit=100)
    prompt = "HEAD-" + "middle" * 100 + "-REPAIR-ERROR-AND-SCHEMA-TAIL"

    recorder.record(model="fixed", prompt=prompt, response="ok")

    retained = recorder.records[0]["prompt"]
    assert len(retained) == 100
    assert retained.startswith("HEAD-")
    assert retained.endswith("-REPAIR-ERROR-AND-SCHEMA-TAIL")
    assert "[MIDDLE TRUNCATED]" in retained


def test_trace_recorder_attaches_tool_result_to_existing_call() -> None:
    recorder = TraceRecorder("51-12")
    recorder.record(model="fixed", prompt="request", response="reply", error=None)

    recorder.update_last(tool="apply_operations", tool_output={"cell_writes": 1})

    assert len(recorder.records) == 1
    assert recorder.records[0]["step"] == 1
    assert recorder.records[0]["tool"] == "apply_operations"
    assert recorder.records[0]["tool_output"] == {"cell_writes": 1}


def test_validate_run_checks_order_workbooks_and_traces(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    predictions: list[Prediction] = []
    for task_id in ("2", "1"):
        _workbook(layout.output_path(task_id), task_id)
        recorder = TraceRecorder(task_id)
        recorder.record(model="fake", prompt="request", response="reply", error=None)
        write_trace(layout, task_id, recorder)
        predictions.append(Prediction(task_id, layout.relative_output(task_id), "ok"))
    write_predictions(layout, predictions)

    checked = validate_run(layout, ("2", "1"))

    assert [item.id for item in checked] == ["2", "1"]
    assert [item.id for item in checked] == [
        row["id"] for row in read_jsonl(layout.predictions_path)
    ]


def test_validate_run_rejects_prediction_order_mismatch(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    for task_id in ("a", "b"):
        _workbook(layout.output_path(task_id))
        recorder = TraceRecorder(task_id)
        recorder.record(model="fake")
        write_trace(layout, task_id, recorder)
    write_predictions(
        layout,
        [
            Prediction("b", layout.relative_output("b"), "ok"),
            Prediction("a", layout.relative_output("a"), "ok"),
        ],
    )

    with pytest.raises(ArtifactError, match="prediction 1 id"):
        validate_run(layout, ("a", "b"))


def test_atomic_jsonl_replaces_prior_file_with_valid_lines(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text("stale", encoding="utf-8")

    atomic_write_jsonl(path, ({"id": 1}, {"id": 2, "text": "£"}))

    assert read_jsonl(path) == [{"id": 1}, {"id": 2, "text": "£"}]
    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == [
        {"id": 1},
        {"id": 2, "text": "£"},
    ]
    assert path.stat().st_mode & 0o777 == 0o644
