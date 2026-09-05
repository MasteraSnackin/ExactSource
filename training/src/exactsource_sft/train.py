"""Command-line preparation and deliberately gated Tinker SFT pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from exactsource.artifacts import atomic_write_text

from exactsource_sft.data import (
    DEFAULT_CASE_FILE,
    DEFAULT_OUTPUT_DIR,
    MAX_LENGTH,
    MODEL_ID,
    RENDERER_NAME,
    REPOSITORY_DIR,
    TRAINING_SEED,
    _load_renderer,
    prepare_dataset,
    read_prepared_records,
    verify_prepared_dataset,
)

PAID_ACK_ENV = "EXACTSOURCE_ALLOW_PAID_TRAINING"
API_KEY_ENV = "TINKER_API_KEY"
PROJECT_ID_ENV = "TINKER_PROJECT_ID"
RUNS_ROOT = DEFAULT_OUTPUT_DIR / "runs"

MAX_PILOT_STEPS = 6
MAX_PILOT_TRAIN_EXAMPLES = 12
MAX_PILOT_TOTAL_RENDERED_TOKENS = 50_000
ALLOWED_LORA_RANKS = {8, 16, 32, 64}


@dataclass(frozen=True, slots=True)
class PilotPlan:
    batch_size: int
    max_steps: int
    learning_rate: float
    lora_rank: int
    train_ids: tuple[str, ...]
    train_datums: tuple[Any, ...]
    tune_ids: tuple[str, ...]
    tune_datums: tuple[Any, ...]
    tokenizer: Any
    manifest: Mapping[str, object]
    manifest_sha256: str
    data_fingerprint: str
    projected_train_tokens: int
    projected_tune_tokens_per_pass: int
    projected_total_tokens: int


def _json_text(value: object, *, compact: bool = False) -> str:
    separators = (",", ":") if compact else None
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=None if compact else 2,
            separators=separators,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )


def paid_training_gate(*, execute: bool, environ: Mapping[str, str]) -> bool:
    """Return False for dry-run; reject incomplete authority before Tinker imports."""

    if not execute:
        return False
    if environ.get(PAID_ACK_ENV) != "YES":
        raise ValueError(f"paid training requires {PAID_ACK_ENV}=YES")
    if not environ.get(API_KEY_ENV, "").strip():
        raise ValueError(f"paid training requires {API_KEY_ENV}")
    if not environ.get(PROJECT_ID_ENV, "").strip():
        raise ValueError(f"paid training requires a writable {PROJECT_ID_ENV}")
    return True


def _safe_error_message(exc: Exception, environ: Mapping[str, str]) -> str:
    """Return an actionable CLI error without echoing credential material."""

    message = str(exc) or type(exc).__name__
    for environment_name in (API_KEY_ENV, PROJECT_ID_ENV):
        raw_secret = environ.get(environment_name, "")
        for secret in {raw_secret, raw_secret.strip()}:
            if secret:
                message = message.replace(secret, "[redacted]")
    return message


def _safe_new_run_dir(
    path: Path,
    *,
    runs_root: Path = RUNS_ROOT,
    repository_root: Path = REPOSITORY_DIR,
) -> Path:
    requested_repository = Path(repository_root).absolute()
    requested_root = Path(runs_root).absolute()
    requested_candidate = Path(path).absolute()
    try:
        root_relative = requested_root.relative_to(requested_repository)
        candidate_relative = requested_candidate.relative_to(requested_root)
    except ValueError as exc:
        raise ValueError("training run directory must be beneath scratch/sft/runs") from exc
    if not root_relative.parts:
        raise ValueError("training runs root must be a named child of the repository")
    if not candidate_relative.parts:
        raise ValueError("training run directory must be a named child of scratch/sft/runs")

    current = requested_repository
    for part in (*root_relative.parts, *candidate_relative.parts):
        if current.is_symlink():
            raise ValueError("training run path must not contain symbolic links")
        current /= part
    if current.is_symlink():
        raise ValueError("training run path must not contain symbolic links")

    repository = requested_repository.resolve(strict=True)
    root = requested_root.resolve(strict=False)
    candidate = requested_candidate.resolve(strict=False)
    try:
        root.relative_to(repository)
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("training run directory resolves outside the repository") from exc
    if candidate.exists() and (not candidate.is_dir() or any(candidate.iterdir())):
        raise ValueError("training run directory already exists and is not empty")
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def _append_jsonl(path: Path, record: Mapping[str, object]) -> None:
    line = _json_text(record, compact=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _render_datum(messages: list[dict[str, str]], renderer: Any) -> Any:
    from tinker_cookbook.renderers import TrainOnWhat
    from tinker_cookbook.supervised.data import conversation_to_datum

    datum = conversation_to_datum(
        messages,
        renderer,
        max_length=None,
        train_on_what=TrainOnWhat.LAST_ASSISTANT_MESSAGE,
    )
    if datum.model_input.length > MAX_LENGTH:
        raise ValueError(
            f"prepared datum has {datum.model_input.length} tokens; limit is {MAX_LENGTH}"
        )
    return datum


def validate_training_plan(
    *,
    data_dir: Path,
    manifest: Mapping[str, object],
    batch_size: int,
    max_steps: int,
    learning_rate: float,
    lora_rank: int,
    renderer: Any | None = None,
) -> PilotPlan:
    """Render and cap the exact paid pilot before checking paid authority."""

    train_records = read_prepared_records(data_dir / "train.jsonl", expected_split="train")
    tune_records = read_prepared_records(data_dir / "tune.jsonl", expected_split="tune")
    if len(train_records) > MAX_PILOT_TRAIN_EXAMPLES:
        raise ValueError(f"paid pilot allows at most {MAX_PILOT_TRAIN_EXAMPLES} training examples")
    if batch_size < 1 or len(train_records) % batch_size:
        raise ValueError("training examples must divide evenly by the positive batch size")
    available_steps = len(train_records) // batch_size
    if max_steps < 1 or max_steps > available_steps or max_steps > MAX_PILOT_STEPS:
        raise ValueError(f"max_steps must be between 1 and {min(available_steps, MAX_PILOT_STEPS)}")
    if not math.isfinite(learning_rate) or not 0 < learning_rate <= 1e-2:
        raise ValueError("learning_rate must be finite, greater than zero and at most 0.01")
    if lora_rank not in ALLOWED_LORA_RANKS:
        raise ValueError("lora_rank must be one of 8, 16, 32 or 64")

    active_renderer = renderer or _load_renderer()
    tokenizer = active_renderer.tokenizer
    train_pairs = [
        (record.id, _render_datum(record.messages, active_renderer)) for record in train_records
    ]
    tune_pairs = [
        (record.id, _render_datum(record.messages, active_renderer)) for record in tune_records
    ]
    random.Random(TRAINING_SEED).shuffle(train_pairs)
    used_count = batch_size * max_steps
    selected = train_pairs[:used_count]
    train_tokens = sum(datum.model_input.length for _case_id, datum in selected)
    tune_tokens = sum(datum.model_input.length for _case_id, datum in tune_pairs)
    total_tokens = train_tokens + 2 * tune_tokens
    if total_tokens > MAX_PILOT_TOTAL_RENDERED_TOKENS:
        raise ValueError(
            "paid pilot rendered-token budget exceeded: "
            f"{total_tokens} > {MAX_PILOT_TOTAL_RENDERED_TOKENS}"
        )

    canonical_manifest = _json_text(manifest).encode("utf-8")
    manifest_sha256 = hashlib.sha256(canonical_manifest).hexdigest()
    fingerprint_material = {
        "manifest_sha256": manifest_sha256,
        "selected_train_ids": [case_id for case_id, _datum in selected],
        "tune_ids": [case_id for case_id, _datum in tune_pairs],
        "batch_size": batch_size,
        "max_steps": max_steps,
        "learning_rate": learning_rate,
        "lora_rank": lora_rank,
    }
    data_fingerprint = hashlib.sha256(
        _json_text(fingerprint_material, compact=True).encode("utf-8")
    ).hexdigest()
    return PilotPlan(
        batch_size=batch_size,
        max_steps=max_steps,
        learning_rate=learning_rate,
        lora_rank=lora_rank,
        train_ids=tuple(case_id for case_id, _datum in selected),
        train_datums=tuple(datum for _case_id, datum in selected),
        tune_ids=tuple(case_id for case_id, _datum in tune_pairs),
        tune_datums=tuple(datum for _case_id, datum in tune_pairs),
        tokenizer=tokenizer,
        manifest=dict(manifest),
        manifest_sha256=manifest_sha256,
        data_fingerprint=data_fingerprint,
        projected_train_tokens=train_tokens,
        projected_tune_tokens_per_pass=tune_tokens,
        projected_total_tokens=total_tokens,
    )


def _normalise_metric(value: object, *, label: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"non-finite training metric: {label}")
        return value
    if isinstance(value, Mapping):
        return {
            str(key): _normalise_metric(item, label=f"{label}.{key}") for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [
            _normalise_metric(item, label=f"{label}[{index}]") for index, item in enumerate(value)
        ]
    item_method = getattr(value, "item", None)
    if callable(item_method):
        return _normalise_metric(item_method(), label=label)
    raise ValueError(f"unsupported training metric type for {label}: {type(value).__name__}")


def _loss_metrics(output: Any, datums: Sequence[Any], tokenizer: Any) -> dict[str, float]:
    from tinker_cookbook.supervised.common import compute_bpb, compute_mean_nll

    logprobs = [result["logprobs"] for result in output.loss_fn_outputs]
    weights = [datum.loss_fn_inputs["weights"] for datum in datums]
    targets = [datum.loss_fn_inputs["target_tokens"] for datum in datums]
    values = {
        "mean_nll": float(compute_mean_nll(logprobs, weights)),
        "mean_bpb": float(compute_bpb(logprobs, weights, targets, tokenizer)),
    }
    for name, value in values.items():
        if not math.isfinite(value):
            raise ValueError(f"non-finite training metric: {name}")
    return values


def _run_training(
    *,
    plan: PilotPlan,
    run_dir: Path,
    project_id: str,
    api_key: str,
) -> dict[str, object]:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    import tinker
    from tinker_cookbook import checkpoint_utils

    config = {
        "schema_version": 1,
        "model": MODEL_ID,
        "renderer": RENDERER_NAME,
        "train_on_what": "LAST_ASSISTANT_MESSAGE",
        "seed": TRAINING_SEED,
        "batch_size": plan.batch_size,
        "max_steps": plan.max_steps,
        "learning_rate": plan.learning_rate,
        "lora_rank": plan.lora_rank,
        "max_length": MAX_LENGTH,
        "max_pilot_steps": MAX_PILOT_STEPS,
        "max_pilot_train_examples": MAX_PILOT_TRAIN_EXAMPLES,
        "max_pilot_total_rendered_tokens": MAX_PILOT_TOTAL_RENDERED_TOKENS,
        "projected_train_tokens": plan.projected_train_tokens,
        "projected_tune_tokens_per_pass": plan.projected_tune_tokens_per_pass,
        "projected_total_tokens": plan.projected_total_tokens,
        "selected_train_ids": list(plan.train_ids),
        "tune_ids": list(plan.tune_ids),
        "verified_manifest_sha256": plan.manifest_sha256,
        "data_fingerprint": plan.data_fingerprint,
        "source_case_sha256": plan.manifest["source_case_sha256"],
        "train_jsonl_sha256": plan.manifest["train_jsonl_sha256"],
        "tune_jsonl_sha256": plan.manifest["tune_jsonl_sha256"],
        "system_prompt_sha256": plan.manifest["system_prompt_sha256"],
        "solve_schema_sha256": plan.manifest["solve_schema_sha256"],
        "dependencies": plan.manifest["dependencies"],
        "tokenizer": plan.manifest["tokenizer"],
        "project_id_recorded": True,
    }
    atomic_write_text(run_dir / "config.json", _json_text(config))
    atomic_write_text(run_dir / "verified_manifest.json", _json_text(plan.manifest))

    metadata = {
        "experiment": "exactsource-sft-v1",
        "renderer_name": RENDERER_NAME,
        "data_fingerprint": plan.data_fingerprint,
    }
    service = tinker.ServiceClient(
        project_id=project_id,
        api_key=api_key,
        user_metadata=metadata,
    )
    client = service.create_lora_training_client(
        base_model=MODEL_ID,
        rank=plan.lora_rank,
        seed=TRAINING_SEED,
        user_metadata=metadata,
    )
    started = time.monotonic()
    metrics_path = run_dir / "metrics.jsonl"
    evaluation_path = run_dir / "tune_metrics.jsonl"

    before = client.forward(list(plan.tune_datums), loss_fn="cross_entropy").result()
    _append_jsonl(
        evaluation_path,
        {
            "phase": "before_training",
            "case_ids": list(plan.tune_ids),
            "tokens": plan.projected_tune_tokens_per_pass,
            **_loss_metrics(before, plan.tune_datums, plan.tokenizer),
        },
    )

    for step in range(plan.max_steps):
        start = step * plan.batch_size
        end = start + plan.batch_size
        batch = plan.train_datums[start:end]
        case_ids = plan.train_ids[start:end]
        step_started = time.monotonic()
        lr_multiplier = 1.0 - step / plan.max_steps
        current_lr = plan.learning_rate * lr_multiplier
        forward_future = client.forward_backward(list(batch), loss_fn="cross_entropy")
        optim_future = client.optim_step(
            tinker.AdamParams(
                learning_rate=current_lr,
                beta1=0.9,
                beta2=0.95,
                eps=1e-8,
            )
        )
        forward = forward_future.result()
        optim = optim_future.result()
        train_metrics = _loss_metrics(forward, batch, plan.tokenizer)
        record: dict[str, object] = {
            "step": step,
            "case_ids": list(case_ids),
            "sequences": len(batch),
            "tokens": sum(datum.model_input.length for datum in batch),
            "learning_rate": current_lr,
            "train_mean_nll": train_metrics["mean_nll"],
            "train_mean_bpb": train_metrics["mean_bpb"],
            "step_wall_time_ms": round((time.monotonic() - step_started) * 1_000),
        }
        if optim.metrics:
            record["optimizer_metrics"] = _normalise_metric(
                optim.metrics,
                label="optimizer_metrics",
            )
        _append_jsonl(metrics_path, record)

    after = client.forward(list(plan.tune_datums), loss_fn="cross_entropy").result()
    _append_jsonl(
        evaluation_path,
        {
            "phase": "after_training",
            "case_ids": list(plan.tune_ids),
            "tokens": plan.projected_tune_tokens_per_pass,
            **_loss_metrics(after, plan.tune_datums, plan.tokenizer),
        },
    )

    paths = checkpoint_utils.save_checkpoint(
        training_client=client,
        name="final",
        log_path=str(run_dir),
        kind="both",
        loop_state={
            "step": plan.max_steps,
            "final": True,
            "data_fingerprint": plan.data_fingerprint,
        },
        ttl_seconds=None,
    )
    result = {
        "schema_version": 1,
        "steps_completed": plan.max_steps,
        "data_fingerprint": plan.data_fingerprint,
        "training_wall_time_ms": round((time.monotonic() - started) * 1_000),
        **paths,
    }
    atomic_write_text(run_dir / "result.json", _json_text(result))
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="exactsource-sft", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare", help="build and validate synthetic JSONL offline")
    prepare.add_argument("--cases", type=Path, default=DEFAULT_CASE_FILE)
    prepare.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    prepare.add_argument("--soffice", type=Path)

    train = subparsers.add_parser("train", help="preflight or explicitly run the paid pilot")
    train.add_argument("--data-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    train.add_argument("--cases", type=Path, default=DEFAULT_CASE_FILE)
    train.add_argument("--run-dir", type=Path, default=RUNS_ROOT / "pilot-v1")
    train.add_argument("--batch-size", type=int, default=2)
    train.add_argument("--max-steps", type=int, default=4)
    train.add_argument("--learning-rate", type=float, default=1e-4)
    train.add_argument("--lora-rank", type=int, default=32)
    train.add_argument("--execute", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    args = _parser().parse_args(argv)
    active_environ = os.environ if environ is None else environ
    try:
        if args.command == "prepare":
            manifest = prepare_dataset(args.cases, args.out_dir, soffice=args.soffice)
            print(
                _json_text(
                    {
                        "mode": "offline-prepare",
                        "train_examples": len(manifest["ordered_train_ids"]),
                        "tune_examples": len(manifest["ordered_tune_ids"]),
                        "formula_cases_verified": len(manifest["formula_verification"]["case_ids"]),
                        "out_dir": str(args.out_dir),
                    }
                ),
                end="",
            )
            return 0

        manifest = verify_prepared_dataset(args.data_dir, case_path=args.cases)
        plan = validate_training_plan(
            data_dir=args.data_dir,
            manifest=manifest,
            batch_size=args.batch_size,
            max_steps=args.max_steps,
            learning_rate=args.learning_rate,
            lora_rank=args.lora_rank,
        )
        if not paid_training_gate(execute=args.execute, environ=active_environ):
            print(
                _json_text(
                    {
                        "mode": "offline-preflight",
                        "model": manifest["model"],
                        "train_examples_available": len(manifest["ordered_train_ids"]),
                        "train_examples_selected": len(plan.train_ids),
                        "tune_examples": len(plan.tune_ids),
                        "would_run_steps": plan.max_steps,
                        "projected_train_tokens": plan.projected_train_tokens,
                        "projected_tune_tokens_per_pass": plan.projected_tune_tokens_per_pass,
                        "projected_total_tokens": plan.projected_total_tokens,
                        "maximum_pilot_tokens": MAX_PILOT_TOTAL_RENDERED_TOKENS,
                        "data_fingerprint": plan.data_fingerprint,
                    }
                ),
                end="",
            )
            return 0

        run_dir = _safe_new_run_dir(args.run_dir)
        result = _run_training(
            plan=plan,
            run_dir=run_dir,
            project_id=active_environ[PROJECT_ID_ENV].strip(),
            api_key=active_environ[API_KEY_ENV].strip(),
        )
        print(_json_text(result), end="")
        return 0
    except Exception as exc:
        print(
            f"ExactSource SFT failed: {_safe_error_message(exc, active_environ)}",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
