import pytest

from talika import RowTable, TableCell, TableData, TableError, field


def test_from_rows_records_one_based_source_locations():
    table = TableData.from_rows(
        [
            ["name", "status"],
            ["Alice", "active"],
        ]
    )

    cell = table.cell(2, 2)

    assert cell.value == "active"
    assert cell.source_row == 2
    assert cell.source_column == 2
    assert cell.source_value == "active"


def test_with_value_preserves_the_original_source():
    source = TableCell.from_value("3:Article", row=2, column=2)

    transformed = source.with_value("Article")

    assert transformed.value == "Article"
    assert transformed.source_row == 2
    assert transformed.source_column == 2
    assert transformed.source_value == "3:Article"


def test_from_cells_and_to_rows_use_current_values():
    source = TableCell.from_value("2:Article", row=2, column=2)
    table = TableData.from_cells(
        [
            [
                TableCell.from_value("Type", row=2, column=1),
                source.with_value("Article"),
            ],
        ]
    )

    assert table.to_rows() == [["Type", "Article"]]


def test_cell_indexes_are_one_based_and_checked():
    table = TableData.from_rows([["value"]])

    with pytest.raises(IndexError, match="start at 1"):
        table.cell(0, 1)
    with pytest.raises(IndexError, match="row 2, column 1"):
        table.cell(2, 1)


def test_schemas_accept_table_data_directly():
    class UserTable(RowTable):
        name = field("name")

    table = TableData.from_rows([["name"], ["Alice"]])

    assert UserTable.parse(table)[0].name == "Alice"


def test_parser_errors_report_a_transformed_cells_original_source():
    def fail(value, context):
        raise ValueError("not accepted")

    class ContentTable(RowTable):
        content_type = field("type", parser=fail)

    label = TableCell.from_value("type", row=2, column=1)
    source = TableCell.from_value("3:Article", row=2, column=2)
    table = TableData.from_cells(
        [
            [label.with_value("type")],
            [source.with_value("Article")],
        ]
    )

    with pytest.raises(TableError, match="not accepted") as error:
        ContentTable.parse(table)

    message = str(error.value)
    assert "row=2" in message
    assert "column=2" in message
    assert "value='3:Article'" in message


def test_talika_error_can_be_created_from_a_source_cell():
    cell = TableCell.from_value("invalid-range", row=1, column=2)

    error = TableError.from_cell("Invalid range", cell, schema="ContentTable")

    assert error.row == 1
    assert error.column == 2
    assert error.value == "invalid-range"
    assert "schema=ContentTable" in str(error)


@pytest.mark.parametrize(
    "value",
    ["not-a-table", b"bytes", [["label"], [1]], [["label"], "bare-row"]],
)
def test_raw_tables_reject_strings_rows_and_non_string_cells(value):
    with pytest.raises(TypeError):
        TableData.from_rows(value)


def test_schema_wraps_invalid_raw_input_as_a_table_error():
    class UserTable(RowTable):
        name = field("name")

    with pytest.raises(TableError) as captured:
        UserTable.parse(["name", "Alice"])

    assert captured.value.code == "invalid_table_input"
    assert isinstance(captured.value.__cause__, TypeError)


def test_direct_table_data_construction_normalizes_and_validates_rows():
    cell = TableCell.from_value("name", row=1, column=1)
    mutable_row = [cell]

    table = TableData(rows=[mutable_row])
    mutable_row.clear()

    assert table.rows == ((cell,),)
    with pytest.raises(TypeError, match="TableCell"):
        TableData(rows=[["name"]])


@pytest.mark.parametrize(
    ("kwargs", "error_type"),
    [
        ({"value": 1}, TypeError),
        ({"source_value": 1}, TypeError),
        ({"source_row": True}, TypeError),
        ({"source_column": 1.5}, TypeError),
        ({"source_row": 0}, ValueError),
        ({"source_column": -1}, ValueError),
    ],
)
def test_table_cells_validate_values_and_coordinates(kwargs, error_type):
    values = {
        "value": "name",
        "source_row": 1,
        "source_column": 1,
        "source_value": "name",
        **kwargs,
    }

    with pytest.raises(error_type):
        TableCell(**values)
