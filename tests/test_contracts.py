from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from exactsource.contracts import (
    MAX_PLAN_OPERATIONS,
    FillArrayFormula,
    QualifiedRange,
    SetArrayFormula,
    SetFormula,
    SetValue,
    SolvePlan,
    TaskSpec,
    cell_solve_plan_json_schema,
    sheet_solve_plan_json_schema,
    solve_plan_json_schema,
)


def test_task_type_is_read_from_metadata_not_id_shape() -> None:
    task = TaskSpec(
        id="could-change-on-hidden-data",
        instruction_type="Cell-level manipulation",
        instruction="Fill the answer.",
        spreadsheet_path="task",
        init_xlsx=Path("task/init.xlsx"),
        answer_ranges=(QualifiedRange("Sheet1", "B2:B5"),),
    )

    assert task.is_cell_level is True


def test_operation_plan_accepts_a_typed_formula_write() -> None:
    plan = SolvePlan(
        route="operations",
        summary="Fill the requested result.",
        operations=[SetFormula(op="set_formula", sheet="Sheet1", cell="B2", formula="=A2*2")],
    )

    assert plan.operations[0].formula == "=A2*2"


def test_operation_plan_enforces_operation_count_in_contract_and_schema() -> None:
    operations = [
        SetValue(op="set_value", sheet="Sheet1", cell="A1", value=index)
        for index in range(MAX_PLAN_OPERATIONS)
    ]
    plan = SolvePlan(
        route="operations",
        summary="Use the maximum supported operation count.",
        operations=operations,
    )

    assert len(plan.operations) == MAX_PLAN_OPERATIONS
    with pytest.raises(ValidationError, match="at most 128 items"):
        SolvePlan(
            route="operations",
            summary="Exceed the supported operation count.",
            operations=[
                *operations,
                SetValue(op="set_value", sheet="Sheet1", cell="A1", value="extra"),
            ],
        )

    schema = solve_plan_json_schema()
    assert schema["properties"]["operations"]["maxItems"] == MAX_PLAN_OPERATIONS


def test_operation_plan_accepts_strict_typed_array_formula_writes() -> None:
    plan = SolvePlan.model_validate(
        {
            "route": "operations",
            "summary": "Write single-cell and multi-cell array formulae.",
            "operations": [
                {
                    "op": "set_array_formula",
                    "sheet": "Sheet1",
                    "cell": "B2",
                    "formula": "=UNIQUE(A2:A9)",
                },
                {
                    "op": "fill_array_formula",
                    "sheet": "Sheet1",
                    "range": "D2:F4",
                    "formula": "=A2:C4*2",
                },
            ],
        }
    )

    assert isinstance(plan.operations[0], SetArrayFormula)
    assert isinstance(plan.operations[1], FillArrayFormula)
    assert plan.operations[1].range == "D2:F4"


def test_array_formula_operations_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SetArrayFormula.model_validate(
            {
                "op": "set_array_formula",
                "sheet": "Sheet1",
                "cell": "B2",
                "formula": "=A2:A4*2",
                "ref": "B2:B4",
            }
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"route": "operations", "summary": "Empty plan"},
        {
            "route": "operations",
            "summary": "Conflicting plan",
            "operations": [
                {
                    "op": "set_formula",
                    "sheet": "Sheet1",
                    "cell": "B2",
                    "formula": "=A2",
                }
            ],
            "python_code": "def transform(wb):\n    return wb",
        },
        {
            "route": "python",
            "summary": "Missing program",
            "python_code": "   ",
        },
    ],
)
def test_plan_routes_are_mutually_exclusive(payload: dict) -> None:
    with pytest.raises(ValidationError):
        SolvePlan.model_validate(payload)


def test_unknown_plan_fields_fail_closed() -> None:
    with pytest.raises(ValidationError):
        SolvePlan.model_validate(
            {
                "route": "operations",
                "summary": "Attempt to smuggle an option.",
                "operations": [
                    {
                        "op": "set_formula",
                        "sheet": "Sheet1",
                        "cell": "A1",
                        "formula": "=1",
                        "unrecognised": True,
                    }
                ],
            }
        )


