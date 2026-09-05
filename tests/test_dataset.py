from __future__ import annotations

import json
import os
from pathlib import Path

import openpyxl
import pytest

from exactsource.dataset import DatasetError, load_tasks


def _workbook(path: Path, *, sheet: str = "Input") -> None:
    workbook = openpyxl.Workbook()
    workbook.active.title = sheet
    workbook.active["A1"] = "source"
    workbook.save(path)


def _record(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "task-1",
        "instruction": "fallback instruction",
        "instruction_type": "Cell-Level Manipulation",
        "spreadsheet_path": "spreadsheet/task-1",
        "answer_position": "B2:B3",
    }
    record.update(overrides)
    return record


def _dataset(tmp_path: Path, records: list[dict[str, object]]) -> Path:
    root = tmp_path / "data"
    root.mkdir()
    for record in records:
        folder = root / str(record["spreadsheet_path"])
        folder.mkdir(parents=True, exist_ok=True)
        _workbook(folder / f"1_{record['id']}_init.xlsx")
    (root / "dataset.json").write_text(json.dumps(records), encoding="utf-8")
    return root


def test_load_tasks_prefers_prompt_and_uses_active_sheet(tmp_path: Path) -> None:
    root = _dataset(tmp_path, [_record()])
    folder = root / "spreadsheet/task-1"
    (folder / "prompt.txt").write_text("  prompt from file  \n", encoding="utf-8")
    # An invalid golden file proves the loader neither opens it nor mistakes it
    # for the single init workbook.
    (folder / "1_task-1_golden.xlsx").write_bytes(b"not an xlsx")

    tasks = load_tasks(root)

    assert len(tasks) == 1
    assert tasks[0].instruction == "prompt from file"
    assert tasks[0].answer_ranges[0].sheet == "Input"
    assert tasks[0].answer_ranges[0].cells == "B2:B3"
    assert tasks[0].init_xlsx.name == "1_task-1_init.xlsx"


def test_load_tasks_canonicalises_existing_sheet_but_keeps_future_sheet(tmp_path: Path) -> None:
    existing = _record(id="existing", spreadsheet_path="spreadsheet/existing", answer_sheet="HR")
    future = _record(id="future", spreadsheet_path="spreadsheet/future", answer_sheet="New Output")
    root = _dataset(tmp_path, [existing, future])
    existing_path = root / "spreadsheet/existing/1_existing_init.xlsx"
    _workbook(existing_path, sheet="HR ")

    tasks = load_tasks(root)

    assert tasks[0].answer_ranges[0].sheet == "HR "
    assert tasks[1].answer_ranges[0].sheet == "New Output"


def test_load_tasks_preserves_dataset_order_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    first = _record(id="2", spreadsheet_path="spreadsheet/2", answer_sheet="Input")
    second = _record(id="1", spreadsheet_path="spreadsheet/1", answer_sheet="Input")
    root = _dataset(tmp_path, [first, second])
    assert [task.id for task in load_tasks(root)] == ["2", "1"]

    (root / "dataset.json").write_text(json.dumps([first, first]), encoding="utf-8")
    with pytest.raises(DatasetError, match="duplicate task id"):
        load_tasks(root)


@pytest.mark.parametrize(
    "spreadsheet_path",
    ["../outside", "/absolute/path", "spreadsheet\\task-1", "spreadsheet/../task-1"],
)
def test_load_tasks_rejects_unsafe_declared_paths(tmp_path: Path, spreadsheet_path: str) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "dataset.json").write_text(
        json.dumps([_record(spreadsheet_path=spreadsheet_path, answer_sheet="Input")]),
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="spreadsheet_path|escapes"):
        load_tasks(root)


def test_load_tasks_rejects_symlink_escape_for_task_folder(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _workbook(outside / "1_task-1_init.xlsx")
    root = tmp_path / "data"
    (root / "spreadsheet").mkdir(parents=True)
    os.symlink(outside, root / "spreadsheet/task-1", target_is_directory=True)
    (root / "dataset.json").write_text(
        json.dumps([_record(answer_sheet="Input")]),
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="escapes the dataset root"):
        load_tasks(root)


def test_load_tasks_rejects_multiple_init_workbooks(tmp_path: Path) -> None:
    root = _dataset(tmp_path, [_record(answer_sheet="Input")])
    _workbook(root / "spreadsheet/task-1/2_task-1_init.xlsx")
    with pytest.raises(DatasetError, match="expected exactly one"):
        load_tasks(root)


def test_load_tasks_never_accepts_a_golden_named_file_as_the_init_workbook(
    tmp_path: Path,
) -> None:
    root = _dataset(tmp_path, [_record(answer_sheet="Input")])
    folder = root / "spreadsheet/task-1"
    (folder / "1_task-1_init.xlsx").unlink()
    # Invalid bytes make the regression fail differently if the loader ever
    # attempts to open this forbidden candidate.
    (folder / "1_task-1_init_golden.xlsx").write_bytes(b"not an xlsx")

    with pytest.raises(DatasetError, match="expected exactly one.*found 0"):
        load_tasks(root)


def test_load_tasks_rejects_an_init_symlink_to_a_golden_workbook(tmp_path: Path) -> None:
    root = _dataset(tmp_path, [_record(answer_sheet="Input")])
    folder = root / "spreadsheet/task-1"
    (folder / "1_task-1_init.xlsx").unlink()
    golden = folder / "1_task-1_golden.xlsx"
    golden.write_bytes(b"must never be opened")
    os.symlink(golden.name, folder / "1_task-1_init.xlsx")

    with pytest.raises(DatasetError, match="must not be a symbolic link"):
        load_tasks(root)


def test_load_tasks_rejects_unsafe_id_before_it_can_become_an_output_path(tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    (root / "dataset.json").write_text(
        json.dumps([_record(id="../escape", spreadsheet_path="spreadsheet/task-1")]),
        encoding="utf-8",
    )
    with pytest.raises(DatasetError, match="unsafe task id"):
        load_tasks(root)
