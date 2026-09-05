import importlib.util
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import openpyxl


def _load_checker():
    script = Path(__file__).parents[1] / "tools" / "check_formula_compatibility.py"
    spec = importlib.util.spec_from_file_location("check_formula_compatibility", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()
FORMULA_CASES = checker.FORMULA_CASES
RESULT_CELL = checker.RESULT_CELL
SHEET_NAME = checker.SHEET_NAME
main = checker.main
render_json = checker.render_json
run_compatibility_check = checker.run_compatibility_check
values_equal = checker._values_equal

EXPECTED_STORAGE_NAMES = {
    "AGGREGATE": "_xlfn.AGGREGATE",
    "CHOOSECOLS": "_xlfn.CHOOSECOLS",
    "CONCAT": "_xlfn.CONCAT",
    "DROP": "_xlfn.DROP",
    "FILTER": "_xlfn._xlws.FILTER",
    "FILTERXML": "_xlfn.FILTERXML",
    "IFNA": "_xlfn.IFNA",
    "LET": "_xlfn.LET",
    "MAXIFS": "_xlfn.MAXIFS",
    "MINIFS": "_xlfn.MINIFS",
    "SORT": "_xlfn._xlws.SORT",
    "SORTBY": "_xlfn.SORTBY",
    "TEXTJOIN": "_xlfn.TEXTJOIN",
    "TEXTSPLIT": "_xlfn.TEXTSPLIT",
    "UNIQUE": "_xlfn.UNIQUE",
    "XLOOKUP": "_xlfn.XLOOKUP",
}


def _fake_soffice(path: Path) -> Path:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def _materialising_recalculator(
    sources: Sequence[Path],
    output_dir: Path,
    profile_dir: Path,
    soffice: Path,
    *,
    mismatched_case: str | None = None,
    observed_temp_roots: list[Path] | None = None,
) -> None:
    assert profile_dir.is_dir()
    assert soffice.is_absolute()
    if observed_temp_roots is not None:
        observed_temp_roots.append(sources[0].parent.parent)
    cases = {case.case_id: case for case in FORMULA_CASES}
    for source in sources:
        case = cases[source.stem]
        workbook = openpyxl.load_workbook(source, data_only=False)
        try:
            assert workbook[SHEET_NAME][RESULT_CELL].value == case.formula
            value = case.expected
            if case.case_id == mismatched_case:
                value = "deliberate mismatch"
            workbook[SHEET_NAME][RESULT_CELL] = value
            workbook.save(output_dir / source.name)
        finally:
            workbook.close()


def test_catalog_covers_exactly_the_sixteen_storage_names() -> None:
    assert len(FORMULA_CASES) == 16
    assert {case.function: case.stored_name for case in FORMULA_CASES} == (EXPECTED_STORAGE_NAMES)
    assert [case.case_id for case in FORMULA_CASES] == sorted(
        case.case_id for case in FORMULA_CASES
    )
    for case in FORMULA_CASES:
        assert case.formula.startswith("=")
        assert case.stored_name in case.formula


def test_run_uses_cached_results_and_cleans_its_temporary_directory(tmp_path: Path) -> None:
    executable = _fake_soffice(tmp_path / "soffice")
    observed_temp_roots: list[Path] = []

    def fake_recalculator(
        sources: Sequence[Path], output_dir: Path, profile_dir: Path, soffice: Path
    ) -> None:
        _materialising_recalculator(
            sources,
            output_dir,
            profile_dir,
            soffice,
            observed_temp_roots=observed_temp_roots,
        )

    result = run_compatibility_check(
        executable.resolve(),
        recalculator=fake_recalculator,
        engine_version="FakeCalc 1.0",
    )

    assert result["summary"] == {"failed": 0, "passed": 16, "total": 16}
    assert result["engine"] == {
        "executable": str(executable.resolve()),
        "version": "FakeCalc 1.0",
    }
    assert all(case["actual"] == case["expected"] for case in result["cases"])
    assert len(observed_temp_roots) == 1
    assert not observed_temp_roots[0].exists()


def test_main_writes_identical_json_and_exits_one_on_a_mismatch(tmp_path: Path, capsys) -> None:
    executable = _fake_soffice(tmp_path / "soffice")
    output = tmp_path / "result" / "compatibility.json"

    def fake_recalculator(
        sources: Sequence[Path], output_dir: Path, profile_dir: Path, soffice: Path
    ) -> None:
        _materialising_recalculator(
            sources,
            output_dir,
            profile_dir,
            soffice,
            mismatched_case="xlookup",
        )

    return_code = main(
        ["--soffice", str(executable), "--out", str(output)],
        recalculator=fake_recalculator,
        engine_version="FakeCalc 1.0",
    )

    captured = capsys.readouterr()
    assert return_code == 1
    assert captured.err == ""
    assert output.read_text(encoding="utf-8") == captured.out
    parsed = json.loads(captured.out)
    assert parsed["summary"] == {"failed": 1, "passed": 15, "total": 16}
    mismatch = next(case for case in parsed["cases"] if not case["passed"])
    assert mismatch["id"] == "xlookup"
    assert render_json(parsed) == captured.out


def test_boolean_results_are_not_treated_as_numbers() -> None:
    assert not values_equal(True, 1)
    assert not values_equal(0, False)
