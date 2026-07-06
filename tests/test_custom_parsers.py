import pytest

from talika import RowTable, TableError, field


def test_parser_receives_cell_location_and_user_context():
    seen = {}

    def parse_value(value, context):
        seen["context"] = context
        return context.user_data["prefix"] + value

    class ParsedTable(RowTable):
        value = field("value", parser=parse_value)

    record = ParsedTable.parse([["value"], ["hello"]], context={"prefix": "parsed:"})[0]

    assert record.value == "parsed:hello"
    assert seen["context"].schema is ParsedTable
    assert seen["context"].field_name == "value"
    assert seen["context"].row == 2
    assert seen["context"].column == 1
    assert seen["context"].source_value == "hello"


def test_parser_failure_is_wrapped_with_cell_details():
    def fail(value, context):
        raise ValueError("not valid")

    class ParsedTable(RowTable):
        value = field("value", parser=fail)

    with pytest.raises(TableError, match="Field parser failed") as error:
        ParsedTable.parse([["value"], ["bad"]])

    message = str(error.value)
    assert "field='value'" in message
    assert "row=2" in message
    assert "column=1" in message
    assert "value='bad'" in message


def test_explicit_empty_optional_cell_is_not_sent_to_parser():
    def reject(value, context):
        raise AssertionError("parser should not run")

    class ParsedTable(RowTable):
        value = field("value", parser=reject)

    assert ParsedTable.parse([["value"], [""]])[0].value == ""
