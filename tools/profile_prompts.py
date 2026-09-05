#!/usr/bin/env python3
"""Profile ExactSource request sizes without reading goldens or calling a model."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean

from exactsource.artifacts import atomic_write_text
from exactsource.config import CONTEXT_CHAR_BUDGET, MODEL_NAME
from exactsource.context import build_context
from exactsource.contracts import TaskSpec
from exactsource.dataset import load_tasks
from exactsource.model import serialise_request_payload
from exactsource.prompts import (
    CELL_SYSTEM_PROMPT,
    PROMPT_PLAN_SCHEMA_TEXT,
    SYSTEM_PROMPT,
    build_messages,
)


@dataclass(frozen=True, slots=True)
class PromptProfile:
    task_id: str
    kind: str
    context_original_chars: int
    context_emitted_chars: int
    context_truncated: bool
    user_content_chars: int
    message_content_chars: int
    request_chars: int
    request_utf8_bytes: int
    renderer_input_tokens: int | None = None


RendererTokenCounter = Callable[[list[dict[str, str]]], int]


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _nearest_rank(values: Sequence[int], percentile: int) -> int:
    if not values:
        raise ValueError("cannot calculate a percentile for an empty sequence")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile / 100 * len(ordered)) - 1)
    return ordered[index]


def distribution(values: Iterable[int]) -> dict[str, int | float]:
    """Return stable integer percentiles and an exact-to-two-decimals mean."""

    items = list(values)
    if not items:
        raise ValueError("cannot summarise an empty sequence")
    return {
        "min": min(items),
        "mean": round(fmean(items), 2),
        "p50": _nearest_rank(items, 50),
        "p90": _nearest_rank(items, 90),
        "p95": _nearest_rank(items, 95),
        "p99": _nearest_rank(items, 99),
        "max": max(items),
    }


def profile_task(
    task: TaskSpec,
    *,
    renderer_token_counter: RendererTokenCounter | None = None,
) -> PromptProfile:
    context = build_context(task)
    messages = build_messages(task, context)
    _validated, _payload, request = serialise_request_payload(messages)
    message_lengths = [len(message["content"]) for message in messages]
    renderer_input_tokens = (
        renderer_token_counter(messages) if renderer_token_counter is not None else None
    )
    if renderer_input_tokens is not None and renderer_input_tokens < 1:
        raise ValueError("renderer input-token count must be positive")
    return PromptProfile(
        task_id=task.id,
        kind="cell" if task.is_cell_level else "sheet",
        context_original_chars=context.original_chars,
        context_emitted_chars=len(context.text),
        context_truncated=context.truncated,
        user_content_chars=message_lengths[-1],
        message_content_chars=sum(message_lengths),
        request_chars=len(request),
        request_utf8_bytes=len(request.encode("utf-8")),
        renderer_input_tokens=renderer_input_tokens,
    )


def build_report(
    profiles: Sequence[PromptProfile],
    *,
    dataset_sha256: str,
    selection_name: str,
    renderer_metadata: Mapping[str, str | int] | None = None,
) -> dict[str, object]:
    if not profiles:
        raise ValueError("at least one prompt profile is required")

    ordered = sorted(profiles, key=lambda item: item.task_id)
    largest = sorted(
        profiles,
        key=lambda item: (-item.request_chars, item.task_id),
    )[:10]
    truncated = sum(item.context_truncated for item in profiles)
    by_kind = Counter(item.kind for item in profiles)
    counted = [item.renderer_input_tokens is not None for item in profiles]
    if any(counted) and not all(counted):
        raise ValueError("renderer token counts must be present for every profile or none")
    renderer_tokens_included = all(counted)

    summary: dict[str, object] = {
        "tasks": len(profiles),
        "tasks_by_kind": dict(sorted(by_kind.items())),
        "context_truncated_tasks": truncated,
        "context_truncated_rate": round(truncated / len(profiles), 6),
        "context_original_chars": distribution(item.context_original_chars for item in profiles),
        "context_emitted_chars": distribution(item.context_emitted_chars for item in profiles),
        "user_content_chars": distribution(item.user_content_chars for item in profiles),
        "message_content_chars": distribution(item.message_content_chars for item in profiles),
        "request_chars": distribution(item.request_chars for item in profiles),
        "request_utf8_bytes": distribution(item.request_utf8_bytes for item in profiles),
    }
    if renderer_tokens_included:
        summary["renderer_input_tokens"] = distribution(
            item.renderer_input_tokens
            for item in profiles
            if item.renderer_input_tokens is not None
        )

    token_counting: dict[str, object] = {
        "enabled": renderer_tokens_included,
        "definition": "generation prompt before model output",
    }
    if renderer_metadata:
        token_counting.update(dict(sorted(renderer_metadata.items())))

    return {
        "schema_version": 2,
        "method": "initial-workbook prompt profiling; no model calls or golden access",
        "dataset_json_sha256": dataset_sha256,
        "selection": selection_name,
        "configuration": {
            "model": MODEL_NAME,
            "context_char_budget": CONTEXT_CHAR_BUDGET,
            "request_serialisation": "compact JSON, ensure_ascii=false",
            "request_scope": "exact fixed Anthropic-compatible provider payload",
            "renderer_token_counting": token_counting,
            "system_prompts": {
                "cell": {
                    "chars": len(CELL_SYSTEM_PROMPT),
                    "sha256": _sha256_text(CELL_SYSTEM_PROMPT),
                },
                "sheet": {
                    "chars": len(SYSTEM_PROMPT),
                    "sha256": _sha256_text(SYSTEM_PROMPT),
                },
            },
            "solve_plan_schema_chars": len(PROMPT_PLAN_SCHEMA_TEXT),
            "solve_plan_schema_sha256": _sha256_text(PROMPT_PLAN_SCHEMA_TEXT),
        },
        "summary": summary,
        "largest_requests": [asdict(item) for item in largest],
        "task_profiles": [asdict(item) for item in ordered],
    }


def _dataset_sha256(dataset_dir: Path) -> str:
    digest = hashlib.sha256()
    with (dataset_dir / "dataset.json").open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _selection(path: Path | None, field: str) -> tuple[set[str] | None, str]:
    if path is None:
        return None, "all"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read selection JSON from {path}: {exc}") from exc
    values = payload.get(field) if isinstance(payload, dict) else None
    if not isinstance(values, list) or not values:
        raise ValueError(f"selection field {field!r} must be a non-empty list")
    selected: set[str] = set()
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValueError(f"selection field {field!r} contains an invalid task id")
        selected.add(str(value))
    if len(selected) != len(values):
        raise ValueError(f"selection field {field!r} contains duplicate task ids")
    return selected, f"{path.name}:{field}"


def _load_renderer_token_counter() -> tuple[RendererTokenCounter, dict[str, str | int]]:
    try:
        from exactsource_sft.data import (
            MODEL_ID,
            RENDERER_NAME,
            TOKENIZER_REVISION,
            TOKENIZER_VOCAB_SIZE,
            _load_renderer,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "exact renderer counts require the isolated training environment; "
            "run this command with 'uv run --project training'"
        ) from exc

    renderer = _load_renderer()

    def count(messages: list[dict[str, str]]) -> int:
        return int(renderer.build_generation_prompt(messages).length)

    return count, {
        "model": MODEL_ID,
        "renderer": RENDERER_NAME,
        "tokenizer_revision": TOKENIZER_REVISION,
        "tokenizer_vocab_size": TOKENIZER_VOCAB_SIZE,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument(
        "--selection-file",
        type=Path,
        help="JSON file containing the task-id list to profile",
    )
    parser.add_argument(
        "--selection-field",
        default="development_ids",
        help="field in --selection-file (default: development_ids)",
    )
    parser.add_argument(
        "--renderer-token-counts",
        action="store_true",
        help=(
            "include exact offline Qwen renderer input-token counts; requires "
            "the isolated training environment and cached pinned tokenizer"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        dataset_dir = args.dataset_dir.resolve(strict=True)
        selected, selection_name = _selection(args.selection_file, args.selection_field)
        tasks = load_tasks(dataset_dir)
        if selected is not None:
            available = {task.id for task in tasks}
            unknown = sorted(selected - available)
            if unknown:
                raise ValueError(f"selection contains unknown task ids: {unknown[:5]}")
            tasks = [task for task in tasks if task.id in selected]
        token_counter = None
        renderer_metadata = None
        if args.renderer_token_counts:
            token_counter, renderer_metadata = _load_renderer_token_counter()
        profiles = [profile_task(task, renderer_token_counter=token_counter) for task in tasks]
        report = build_report(
            profiles,
            dataset_sha256=_dataset_sha256(dataset_dir),
            selection_name=selection_name,
            renderer_metadata=renderer_metadata,
        )
        report_text = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        atomic_write_text(args.out, report_text)
    except Exception as exc:
        print(f"prompt profile failed: {exc}")
        return 1
    print(
        json.dumps(
            {"out": str(args.out), **report["summary"]},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
