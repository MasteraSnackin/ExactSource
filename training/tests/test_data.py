from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest
from exactsource.prompts import (
    CELL_PROMPT_PLAN_SCHEMA_TEXT,
    SHEET_PROMPT_PLAN_SCHEMA_TEXT,
)

from exactsource_sft.data import (
    DEFAULT_CASE_FILE,
    MAX_LENGTH,
    _render_lengths,
    load_case_file,
    prepare_dataset,
    read_conversations,
    read_prepared_records,
    verify_prepared_dataset,
)

TRAIN_IDS = [
    "synthetic-sum-column-001",
    "synthetic-nested-if-001",
    "synthetic-index-match-001",
    "synthetic-vlookup-iferror-001",
    "synthetic-fill-product-001",
    "synthetic-fill-margin-001",
    "synthetic-countifs-001",
    "synthetic-sumifs-001",
    "synthetic-text-label-001",
    "synthetic-eomonth-001",
    "synthetic-clear-notes-001",
    "synthetic-filter-approved-sheet-001",
]
TUNE_IDS = [
    "synthetic-averageif-001",
    "synthetic-copy-template-001",
    "synthetic-rank-001",
    "synthetic-category-summary-sheet-001",
]


class _Count:
    def __init__(self, value: int) -> None:
        self.value = value

    def sum(self) -> _Count:
        return self

    def item(self) -> int:
        return self.value


class _Weights:
    def __init__(self, positive: int) -> None:
        self.positive = positive

    def __gt__(self, _other: object) -> _Count:
        return _Count(self.positive)


class FakeRenderer:
    def __init__(self, *, length: int = 512, positive_targets: int = 32) -> None:
        self.length = length
        self.positive_targets = positive_targets
        self.calls: list[list[dict[str, str]]] = []

    def build_supervised_example(
        self,
        messages: list[dict[str, str]],
        *,
        train_on_what: object,
    ) -> tuple[SimpleNamespace, _Weights]:
        assert getattr(train_on_what, "name", None) == "LAST_ASSISTANT_MESSAGE"
        self.calls.append(messages)
        return SimpleNamespace(length=self.length), _Weights(self.positive_targets)


def test_case_file_has_fixed_ordered_splits_and_unique_ids() -> None:
    resolved, case_file = load_case_file(DEFAULT_CASE_FILE)

    assert resolved == DEFAULT_CASE_FILE.resolve()
    assert [case.id for case in case_file.cases if case.split == "train"] == TRAIN_IDS
    assert [case.id for case in case_file.cases if case.split == "tune"] == TUNE_IDS
    assert len({case.id for case in case_file.cases}) == len(case_file.cases) == 16


def test_preparation_is_deterministic_with_an_injected_renderer(
    prepared_output: Path,
    tmp_path: Path,
    fake_formula_verifier: Callable[[object, Path, object], str],
) -> None:
    second_output = tmp_path / "second"
    second_renderer = FakeRenderer()

    second_manifest = prepare_dataset(
        output_dir=second_output,
        renderer=second_renderer,
        formula_verifier=fake_formula_verifier,
    )
    first_manifest = json.loads((prepared_output / "manifest.json").read_text(encoding="utf-8"))

    assert second_manifest == first_manifest
    for name in ("train.jsonl", "tune.jsonl", "manifest.json"):
        assert (second_output / name).read_bytes() == (prepared_output / name).read_bytes()
    assert len(second_renderer.calls) == 16

    conversations = read_conversations(second_output / "train.jsonl")
    assert len(conversations) == 12
    for messages in conversations:
        assert [message["role"] for message in messages] == ["system", "user", "assistant"]
        assert set(json.loads(messages[-1]["content"])) == {
            "operations",
            "python_code",
            "route",
            "summary",
        }


def test_manifest_hashes_each_route_specific_solve_schema(prepared_output: Path) -> None:
    manifest = json.loads((prepared_output / "manifest.json").read_text(encoding="utf-8"))
    expected = {
        "cell": hashlib.sha256(CELL_PROMPT_PLAN_SCHEMA_TEXT.encode("utf-8")).hexdigest(),
        "sheet": hashlib.sha256(SHEET_PROMPT_PLAN_SCHEMA_TEXT.encode("utf-8")).hexdigest(),
    }

    assert expected["cell"] != expected["sheet"]
    assert manifest["schema_version"] == 2
    assert manifest["solve_schema_sha256"] == expected
    assert verify_prepared_dataset(prepared_output)["solve_schema_sha256"] == expected


