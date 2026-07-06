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
