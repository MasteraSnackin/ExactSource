from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from exactsource_sft import train


@pytest.mark.parametrize(
    ("execute", "environ", "expected"),
    [
        (False, {}, False),
        (
            False,
            {
                train.PAID_ACK_ENV: "YES",
                train.API_KEY_ENV: "secret",
                train.PROJECT_ID_ENV: "project",
            },
            False,
        ),
        (
            True,
            {
                train.PAID_ACK_ENV: "YES",
                train.API_KEY_ENV: "secret",
                train.PROJECT_ID_ENV: "project",
            },
            True,
        ),
    ],
)
def test_paid_training_gate_accepts_only_complete_explicit_authority(
    execute: bool,
    environ: dict[str, str],
    expected: bool,
) -> None:
    assert train.paid_training_gate(execute=execute, environ=environ) is expected


@pytest.mark.parametrize(
    ("environ", "message"),
    [
        ({}, train.PAID_ACK_ENV),
        ({train.PAID_ACK_ENV: "yes"}, train.PAID_ACK_ENV),
        ({train.PAID_ACK_ENV: "YES"}, train.API_KEY_ENV),
        (
            {train.PAID_ACK_ENV: "YES", train.API_KEY_ENV: "   "},
            train.API_KEY_ENV,
        ),
        (
            {train.PAID_ACK_ENV: "YES", train.API_KEY_ENV: "secret"},
            train.PROJECT_ID_ENV,
        ),
        (
            {
                train.PAID_ACK_ENV: "YES",
                train.API_KEY_ENV: "secret",
                train.PROJECT_ID_ENV: " ",
            },
            train.PROJECT_ID_ENV,
        ),
    ],
)
def test_paid_training_gate_rejects_each_missing_or_invalid_requirement(
    environ: dict[str, str],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        train.paid_training_gate(execute=True, environ=environ)


def test_cli_dry_run_verifies_data_without_calling_training(
    prepared_output: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    renderer_factory: Callable[[int], object],
) -> None:
    called = False

    def forbidden_training(**_kwargs: object) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError("paid training must not run during a dry-run")

    monkeypatch.setattr(train, "_run_training", forbidden_training)
    monkeypatch.setattr(train, "_load_renderer", lambda: renderer_factory(101))

    result = train.run(["train", "--data-dir", str(prepared_output)], environ={})

    assert result == 0
    assert called is False
    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "offline-preflight"
    assert output["model"] == "Qwen/Qwen3.8-27B"
    assert output["train_examples_available"] == 12
    assert output["train_examples_selected"] == 8
    assert output["tune_examples"] == 4
    assert output["would_run_steps"] == 4
    assert output["projected_train_tokens"] == 800
    assert output["projected_tune_tokens_per_pass"] == 400
    assert output["projected_total_tokens"] == 1_600
    assert output["maximum_pilot_tokens"] == train.MAX_PILOT_TOTAL_RENDERED_TOKENS
    assert len(output["data_fingerprint"]) == 64


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--batch-size", "0"], "positive batch size"),
        (["--max-steps", "7"], "max_steps must be between"),
        (["--learning-rate", "nan"], "learning_rate must be finite"),
        (["--lora-rank", "7"], "lora_rank must be one of"),
    ],
)
def test_invalid_dry_run_hyperparameters_fail_before_training(
    prepared_output: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
    message: str,
) -> None:
    called = False

    def forbidden_training(**_kwargs: object) -> dict[str, object]:
        nonlocal called
        called = True
        raise AssertionError("invalid preflight must not start paid training")

    monkeypatch.setattr(train, "_run_training", forbidden_training)

    result = train.run(
        ["train", "--data-dir", str(prepared_output), *arguments],
        environ={},
    )

    assert result == 1
    assert called is False
    assert message in capsys.readouterr().err


