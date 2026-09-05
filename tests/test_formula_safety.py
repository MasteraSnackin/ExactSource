import pytest
from openpyxl import Workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.formula import ArrayFormula
from openpyxl.worksheet.table import Table, TableFormula

from exactsource.formula_safety import (
    FormulaSafetyError,
    snapshot_cell_hyperlinks,
    snapshot_formula_metadata,
    snapshot_formula_texts,
    validate_changed_cell_hyperlinks,
    validate_changed_formula_metadata_safety,
    validate_changed_formula_safety,
    validate_formula_safety,
)


@pytest.mark.parametrize(
    "formula",
    [
        "=SUM(A1:A3)",
        '="WEBSERVICE(""https://example.invalid"")"',
        '="text|not-dde"',
        "=SUM(Sales[Amount])",
        "=SUM(Sales[[#Data],[Amount]])",
        "='WEBSERVICE(archive)'!A1",
        "='Budget | Forecast'!A1",
        '=INDIRECT("A"&1)',
    ],
)
def test_validate_formula_safety_allows_internal_calculations(formula: str) -> None:
    validate_formula_safety(formula)


@pytest.mark.parametrize(
    ("formula", "category"),
    [
        ('=WEBSERVICE("https://private.invalid/path")', "external-capability function"),
        ('=_xlfn.WEBSERVICE("https://private.invalid")', "external-capability function"),
        ('=RTD("server",,A1)', "external-capability function"),
        ('=_xlfn.CALL("library","entry","J")', "external-capability function"),
        ('=REGISTER("library","entry","J")', "external-capability function"),
        ('=REGISTER.ID("library","entry","J")', "external-capability function"),
        ('=EXEC("notepad")', "external-capability function"),
        ('=RUN("MacroName")', "external-capability function"),
        ('=EVALUATE("WEBSERVICE(A1)")', "external-capability function"),
        ("=program|'topic'!A1", "DDE link"),
        ("='program'|'topic'!A1", "DDE link"),
        ("=[book.xlsx]Sheet1!A1", "external workbook link"),
        ("='[book.xlsx]Cash Flow'!$A$1", "external workbook link"),
        ("='C:\\funds\\[book.xlsx]Cash Flow'!$A$1", "external workbook link"),
        ('="file:///private/report.xlsx"', "file or UNC reference"),
        ('="\\\\server\\share\\report.xlsx"', "file or UNC reference"),
        ('=HYPERLINK("#\'Summary\'!A1","Jump")', "hyperlink or image function"),
        ('=HYPERLINK(A1,"Open")', "hyperlink or image function"),
        ("=_xlfn.IMAGE(A1)", "hyperlink or image function"),
        ('=INDIRECT("[book.xlsx]Sheet1!A1")', "external workbook link"),
        (
            '=INDIRECT("["&"book.xlsx"&"]"&"Sheet1"&"!A1")',
            "external workbook link",
        ),
        ('=INDIRECT("["&A1&"]Sheet1!A1")', "external workbook link"),
    ],
)
def test_validate_formula_safety_rejects_external_capabilities_without_echoing_input(
    formula: str,
    category: str,
) -> None:
    with pytest.raises(FormulaSafetyError) as caught:
        validate_formula_safety(formula)

    assert caught.value.category == category
    assert "private.invalid" not in str(caught.value)
    assert "server\\share" not in str(caught.value)


def test_changed_formula_validation_grandfathers_only_unchanged_formulae() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet["A1"] = '=WEBSERVICE("https://legacy.invalid")'
    sheet["A2"] = ArrayFormula(ref="A2", text="=SUM(B2:B3)")
    before = snapshot_formula_texts(workbook)

    assert validate_changed_formula_safety(workbook, before) == 0

    sheet["A2"].value.text = '=WEBSERVICE("https://new.invalid")'
    with pytest.raises(FormulaSafetyError, match="external-capability function"):
        validate_changed_formula_safety(workbook, before)


def test_changed_array_formula_cannot_hide_function_in_discarded_prefix() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = ArrayFormula(ref="A1", text="=SUM(B1:B2)")
    before = snapshot_formula_texts(workbook)

    # openpyxl writes ArrayFormula.text[1:] into the worksheet XML. A malformed
    # leading character must not hide the formula which would actually be saved.
    sheet["A1"].value.text = 'xWEBSERVICE("https://array.invalid")'

    with pytest.raises(FormulaSafetyError, match="external-capability function"):
        validate_changed_formula_safety(workbook, before)


def test_expanding_preexisting_unsafe_array_formula_is_not_grandfathered() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = ArrayFormula(
        ref="A1",
        text='=WEBSERVICE("https://legacy-array.invalid")',
    )
    before = snapshot_formula_texts(workbook)

    sheet["A1"].value.ref = "A1:A10"

    with pytest.raises(FormulaSafetyError, match="external-capability function"):
        validate_changed_formula_safety(workbook, before)


def test_formula_snapshot_does_not_expand_sparse_worksheet_dimensions() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["XFD1048576"] = "=1+1"

    before_cells = len(sheet._cells)
    snapshot = snapshot_formula_texts(workbook)

    assert len(sheet._cells) == before_cells == 1
    assert snapshot == {("Sheet", "XFD1048576"): ("formula", "=1+1")}


def test_moved_preexisting_external_formula_is_not_grandfathered() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"] = '=WEBSERVICE("https://legacy.invalid")'
    before = snapshot_formula_texts(workbook)

    sheet["B1"] = sheet["A1"].value
    sheet["A1"] = None

    with pytest.raises(FormulaSafetyError, match="external-capability function"):
        validate_changed_formula_safety(workbook, before)


