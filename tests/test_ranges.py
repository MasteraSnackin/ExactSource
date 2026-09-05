from __future__ import annotations

import pytest

from exactsource.contracts import QualifiedRange
from exactsource.ranges import (
    RangeSyntaxError,
    RangeTooLargeError,
    format_qualified_range,
    iter_range_coordinates,
    normalise_a1_range,
    parse_answer_ranges,
    parse_qualified_ranges,
    range_bounds,
    sheet_candidates,
)


@pytest.mark.parametrize(
    ("raw", "default", "expected"),
    [
        (
            "OUT CAS'!A2:C1529,'OUT CAS'!E2:G586",
            "OUT CAS",
            (
                QualifiedRange("OUT CAS", "A2:C1529"),
                QualifiedRange("OUT CAS", "E2:G586"),
            ),
        ),
        (
            "'Sheet1!'A1:A50,'Sheet2!'A1:E20",
            None,
            (
                QualifiedRange("Sheet1", "A1:A50"),
                QualifiedRange("Sheet2", "A1:E20"),
            ),
        ),
        (
            "'b2b, sez, de'!A5:V10",
            None,
            (QualifiedRange("b2b, sez, de", "A5:V10"),),
        ),
        (
            "Sheet1!'A1:A14'Sheet2!'A1:E11",
            None,
            (
                QualifiedRange("Sheet1", "A1:A14"),
                QualifiedRange("Sheet2", "A1:E11"),
            ),
        ),
        (
            "sheet1!A1:j24',',ورق1!B1:B11'",
            None,
            (
                QualifiedRange("sheet1", "A1:J24"),
                QualifiedRange("ورق1", "B1:B11"),
            ),
        ),
        ("'A1'!B2", None, (QualifiedRange("A1", "B2"),)),
        ("I12:I13", "Sheet1", (QualifiedRange("Sheet1", "I12:I13"),)),
    ],
)
def test_parse_benchmark_range_dialects(
    raw: str,
    default: str | None,
    expected: tuple[QualifiedRange, ...],
) -> None:
    assert parse_qualified_ranges(raw, default_sheet=default) == expected


def test_answer_ranges_use_first_declared_sheet() -> None:
    assert parse_answer_ranges("A3:E11", "Consolidated Tracker,Existing Task") == (
        QualifiedRange("Consolidated Tracker", "A3:E11"),
    )


def test_sheet_candidate_parser_preserves_a_quoted_comma() -> None:
    assert sheet_candidates("'b2b, sez, de'") == ("b2b, sez, de",)
    assert sheet_candidates("'Sheet1','Sheet2'") == ("Sheet1", "Sheet2")


def test_range_normalisation_matches_evaluator_repair() -> None:
    assert normalise_a1_range("'$BD$2: 308'") == "BD2:BD308"
    assert normalise_a1_range("a:g") == "A:G"
    assert normalise_a1_range("2:10") == "2:10"
    with pytest.raises(RangeSyntaxError):
        normalise_a1_range("A0")
    with pytest.raises(RangeSyntaxError):
        normalise_a1_range("XFE1")
    with pytest.raises(RangeSyntaxError):
        normalise_a1_range("B2:A1")


def test_whole_column_expansion_is_bounded_by_sheet_dimension() -> None:
    assert range_bounds("B:D", max_row=3) == (2, 1, 4, 3)
    assert list(iter_range_coordinates("B:C", max_row=2)) == ["B1", "C1", "B2", "C2"]
    with pytest.raises(RangeSyntaxError):
        list(iter_range_coordinates("B:C"))
    with pytest.raises(RangeTooLargeError):
        list(iter_range_coordinates("A1:C3", max_cells=8))


def test_qualified_range_format_quotes_only_when_needed() -> None:
    assert format_qualified_range(QualifiedRange("Sheet1", "A1")) == "Sheet1!A1"
    assert format_qualified_range(QualifiedRange("O'Brien Data", "A1")) == "'O''Brien Data'!A1"