def test_source_verification_rejects_tampering_even_with_a_self_updated_hash(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    tampered = tmp_path / "tampered"
    shutil.copytree(prepared_output, tampered)
    train_path = tampered / "train.jsonl"
    lines = train_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["messages"][1]["content"] += " Tampered."
    lines[0] = json.dumps(
        first,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    train_text = "\n".join(lines) + "\n"
    train_path.write_text(train_text, encoding="utf-8")

    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["train_jsonl_sha256"] = hashlib.sha256(train_text.encode("utf-8")).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="does not reproduce from the reviewed case source"):
        verify_prepared_dataset(tampered)


def test_verification_detects_manifest_configuration_tampering(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    tampered = tmp_path / "tampered"
    shutil.copytree(prepared_output, tampered)
    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["model"] = "not-the-fixed-model"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="field 'model' does not match"):
        verify_prepared_dataset(tampered)


def test_verification_rejects_legacy_manifest_schema_version(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    tampered = tmp_path / "legacy-manifest"
    shutil.copytree(prepared_output, tampered)
    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported SFT manifest"):
        verify_prepared_dataset(tampered)


@pytest.mark.parametrize(
    "replacement",
    [
        "legacy-single-schema-hash",
        {"cell": "0" * 64},
        {"cell": "0" * 64, "sheet": "1" * 64},
        {"cell": "0" * 64, "sheet": "1" * 64, "other": "2" * 64},
    ],
)
def test_verification_rejects_incomplete_or_tampered_route_schema_hashes(
    prepared_output: Path,
    tmp_path: Path,
    replacement: object,
) -> None:
    tampered = tmp_path / "tampered-schema"
    shutil.copytree(prepared_output, tampered)
    manifest_path = tampered / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["solve_schema_sha256"] = replacement
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="hash mismatch for solve_schema_sha256"):
        verify_prepared_dataset(tampered)


def test_case_source_must_stay_beneath_the_declared_cases_root(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="beneath training/cases"):
        load_case_file(outside, cases_root=cases_root)


def test_case_source_rejects_a_symbolic_link(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    target = cases_root / "target.json"
    target.write_text("{}", encoding="utf-8")
    link = cases_root / "linked.json"
    link.symlink_to(target)

    with pytest.raises(ValueError, match="must not be a symbolic link"):
        load_case_file(link, cases_root=cases_root)


def _write_case_payload(tmp_path: Path, payload: object) -> tuple[Path, Path]:
    cases_root = tmp_path / "cases"
    cases_root.mkdir(parents=True)
    path = cases_root / "synthetic.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path, cases_root


def test_case_source_rejects_non_standard_numeric_constants(tmp_path: Path) -> None:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    path = cases_root / "synthetic.json"
    path.write_text('{"schema_version":1,"cases":[NaN]}', encoding="utf-8")

    with pytest.raises(ValueError, match="non-standard JSON numeric constant"):
        load_case_file(path, cases_root=cases_root)


def test_case_source_rejects_invalid_and_case_colliding_sheet_names(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_CASE_FILE.read_text(encoding="utf-8"))
    payload["cases"][0]["workbook"]["sheets"][0]["name"] = "Bad/Name"
    path, cases_root = _write_case_payload(tmp_path / "invalid", payload)

    with pytest.raises(ValueError, match="prohibited character"):
        load_case_file(path, cases_root=cases_root)

    payload = json.loads(DEFAULT_CASE_FILE.read_text(encoding="utf-8"))
    payload["cases"][0]["workbook"]["sheets"].append({"name": "data", "cells": {"A1": "collision"}})
    path, cases_root = _write_case_payload(tmp_path / "collision", payload)

    with pytest.raises(ValueError, match="case-insensitive duplicate"):
        load_case_file(path, cases_root=cases_root)


def test_case_source_requires_exact_answer_expectation_coverage(tmp_path: Path) -> None:
    payload = json.loads(DEFAULT_CASE_FILE.read_text(encoding="utf-8"))
    case = next(item for item in payload["cases"] if item["id"] == "synthetic-fill-product-001")
    del case["expectations"]["cells"]["Sales!D5"]
    del case["expectations"]["calculated"]["Sales!D5"]
    path, cases_root = _write_case_payload(tmp_path, payload)

    with pytest.raises(ValueError, match="cover every declared answer cell exactly"):
        load_case_file(path, cases_root=cases_root)


def test_rendered_example_over_the_fixed_limit_is_rejected() -> None:
    renderer = FakeRenderer(length=MAX_LENGTH + 1)

    with pytest.raises(ValueError, match=rf"{MAX_LENGTH + 1} tokens; limit is {MAX_LENGTH}"):
        _render_lengths(renderer, [{"role": "assistant", "content": "{}"}])


def test_rendered_example_must_have_a_positive_weight_target() -> None:
    renderer = FakeRenderer(positive_targets=0)

    with pytest.raises(ValueError, match="no positive-weight target tokens"):
        _render_lengths(renderer, [{"role": "assistant", "content": "{}"}])


def test_prepared_records_reject_message_objects_with_extra_fields(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    row = json.loads((prepared_output / "train.jsonl").read_text().splitlines()[0])
    row["messages"][0]["unexpected"] = True
    path = tmp_path / "malformed-messages.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid message objects"):
        read_prepared_records(path, expected_split="train")


def test_prepared_records_reject_mismatched_provenance(
    prepared_output: Path,
    tmp_path: Path,
) -> None:
    row = json.loads((prepared_output / "train.jsonl").read_text().splitlines()[0])
    row["provenance"]["split"] = "tune"
    path = tmp_path / "wrong-provenance.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid provenance"):
        read_prepared_records(path, expected_split="train")
