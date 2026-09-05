import importlib.util
import sys
from pathlib import Path


def load_splitter():
    script = Path(__file__).parents[1] / "tools" / "freeze_split.py"
    spec = importlib.util.spec_from_file_location("freeze_split", script)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


splitter = load_splitter()


def feature(task_id: str, kind: str, family: str, bucket: str):
    return splitter.Features(
        task_id=task_id,
        kind=kind,
        family=family,
        answer_size_bucket=bucket,
        has_formula=False,
        multi_sheet=False,
        macro_wording=False,
        exceeds_baseline_window=False,
        has_table=False,
        has_defined_name=False,
    )


def test_apportionment_is_exact_deterministic_and_disjoint() -> None:
    rows = [
        feature(
            str(index),
            "cell" if index < 15 else "sheet",
            "lookup" if index % 2 else "aggregate",
            "01-10" if index % 3 else "11-50",
        )
        for index in range(20)
    ]

    first_dev, first_holdout = splitter.apportion_holdout(rows, count=4, seed="fixed")
    second_dev, second_holdout = splitter.apportion_holdout(rows, count=4, seed="fixed")

    assert (first_dev, first_holdout) == (second_dev, second_holdout)
    assert len(first_dev) == 16
    assert len(first_holdout) == 4
    assert set(first_dev).isdisjoint(first_holdout)
    assert set(first_dev) | set(first_holdout) == {str(index) for index in range(20)}
    by_id = {row.task_id: row for row in rows}
    assert sum(by_id[task_id].kind == "cell" for task_id in first_holdout) == 3
    assert sum(by_id[task_id].kind == "sheet" for task_id in first_holdout) == 1


def test_size_buckets_cover_large_ranges() -> None:
    assert splitter.size_bucket(1) == "01-10"
    assert splitter.size_bucket(1_001) == "1001-10000"
    assert splitter.size_bucket(100_000) == "10001+"
