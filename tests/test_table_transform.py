import pytest

from talika import (
    ParseContext,
    RowTable,
    TableData,
    TableError,
    field,
)


def test_default_transform_hook_leaves_the_table_unchanged():
    class PlainTable(RowTable):
        value = field("value")

    records = PlainTable.parse([["value"], ["one"]])

    assert records[0].value == "one"


def test_transform_hook_receives_table_data_and_parse_context():
    seen = {}

    class ContextTable(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            seen["table"] = table
            seen["context"] = context
            return table

    ContextTable.parse([["value"], ["one"]], context={"mode": "example"})

    assert isinstance(seen["table"], TableData)
    assert isinstance(seen["context"], ParseContext)
    assert seen["context"].user_data["mode"] == "example"


def test_transform_hook_can_change_values_before_field_parsing():
    class UpperTable(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            rows = [list(row) for row in table.rows]
            rows[1][0] = rows[1][0].with_value(rows[1][0].value.upper())
            return TableData.from_cells(rows)

    assert UpperTable.parse([["value"], ["one"]])[0].value == "ONE"


def test_transform_hook_must_return_table_data():
    class InvalidTable(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            return table.to_rows()

    with pytest.raises(TableError, match="must return TableData"):
        InvalidTable.parse([["value"], ["one"]])


def test_unexpected_transform_error_is_wrapped():
    class BrokenTable(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            raise RuntimeError("transformer unavailable")

    with pytest.raises(TableError, match="transformer unavailable") as error:
        BrokenTable.parse([["value"], ["one"]])

    assert "schema=BrokenTable" in str(error.value)
    assert isinstance(error.value.__cause__, RuntimeError)


def test_intentional_table_error_from_transformer_is_preserved():
    class RangeTable(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            cell = table.cell(2, 1)
            raise TableError.from_cell("Invalid range", cell, schema=cls)

    with pytest.raises(TableError, match="Invalid range") as error:
        RangeTable.parse([["value"], ["3..1"]])

    assert error.value.row == 2
    assert error.value.column == 1
    assert error.value.value == "3..1"


def test_parser_error_after_transformation_reports_original_cell():
    seen = {}

    def require_poll(value, context):
        seen["current_value"] = value
        seen["source_value"] = context.source_value
        if value != "Poll":
            raise ValueError("expected Poll")
        return value

    class ExpandedTable(RowTable):
        content_type = field("type", parser=require_poll)

        @classmethod
        def transform_table(cls, table, context):
            source = table.cell(2, 1)
            return TableData.from_cells(
                [
                    [table.cell(1, 1)],
                    [source.with_value("Article")],
                ]
            )

    with pytest.raises(TableError, match="expected Poll") as error:
        ExpandedTable.parse([["type"], ["3:Article"]])

    assert error.value.row == 2
    assert error.value.column == 1
    assert error.value.value == "3:Article"
    assert seen == {
        "current_value": "Article",
        "source_value": "3:Article",
    }
