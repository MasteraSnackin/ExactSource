import json
import subprocess
import sys
from pathlib import Path

import openpyxl

from exactsource.artifacts import read_jsonl


def _write_dataset(root: Path) -> Path:
    data = root / "data"
    task_dir = data / "spreadsheet" / "control-1"
    task_dir.mkdir(parents=True)
    workbook = openpyxl.Workbook()
    workbook.active.title = "Input"
    workbook.active["A1"] = "unchanged"
    workbook.save(task_dir / "book_init.xlsx")
    workbook.close()
    (task_dir / "prompt.txt").write_text("Leave this untouched for the control.", encoding="utf-8")
    (data / "dataset.json").write_text(
        json.dumps(
            [
                {
                    "id": "control-1",
                    "instruction_type": "Cell-Level",
                    "instruction": "fallback",
                    "spreadsheet_path": "spreadsheet/control-1",
                    "answer_position": "B1",
                    "answer_sheet": "Input",
                    "data_position": "Input!A1:A1",
                }
            ]
        ),
        encoding="utf-8",
    )
    return data


def test_copy_baseline_is_complete_and_byte_identical(tmp_path: Path) -> None:
    data = _write_dataset(tmp_path)
    out = tmp_path / "out"
    command = [
        sys.executable,
        "tools/make_copy_baseline.py",
        "--dataset-dir",
        str(data),
        "--out-dir",
        str(out),
    ]

    completed = subprocess.run(command, capture_output=True, text=True, check=False)

    assert completed.returncode == 0, completed.stderr
    assert (out / "outputs" / "control-1.xlsx").read_bytes() == (
        data / "spreadsheet" / "control-1" / "book_init.xlsx"
    ).read_bytes()
    assert read_jsonl(out / "predictions.jsonl") == [
        {
            "id": "control-1",
            "output": "outputs/control-1.xlsx",
            "status": "control_copy",
        }
    ]
    trace = read_jsonl(out / "traces" / "control-1.jsonl")
    assert trace[0]["model_calls"] == 0
    assert trace[0]["model"] == "none:untouched-workbook-control"
    assert json.loads((out / "run.log").read_text())["tasks"] == 1