def _workbook_with_formula_metadata() -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    sheet.append(["Amount", "Calculated"])
    sheet.append([1, 2])
    sheet.append([3, 4])

    workbook.defined_names.add(DefinedName("SafeName", attr_text="SUM(Sheet1!A2:A3)"))
    table = Table(displayName="CashTable", ref="A1:B3")
    table._initialise_columns()
    table.tableColumns[0].name = "Amount"
    table.tableColumns[1].name = "Calculated"
    table.tableColumns[1].calculatedColumnFormula = TableFormula(attr_text="SUM(CashTable[Amount])")
    table.tableColumns[1].totalsRowFormula = TableFormula(attr_text="SUM(CashTable[Calculated])")
    sheet.add_table(table)

    validation = DataValidation(type="custom", formula1="SUM(A2:A3)>0")
    validation.add("A2:A3")
    sheet.add_data_validation(validation)
    sheet.conditional_formatting.add("A2:A3", FormulaRule(formula=["SUM(A2:A3)>0"]))
    return workbook


@pytest.mark.parametrize(
    "mutate",
    [
        lambda workbook: setattr(
            workbook.defined_names["SafeName"],
            "attr_text",
            'WEBSERVICE("https://name.invalid")',
        ),
        lambda workbook: setattr(
            workbook["Sheet1"].tables["CashTable"].tableColumns[1].calculatedColumnFormula,
            "attr_text",
            'WEBSERVICE("https://table.invalid")',
        ),
        lambda workbook: setattr(
            workbook["Sheet1"].tables["CashTable"].tableColumns[1].totalsRowFormula,
            "attr_text",
            'HYPERLINK("#A1","Jump")',
        ),
        lambda workbook: setattr(
            workbook["Sheet1"].data_validations.dataValidation[0],
            "formula1",
            'INDIRECT("[book.xlsx]Sheet1!A1")',
        ),
        lambda workbook: setattr(
            next(iter(workbook["Sheet1"].conditional_formatting._cf_rules.values()))[0],
            "formula",
            ['WEBSERVICE("https://format.invalid")'],
        ),
    ],
)
def test_changed_formula_metadata_is_checked_without_leaking_content(mutate) -> None:
    workbook = _workbook_with_formula_metadata()
    before = snapshot_formula_metadata(workbook)

    mutate(workbook)

    with pytest.raises(FormulaSafetyError) as caught:
        validate_changed_formula_metadata_safety(workbook, before)
    assert ".invalid" not in str(caught.value)


def test_unchanged_legacy_formula_metadata_is_grandfathered() -> None:
    workbook = _workbook_with_formula_metadata()
    workbook.defined_names["SafeName"].attr_text = 'WEBSERVICE("https://legacy.invalid")'
    table_formula = workbook["Sheet1"].tables["CashTable"].tableColumns[1].calculatedColumnFormula
    table_formula.attr_text = 'WEBSERVICE("https://legacy.invalid")'
    before = snapshot_formula_metadata(workbook)

    assert validate_changed_formula_metadata_safety(workbook, before) == {
        "conditional_formatting": 0,
        "data_validations": 0,
        "defined_names": 0,
        "table_formulae": 0,
    }


@pytest.mark.parametrize("flag", ["xlm", "function", "vbProcedure"])
def test_changed_defined_name_with_executable_flag_is_rejected(flag: str) -> None:
    workbook = _workbook_with_formula_metadata()
    before = snapshot_formula_metadata(workbook)

    setattr(workbook.defined_names["SafeName"], flag, True)

    with pytest.raises(FormulaSafetyError) as caught:
        validate_changed_formula_metadata_safety(workbook, before)
    assert caught.value.category == "executable defined name"


def test_new_external_cell_hyperlink_is_rejected_but_internal_location_is_allowed() -> None:
    workbook = Workbook()
    sheet = workbook.active
    before = snapshot_cell_hyperlinks(workbook)

    sheet["A1"].hyperlink = "https://private.invalid/path"
    with pytest.raises(FormulaSafetyError) as caught:
        validate_changed_cell_hyperlinks(workbook, before)
    assert caught.value.category == "external cell hyperlink"
    assert "private.invalid" not in str(caught.value)

    sheet["A1"].hyperlink = "#'Sheet'!B2"
    assert validate_changed_cell_hyperlinks(workbook, before) == 1


def test_external_hyperlink_location_cannot_hide_behind_internal_target() -> None:
    workbook = Workbook()
    sheet = workbook.active
    before = snapshot_cell_hyperlinks(workbook)
    sheet["A1"].hyperlink = "#Sheet!B2"
    sheet["A1"].hyperlink.location = "https://private.invalid/?payload=secret"

    with pytest.raises(FormulaSafetyError) as caught:
        validate_changed_cell_hyperlinks(workbook, before)

    assert caught.value.category == "external cell hyperlink"
    assert "private.invalid" not in str(caught.value)


def test_unchanged_legacy_external_hyperlink_is_grandfathered() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"].hyperlink = "https://legacy.invalid/path"
    before = snapshot_cell_hyperlinks(workbook)

    sheet["A1"].hyperlink.tooltip = "Updated display metadata"

    assert validate_changed_cell_hyperlinks(workbook, before) == 0


def test_moved_preexisting_external_cell_hyperlink_is_not_grandfathered() -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet["A1"].hyperlink = "https://legacy.invalid/path"
    before = snapshot_cell_hyperlinks(workbook)

    sheet["B1"].hyperlink = sheet["A1"].hyperlink
    sheet["A1"].hyperlink = None

    with pytest.raises(FormulaSafetyError, match="external cell hyperlink"):
        validate_changed_cell_hyperlinks(workbook, before)
