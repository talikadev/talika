import pytest

from talika import (
    ColumnTable,
    RowTable,
    SchemaDefinitionError,
    TableError,
    field,
    id_field,
)


def test_asterisk_in_label_has_no_implicit_meaning():
    class LiteralLabelTable(RowTable):
        value = field("Value*")

    record = LiteralLabelTable.parse([["Value*"], [""]])[0]

    assert record.value == ""


def test_column_table_requires_exactly_one_id_field():
    class MissingIdTable(ColumnTable):
        value = field("Value")

    with pytest.raises(TableError, match="exactly one id_field"):
        MissingIdTable.parse([["Value", "one"]])


def test_duplicate_schema_labels_are_rejected():
    with pytest.raises(SchemaDefinitionError, match="already used"):

        class DuplicateSchema(RowTable):
            first = field("value")
            second = field("value")


def test_id_field_can_use_a_custom_parser():
    class NumberedTable(ColumnTable):
        id = id_field("IDs", parser=lambda value, context: int(value))
        value = field("Value")

    assert NumberedTable.parse([["IDs", "7"], ["Value", "seven"]])[0].id == 7


def test_field_empty_policy_preserves_legacy_raw_default():
    class EmptyTable(RowTable):
        value = field("value", parser=lambda value, context: int(value))

    record = EmptyTable.parse([["value"], [""]])[0]

    assert record.value == ""


def test_field_empty_policy_can_parse_blank_cells():
    seen = []

    def parse(value, context):
        seen.append(value)
        return "parsed-blank"

    class EmptyTable(RowTable):
        value = field("value", parser=parse, empty="parse")

    record = EmptyTable.parse([["value"], [""]])[0]

    assert record.value == "parsed-blank"
    assert seen == [""]


def test_field_empty_policy_can_convert_blank_cells_to_none():
    class EmptyTable(RowTable):
        value = field("value", empty="none")

    record = EmptyTable.parse([["value"], [""]])[0]

    assert record.value is None


def test_field_empty_policy_can_reject_optional_blank_cells():
    class EmptyTable(RowTable):
        value = field("value", empty="error")

    with pytest.raises(TableError, match="empty value") as error:
        EmptyTable.parse([["value"], [""]])

    assert error.value.code == "empty_optional"
    assert error.value.field == "value"


def test_field_empty_policy_rejects_unknown_policy():
    with pytest.raises(ValueError, match="empty must be"):
        field("value", empty="sometimes")