def test_provider_schema_requires_nullable_and_defaulted_fields() -> None:
    schema = solve_plan_json_schema()

    assert schema["required"] == ["route", "summary", "operations", "python_code"]
    assert "default" not in schema["properties"]["python_code"]
    assert "include_style" in schema["$defs"]["CopyRange"]["required"]
    assert schema["$defs"]["SetArrayFormula"]["required"] == [
        "op",
        "sheet",
        "cell",
        "formula",
    ]
    assert schema["$defs"]["FillArrayFormula"]["required"] == [
        "op",
        "sheet",
        "range",
        "formula",
    ]


def test_cell_schema_is_a_non_empty_operations_only_subset() -> None:
    schema = cell_solve_plan_json_schema()

    assert schema["properties"]["route"] == {"const": "operations", "type": "string"}
    assert schema["properties"]["operations"]["minItems"] == 1
    assert schema["properties"]["operations"]["maxItems"] == MAX_PLAN_OPERATIONS
    assert "python_code" not in schema["properties"]
    assert schema["required"] == ["route", "summary", "operations"]
    assert schema["additionalProperties"] is False


def test_sheet_schema_encodes_the_same_mutually_exclusive_routes_as_solve_plan() -> None:
    schema = sheet_solve_plan_json_schema()
    operations_route, python_route = schema["oneOf"]

    assert operations_route == {
        "properties": {
            "route": {"const": "operations"},
            "operations": {"minItems": 1},
            "python_code": {"type": "null"},
        },
        "required": ["route", "operations", "python_code"],
    }
    assert python_route == {
        "properties": {
            "route": {"const": "python"},
            "operations": {"maxItems": 0},
            "python_code": {"type": "string", "pattern": r"\S"},
        },
        "required": ["route", "operations", "python_code"],
    }


@pytest.mark.parametrize(
    "schema_factory,payload",
    [
        (
            cell_solve_plan_json_schema,
            {
                "route": "operations",
                "summary": "Write the requested formula.",
                "operations": [
                    {
                        "op": "set_formula",
                        "sheet": "Sheet1",
                        "cell": "B2",
                        "formula": "=A2*2",
                    }
                ],
            },
        ),
        (
            sheet_solve_plan_json_schema,
            {
                "route": "operations",
                "summary": "Write the requested formula.",
                "operations": [
                    {
                        "op": "set_formula",
                        "sheet": "Sheet1",
                        "cell": "B2",
                        "formula": "=A2*2",
                    }
                ],
                "python_code": None,
            },
        ),
        (
            sheet_solve_plan_json_schema,
            {
                "route": "python",
                "summary": "Build the requested report sheet.",
                "operations": [],
                "python_code": "def transform(wb):\n    wb.create_sheet('Report')",
            },
        ),
    ],
)
def test_advertised_route_examples_are_accepted_by_production_solve_plan(
    schema_factory: Callable[[], dict[str, Any]],
    payload: dict[str, object],
) -> None:
    # Building the schema first makes each case explicitly exercise the advertised
    # route. SolvePlan remains the sole production parsing authority.
    schema = schema_factory()
    assert set(schema["required"]).issubset(payload)
    assert set(payload).issubset(schema["properties"])

    if "oneOf" in schema:
        matching_route = [
            branch
            for branch in schema["oneOf"]
            if branch["properties"]["route"]["const"] == payload["route"]
        ]
        assert len(matching_route) == 1
        branch = matching_route[0]
        if payload["route"] == "operations":
            assert len(payload["operations"]) >= branch["properties"]["operations"]["minItems"]
            assert payload["python_code"] is None
        else:
            assert payload["operations"] == []
            assert str(payload["python_code"]).strip()
    else:
        assert payload["route"] == schema["properties"]["route"]["const"]
        assert len(payload["operations"]) >= schema["properties"]["operations"]["minItems"]

    plan = SolvePlan.model_validate(payload)

    assert plan.route == payload["route"]