def test_safe_run_directory_creates_a_named_child(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    requested = root / "pilot-v1"

    created = train._safe_new_run_dir(
        requested,
        runs_root=root,
        repository_root=tmp_path,
    )

    assert created == requested.resolve()
    assert created.is_dir()


def test_safe_run_directory_rejects_the_runs_root(tmp_path: Path) -> None:
    root = tmp_path / "runs"

    with pytest.raises(ValueError, match="named child"):
        train._safe_new_run_dir(root, runs_root=root, repository_root=tmp_path)


def test_safe_run_directory_rejects_path_traversal(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    outside = root / ".." / "outside"

    with pytest.raises(ValueError, match="(?:outside|beneath)"):
        train._safe_new_run_dir(outside, runs_root=root, repository_root=tmp_path)


def test_safe_run_directory_rejects_a_nonempty_directory(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    requested = root / "pilot-v1"
    requested.mkdir(parents=True)
    (requested / "existing.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="already exists and is not empty"):
        train._safe_new_run_dir(requested, runs_root=root, repository_root=tmp_path)


def test_safe_run_directory_rejects_an_internal_symbolic_link(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    target = root / "real-empty-directory"
    target.mkdir(parents=True)
    link = root / "pilot-v1"
    link.symlink_to(target, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        train._safe_new_run_dir(link, runs_root=root, repository_root=tmp_path)


def test_safe_run_directory_rejects_a_symbolic_link_ancestor(tmp_path: Path) -> None:
    real_root = tmp_path / "real-runs"
    real_root.mkdir()
    linked_root = tmp_path / "linked-runs"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(ValueError, match="symbolic link"):
        train._safe_new_run_dir(
            linked_root / "pilot-v1",
            runs_root=linked_root,
            repository_root=tmp_path,
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_optimizer_metrics_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="non-finite training metric"):
        train._normalise_metric({"loss": value}, label="optimizer_metrics")


def test_pilot_rejects_more_than_the_training_example_ceiling(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    copied = tmp_path / "too-many"
    shutil.copytree(prepared_output, copied)
    path = copied / "train.jsonl"
    lines = path.read_text(encoding="utf-8").splitlines()
    extra = json.loads(lines[0])
    extra["id"] = "synthetic-extra-001"
    extra["provenance"]["case"] = extra["id"]
    path.write_text("\n".join([*lines, json.dumps(extra)]) + "\n", encoding="utf-8")
    manifest = json.loads((copied / "manifest.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="allows at most 12 training examples"):
        train.validate_training_plan(
            data_dir=copied,
            manifest=manifest,
            batch_size=1,
            max_steps=1,
            learning_rate=1e-4,
            lora_rank=32,
        )


def test_pilot_rejects_more_than_the_step_ceiling(prepared_output: Path) -> None:
    manifest = json.loads((prepared_output / "manifest.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="max_steps must be between 1 and 6"):
        train.validate_training_plan(
            data_dir=prepared_output,
            manifest=manifest,
            batch_size=1,
            max_steps=train.MAX_PILOT_STEPS + 1,
            learning_rate=1e-4,
            lora_rank=32,
        )


def test_pilot_rejects_more_than_the_rendered_token_ceiling(
    prepared_output: Path,
    renderer_factory: Callable[[int], object],
) -> None:
    manifest = json.loads((prepared_output / "manifest.json").read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="rendered-token budget exceeded"):
        train.validate_training_plan(
            data_dir=prepared_output,
            manifest=manifest,
            batch_size=2,
            max_steps=1,
            learning_rate=1e-4,
            lora_rank=32,
            renderer=renderer_factory(5_002),
        )


def test_cli_redacts_the_api_key_if_paid_training_fails(
    prepared_output: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    renderer_factory: Callable[[int], object],
) -> None:
    secret = "tinker-test-secret-that-must-not-appear"
    project_id = "project-id-that-must-not-appear"

    def fail_training(**kwargs: object) -> dict[str, object]:
        assert kwargs["api_key"] == secret
        assert kwargs["project_id"] == project_id
        raise RuntimeError(f"upstream failure included {secret} and {project_id}")

    monkeypatch.setattr(train, "_load_renderer", lambda: renderer_factory(101))
    monkeypatch.setattr(train, "_safe_new_run_dir", lambda _path: tmp_path / "run")
    monkeypatch.setattr(train, "_run_training", fail_training)

    result = train.run(
        ["train", "--data-dir", str(prepared_output), "--execute"],
        environ={
            train.PAID_ACK_ENV: "YES",
            train.API_KEY_ENV: secret,
            train.PROJECT_ID_ENV: project_id,
        },
    )

    captured = capsys.readouterr()
    assert result == 1
    assert secret not in captured.out
    assert secret not in captured.err
    assert project_id not in captured.out
    assert project_id not in captured.err
    assert "[redacted]" in captured.err
