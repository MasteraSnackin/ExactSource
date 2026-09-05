import importlib.util
import json
from pathlib import Path

import openpyxl
import pytest

from exactsource.artifacts import OutputLayout, Prediction
from exactsource.metrics import build_run_metrics


def load_checker():
    script = Path(__file__).parents[1] / "tools" / "check_submission.py"
    spec = importlib.util.spec_from_file_location("check_submission", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


checker = load_checker()


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")


def create_valid_fixture(tmp_path: Path) -> tuple[Path, Path]:
    dataset_dir = tmp_path / "data"
    submission_dir = tmp_path / "out"
    dataset_dir.mkdir()
    (dataset_dir / "dataset.json").write_text(
        json.dumps([{"id": "one"}, {"id": "two"}]), encoding="utf-8"
    )

    predictions = []
    for task_id in ("one", "two"):
        workbook_path = submission_dir / "outputs" / f"{task_id}.xlsx"
        workbook_path.parent.mkdir(parents=True, exist_ok=True)
        workbook = openpyxl.Workbook()
        workbook.active["A1"] = task_id
        workbook.save(workbook_path)
        write_jsonl(
            submission_dir / "traces" / f"{task_id}.jsonl",
            [
                {
                    "task_id": task_id,
                    "step": 1,
                    "model": "tinker:Qwen/Qwen3.8-27B",
                    "task_status": "ok",
                    "task_latency_ms": 1,
                }
            ],
        )
        predictions.append(
            {
                "id": task_id,
                "output": f"outputs/{task_id}.xlsx",
                "status": "ok",
            }
        )
    write_jsonl(submission_dir / "predictions.jsonl", predictions)
    (submission_dir / "run.log").write_text("completed 2 tasks\n", encoding="utf-8")
    metrics = build_run_metrics(
        OutputLayout(submission_dir),
        [Prediction(**prediction) for prediction in predictions],
        run_wall_time_ms=123,
    )
    (submission_dir / "run_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return dataset_dir, submission_dir


def test_valid_submission_is_complete(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)

    summary = checker.validate(dataset_dir, submission_dir)

    assert summary == {
        "tasks": 2,
        "predictions": 2,
        "workbooks": 2,
        "trace_records": 2,
        "task_failures": 0,
    }


def test_escaping_output_path_is_rejected(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "predictions.jsonl",
        [
            {"id": "one", "output": "../outside.xlsx", "status": "ok"},
            {"id": "two", "output": "outputs/two.xlsx", "status": "ok"},
        ],
    )

    with pytest.raises(checker.CheckFailure, match="unexpected output path"):
        checker.validate(dataset_dir, submission_dir)


def test_missing_prediction_is_rejected(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "predictions.jsonl",
        [{"id": "one", "output": "outputs/one.xlsx", "status": "ok"}],
    )

    with pytest.raises(checker.CheckFailure, match="expected 2 predictions"):
        checker.validate(dataset_dir, submission_dir)


def test_predictions_must_preserve_dataset_order_and_exact_fields(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    predictions_path = submission_dir / "predictions.jsonl"
    predictions = [json.loads(line) for line in predictions_path.read_text().splitlines()]
    write_jsonl(predictions_path, list(reversed(predictions)))

    with pytest.raises(checker.CheckFailure, match="prediction 1 id"):
        checker.validate(dataset_dir, submission_dir)

    predictions[0]["unexpected"] = True
    write_jsonl(predictions_path, predictions)

    with pytest.raises(checker.CheckFailure, match="unexpected fields"):
        checker.validate(dataset_dir, submission_dir)


def test_prediction_output_must_use_the_canonical_task_path(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    source = submission_dir / "outputs" / "one.xlsx"
    renamed = submission_dir / "outputs" / "renamed.xlsx"
    source.rename(renamed)
    predictions_path = submission_dir / "predictions.jsonl"
    predictions = [json.loads(line) for line in predictions_path.read_text().splitlines()]
    predictions[0]["output"] = "outputs/renamed.xlsx"
    write_jsonl(predictions_path, predictions)

    with pytest.raises(checker.CheckFailure, match="unexpected output path"):
        checker.validate(dataset_dir, submission_dir)


def test_trace_steps_must_increase(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "traces" / "one.jsonl",
        [
            {
                "task_id": "one",
                "step": 1,
                "model": "tinker:Qwen/Qwen3.8-27B",
            },
            {
                "task_id": "one",
                "step": 1,
                "model": "tinker:Qwen/Qwen3.8-27B",
            },
        ],
    )

    with pytest.raises(checker.CheckFailure, match="strictly increasing"):
        checker.validate(dataset_dir, submission_dir)


def test_trace_step_must_not_be_boolean(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "traces" / "one.jsonl",
        [
            {
                "task_id": "one",
                "step": True,
                "model": "tinker:Qwen/Qwen3.8-27B",
                "task_status": "ok",
                "task_latency_ms": 1,
            }
        ],
    )

    with pytest.raises(checker.CheckFailure, match="strictly increasing"):
        checker.validate(dataset_dir, submission_dir)


def test_trace_from_another_model_is_rejected(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "traces" / "one.jsonl",
        [{"task_id": "one", "step": 1, "model": "another/model"}],
    )

    with pytest.raises(checker.CheckFailure, match="expected.*Qwen/Qwen3.8-27B"):
        checker.validate(dataset_dir, submission_dir)


def test_missing_run_metrics_is_rejected(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    (submission_dir / "run_metrics.json").unlink()

    with pytest.raises(checker.CheckFailure, match="cannot read JSON"):
        checker.validate(dataset_dir, submission_dir)


def test_run_metrics_must_match_final_traces(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    metrics_path = submission_dir / "run_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["model"]["attempts"] = 999
    metrics_path.write_text(json.dumps(metrics), encoding="utf-8")

    with pytest.raises(checker.CheckFailure, match="does not match"):
        checker.validate(dataset_dir, submission_dir)


def test_run_metrics_preserve_latency_for_an_empty_pre_call_trace(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    (submission_dir / "traces" / "two.jsonl").write_text("", encoding="utf-8")
    predictions_path = submission_dir / "predictions.jsonl"
    predictions = [json.loads(line) for line in predictions_path.read_text().splitlines()]
    predictions[1]["status"] = "error: context"
    write_jsonl(predictions_path, predictions)
    typed = [Prediction(**prediction) for prediction in predictions]
    metrics = build_run_metrics(
        OutputLayout(submission_dir),
        typed,
        run_wall_time_ms=123,
        task_latencies_ms={"one": 1, "two": 9},
    )
    (submission_dir / "run_metrics.json").write_text(
        json.dumps(metrics, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    summary = checker.validate(dataset_dir, submission_dir)

    assert summary["task_failures"] == 1
    assert metrics["latency_ms"]["task"]["by_task"] == {"one": 1, "two": 9}


def test_nonempty_trace_requires_terminal_task_evidence(tmp_path: Path) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    write_jsonl(
        submission_dir / "traces" / "one.jsonl",
        [
            {
                "task_id": "one",
                "step": 1,
                "model": "tinker:Qwen/Qwen3.8-27B",
            }
        ],
    )

    with pytest.raises(checker.CheckFailure, match="terminal task_status"):
        checker.validate(dataset_dir, submission_dir)


def test_positive_coordinator_wall_time_is_structurally_not_independently_verified(
    tmp_path: Path,
) -> None:
    dataset_dir, submission_dir = create_valid_fixture(tmp_path)
    metrics_path = submission_dir / "run_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["run_wall_time_ms"] = 987_654_321
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    summary = checker.validate(dataset_dir, submission_dir)

    assert summary["tasks"] == 2
