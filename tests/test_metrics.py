from __future__ import annotations

import json
from pathlib import Path

import pytest

from exactsource.artifacts import (
    ArtifactError,
    Prediction,
    TraceRecorder,
    prepare_output,
    write_trace,
)
from exactsource.metrics import build_run_metrics, write_run_metrics


def _prediction(task_id: str, status: str = "ok") -> Prediction:
    return Prediction(task_id, f"outputs/{task_id}.xlsx", status)


def test_metrics_aggregate_calls_attempts_statuses_and_known_usage(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)

    first = TraceRecorder("first")
    first.record(
        model="fixed",
        semantic_attempt=1,
        attempt=1,
        status="retry",
        input_tokens=100,
        output_tokens=None,
        cache_creation_input_tokens=10,
        cache_read_input_tokens=20,
        latency_ms=50,
    )
    first.record(
        model="fixed",
        semantic_attempt=1,
        attempt=2,
        status="success",
        input_tokens=120,
        output_tokens=30,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=0,
        latency_ms=80,
    )
    write_trace(layout, "first", first)

    second = TraceRecorder("second")
    second.record(
        model="fixed",
        semantic_attempt=1,
        attempt=1,
        status="error",
        output_tokens=None,
        cache_read_input_tokens=None,
    )
    write_trace(layout, "second", second)

    empty_failure = TraceRecorder("pre-call-failure")
    write_trace(layout, "pre-call-failure", empty_failure)
    predictions = [
        _prediction("first"),
        _prediction("second", "error: provider"),
        _prediction("pre-call-failure", "error: context"),
    ]

    metrics = build_run_metrics(layout, predictions, run_wall_time_ms=1_234)

    assert metrics["run_wall_time_ms"] == 1_234
    assert metrics["tasks"] == {"total": 3, "succeeded": 1, "failed": 2}
    assert metrics["model"] == {
        "calls": 2,
        "attempts": 3,
        "attempt_status_counts": {"error": 1, "retry": 1, "success": 1},
    }
    assert metrics["usage"]["input_tokens"] == {
        "known_sum": 220,
        "known_attempts": 2,
        "unknown_attempts": 1,
    }
    # Cache usage remains a separate observation; it is not added to input_tokens.
    assert metrics["usage"]["cache_creation_input_tokens"] == {
        "known_sum": 10,
        "known_attempts": 2,
        "unknown_attempts": 1,
    }
    assert metrics["usage"]["cache_read_input_tokens"] == {
        "known_sum": 20,
        "known_attempts": 2,
        "unknown_attempts": 1,
    }
    assert metrics["usage"]["output_tokens"] == {
        "known_sum": 30,
        "known_attempts": 1,
        "unknown_attempts": 2,
    }
    assert metrics["usage"]["provider_latency_ms"] == {
        "known_sum": 130,
        "known_attempts": 2,
        "unknown_attempts": 1,
    }


