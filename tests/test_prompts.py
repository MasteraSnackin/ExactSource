import json
from pathlib import Path

from exactsource.contracts import QualifiedRange, TaskSpec
from exactsource.prompts import (
    CELL_PROMPT_PLAN_SCHEMA,
    CELL_PROMPT_PLAN_SCHEMA_TEXT,
    CELL_SYSTEM_PROMPT,
    PROMPT_PLAN_SCHEMA,
    PROMPT_PLAN_SCHEMA_TEXT,
    SHEET_PROMPT_PLAN_SCHEMA,
    SHEET_PROMPT_PLAN_SCHEMA_TEXT,
    SYSTEM_PROMPT,
    system_prompt_for,
)


def _task(instruction_type: str) -> TaskSpec:
    return TaskSpec(
        id="prompt-route",
        instruction_type=instruction_type,
        instruction="Complete the declared output.",
        spreadsheet_path="prompt-route",
        init_xlsx=Path("prompt-route/init.xlsx"),
        answer_ranges=(QualifiedRange("Output", "A1:B2"),),
    )


def test_cell_prompt_uses_only_the_operations_schema() -> None:
    assert system_prompt_for(_task("Cell-level manipulation")) == CELL_SYSTEM_PROMPT
    assert CELL_PROMPT_PLAN_SCHEMA["properties"]["route"]["const"] == "operations"
    assert CELL_PROMPT_PLAN_SCHEMA["properties"]["operations"]["minItems"] == 1
    assert "python_code" not in CELL_PROMPT_PLAN_SCHEMA_TEXT
    assert '"route":{"const":"operations"' in CELL_SYSTEM_PROMPT
    assert SHEET_PROMPT_PLAN_SCHEMA_TEXT not in CELL_SYSTEM_PROMPT


def test_sheet_prompt_uses_the_mutually_exclusive_full_schema() -> None:
    assert system_prompt_for(_task("Sheet-level manipulation")) == SYSTEM_PROMPT
    assert len(SHEET_PROMPT_PLAN_SCHEMA["oneOf"]) == 2
    assert '"oneOf"' in SYSTEM_PROMPT
    assert '"pattern":"\\\\S"' in SYSTEM_PROMPT
    assert CELL_PROMPT_PLAN_SCHEMA_TEXT not in SYSTEM_PROMPT


def test_legacy_prompt_schema_names_resolve_to_the_sheet_schema() -> None:
    assert PROMPT_PLAN_SCHEMA is SHEET_PROMPT_PLAN_SCHEMA
    assert PROMPT_PLAN_SCHEMA_TEXT == SHEET_PROMPT_PLAN_SCHEMA_TEXT
    assert json.loads(PROMPT_PLAN_SCHEMA_TEXT) == PROMPT_PLAN_SCHEMA


def test_route_specific_prompt_schemas_remain_compact() -> None:
    for schema in (CELL_PROMPT_PLAN_SCHEMA, SHEET_PROMPT_PLAN_SCHEMA):
        serialised = json.dumps(schema, sort_keys=True)
        assert '"title"' not in serialised
        assert '"mapping"' not in serialised

    # The cell contract omits the entire Python field and its route constraints.
    assert len(CELL_PROMPT_PLAN_SCHEMA_TEXT) < len(SHEET_PROMPT_PLAN_SCHEMA_TEXT)