def test_metrics_count_unlabelled_trace_records_as_distinct_calls(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("legacy")
    trace.record(model="fixed", status="success")
    trace.record(model="fixed", status="success")
    write_trace(layout, "legacy", trace)

    metrics = build_run_metrics(layout, [_prediction("legacy")], run_wall_time_ms=0)

    assert metrics["model"]["calls"] == 2
    assert metrics["model"]["attempts"] == 2
    assert metrics["usage"]["input_tokens"]["unknown_attempts"] == 2


def test_metrics_reject_invalid_non_null_usage(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("bad")
    trace.record(model="fixed", input_tokens=True)
    write_trace(layout, "bad", trace)

    with pytest.raises(ArtifactError, match="invalid input_tokens"):
        build_run_metrics(layout, [_prediction("bad")], run_wall_time_ms=1)


def test_write_run_metrics_is_atomic_json_with_public_file_mode(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("one")
    trace.record(model="fixed", semantic_attempt=1, status="success", latency_ms=9)
    write_trace(layout, "one", trace)

    expected = write_run_metrics(layout, [_prediction("one")], run_wall_time_ms=12)

    assert json.loads(layout.run_metrics_path.read_text(encoding="utf-8")) == expected
    assert layout.run_metrics_path.read_bytes().endswith(b"\n")
    assert layout.run_metrics_path.stat().st_mode & 0o777 == 0o644
    assert not list(tmp_path.glob(".run_metrics.*"))


def test_metrics_v2_separates_provider_plan_and_task_telemetry(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)

    first = TraceRecorder("first")
    first.record(
        model="fixed",
        semantic_attempt=1,
        attempt=1,
        status="retry",
        provider_status="retry",
        latency_ms=10,
        retry_delay_seconds=0.025,
        message_chars=100,
        request_chars=120,
        response_chars=4,
        answer_chars=None,
        thinking_chars=None,
        context_build_latency_ms=1,
        message_build_latency_ms=2,
    )
    first.record(
        model="fixed",
        semantic_attempt=1,
        attempt=2,
        status="plan_rejected",
        provider_status="success",
        plan_status="parse_rejected",
        logical_call_latency_ms=40,
        latency_ms=20,
        message_chars=100,
        request_chars=120,
        response_chars=40,
        answer_chars=30,
        thinking_chars=10,
        plan_parse_latency_ms=3,
    )
    first.record(
        model="fixed",
        semantic_attempt=2,
        attempt=1,
        status="success",
        provider_status="success",
        plan_status="accepted",
        logical_call_latency_ms=30,
        latency_ms=30,
        message_chars=150,
        request_chars=170,
        response_chars=35,
        answer_chars=35,
        thinking_chars=0,
        plan_parse_latency_ms=2,
        plan_apply_latency_ms=5,
        task_latency_ms=100,
    )
    write_trace(layout, "first", first)

    second = TraceRecorder("second")
    second.record(
        model="fixed",
        semantic_attempt=1,
        attempt=1,
        status="error",
        provider_status="error",
        plan_status="not_reached",
        logical_call_latency_ms=12,
        latency_ms=12,
        message_chars=90,
        request_chars=110,
        response_chars=None,
        answer_chars=None,
        thinking_chars=0,
        context_build_latency_ms=2,
        message_build_latency_ms=1,
        task_latency_ms=30,
    )
    write_trace(layout, "second", second)

    pre_call_failure = TraceRecorder("pre-call-failure")
    write_trace(layout, "pre-call-failure", pre_call_failure)
    predictions = [
        _prediction("first"),
        _prediction("second", "error: provider"),
        _prediction("pre-call-failure", "error: context"),
    ]

    metrics = build_run_metrics(
        layout,
        predictions,
        run_wall_time_ms=150,
        task_latencies_ms={"first": 100, "second": 30, "pre-call-failure": 5},
    )

    assert metrics["schema_version"] == 2
    assert metrics["model"] == {
        "calls": 3,
        "attempts": 4,
        "attempt_status_counts": {
            "error": 1,
            "plan_rejected": 1,
            "retry": 1,
            "success": 1,
        },
    }
    assert metrics["reliability"] == {
        "provider_status_counts": {"error": 1, "retry": 1, "success": 2},
        "plan_status_counts": {
            "accepted": 1,
            "not_reached": 1,
            "parse_rejected": 1,
        },
        "semantic_repairs": 1,
        "semantic_attempt_unknown_calls": 0,
        "transport_retries": 1,
    }
    assert metrics["latency_ms"]["task"]["all"] == {
        "known_count": 3,
        "unknown_count": 0,
        "sum": 135,
        "min": 5,
        "median": 30,
        "p95": 100,
        "max": 100,
    }
    assert metrics["latency_ms"]["task"]["by_task"] == {
        "first": 100,
        "pre-call-failure": 5,
        "second": 30,
    }
    assert metrics["latency_ms"]["task"]["by_outcome"]["failed"]["median"] == 17.5
    assert metrics["latency_ms"]["logical_call"]["all"]["median"] == 30
    assert metrics["latency_ms"]["provider_attempt"]["all"]["median"] == 16.0
    assert metrics["latency_ms"]["transport_retry_delay"]["sum"] == 25
    assert metrics["latency_ms"]["stages"]["context_build_latency_ms"] == {
        "known_count": 2,
        "unknown_count": 1,
        "sum": 3,
        "min": 1,
        "median": 1.5,
        "p95": 2,
        "max": 2,
    }
    assert metrics["latency_ms"]["stages"]["plan_parse_latency_ms"]["known_count"] == 2
    assert metrics["latency_ms"]["stages"]["plan_apply_latency_ms"]["sum"] == 5
    assert metrics["characters"]["scope"] == "provider_attempt"
    assert metrics["characters"]["request_chars"]["sum"] == 520
    assert metrics["characters"]["response_chars"]["unknown_count"] == 1
    assert metrics["characters"]["answer_chars"]["known_count"] == 2
    assert metrics["characters"]["thinking_chars"]["sum"] == 10


def test_metrics_reject_task_latency_id_mismatch(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("one")
    trace.record(model="fixed", status="success")
    write_trace(layout, "one", trace)

    with pytest.raises(ArtifactError, match="task latency ids"):
        build_run_metrics(
            layout,
            [_prediction("one")],
            run_wall_time_ms=1,
            task_latencies_ms={"other": 1},
        )


def test_metrics_reject_task_latency_that_disagrees_with_trace(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("one")
    trace.record(model="fixed", status="success", task_latency_ms=7)
    write_trace(layout, "one", trace)

    with pytest.raises(ArtifactError, match="does not match its terminal trace"):
        build_run_metrics(
            layout,
            [_prediction("one")],
            run_wall_time_ms=10,
            task_latencies_ms={"one": 8},
        )


def test_metrics_reject_task_latency_above_run_wall_time(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("one")
    write_trace(layout, "one", trace)

    with pytest.raises(ArtifactError, match="latency exceeds the run wall time"):
        build_run_metrics(
            layout,
            [_prediction("one", "error: context")],
            run_wall_time_ms=0,
            task_latencies_ms={"one": 1},
        )


def test_metrics_do_not_recover_task_latency_from_a_nonterminal_record(tmp_path: Path) -> None:
    layout = prepare_output(tmp_path)
    trace = TraceRecorder("one")
    trace.record(model="fixed", status="retry", task_latency_ms=7)
    trace.record(model="fixed", status="success")
    write_trace(layout, "one", trace)

    metrics = build_run_metrics(layout, [_prediction("one")], run_wall_time_ms=10)

    assert metrics["latency_ms"]["task"]["by_task"] == {"one": None}
    assert metrics["latency_ms"]["task"]["all"]["unknown_count"] == 1
