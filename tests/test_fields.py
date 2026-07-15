import pytest

from talika import (
    ColumnTable,
    RowTable,
    SchemaDefinitionError,
    TableError,
    TableErrors,
    TableFields,
    field,
    id_field,
)


def test_asterisk_in_label_has_no_implicit_meaning():
    class LiteralLabelTable(RowTable):
        value = field("Value*")

    record = LiteralLabelTable.parse([["Value*"], [""]])[0]

    assert record.value == ""


def test_field_uses_its_attribute_name_when_label_is_omitted():
    class UserTable(RowTable):
        name = field(aliases=("Full name",))

    assert UserTable.name.label == "name"
    assert UserTable.parse([["Full name"], ["Alice"]])[0].name == "Alice"


def test_column_table_requires_exactly_one_id_field():
    with pytest.raises(SchemaDefinitionError, match="exactly one id_field"):

        class MissingIdTable(ColumnTable):
            value = field("Value")

    with pytest.raises(SchemaDefinitionError, match="exactly one id_field"):

        class MultipleIdTable(ColumnTable):
            first = id_field("First")
            second = id_field("Second")


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


def test_row_table_rejects_multiple_id_fields_during_declaration():
    with pytest.raises(SchemaDefinitionError, match="at most one"):

        class MultipleIdRows(RowTable):
            first = id_field("first")
            second = id_field("second")


@pytest.mark.parametrize(
    "factory",
    [
        lambda: field(1),
        lambda: field("value", aliases="alias"),
        lambda: field("value", aliases=(1,)),
        lambda: field("value", parser="parser"),
        lambda: field("value", default_factory="factory"),
        lambda: id_field("id", parser=object()),
    ],
)
def test_invalid_field_declarations_fail_immediately(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_empty_parse_requires_an_inferred_or_explicit_parser():
    with pytest.raises(SchemaDefinitionError, match="empty='parse'"):

        class InvalidRows(RowTable):
            value = field(empty="parse")


def test_required_fields_reject_blank_before_calling_the_parser():
    calls = []

    class RequiredRows(RowTable):
        value = field(
            required=True,
            parser=lambda value, context: calls.append(value) or None,
        )

    with pytest.raises(TableError) as captured:
        RequiredRows.parse([["value"], [""]])

    assert captured.value.code == "empty_required"
    assert calls == []


def test_column_required_fields_also_reject_blank_before_parser():
    calls = []

    class RequiredColumns(ColumnTable):
        id = id_field("IDs")
        value = field(
            required=True,
            parser=lambda value, context: calls.append(value) or None,
        )

    with pytest.raises(TableError) as captured:
        RequiredColumns.parse([["IDs", "one"], ["value", ""]])

    assert captured.value.code == "empty_required"
    assert calls == []


def test_column_optional_empty_policies_match_row_policies():
    class OptionalColumns(ColumnTable):
        id = id_field("IDs")
        raw = field(parser=lambda value, context: int(value))
        none = field(empty="none")
        parsed = field(
            parser=lambda value, context: "parsed-blank",
            empty="parse",
        )

    record = OptionalColumns.parse(
        [["IDs", "one"], ["raw", ""], ["none", ""], ["parsed", ""]]
    )[0]

    assert record.raw == ""
    assert record.none is None
    assert record.parsed == "parsed-blank"


def test_column_optional_empty_error_is_source_aware():
    class OptionalColumns(ColumnTable):
        id = id_field("IDs")
        value = field(empty="error")

    with pytest.raises(TableError) as captured:
        OptionalColumns.parse([["IDs", "one"], ["value", ""]])

    assert captured.value.code == "empty_optional"
    assert (captured.value.row, captured.value.column) == (2, 2)


@pytest.mark.parametrize("empty", ["raw", "none", "parse"])
def test_required_fields_reject_contradictory_empty_policies(empty):
    with pytest.raises(ValueError, match="required fields"):
        field(required=True, empty=empty)


@pytest.mark.parametrize("default", [[], {}, set()])
def test_mutable_or_unhashable_static_defaults_are_rejected(default):
    with pytest.raises(TypeError, match="default_factory"):
        field("value", default=default)


def test_default_factories_create_fresh_final_values():
    class Defaults(RowTable):
        name = field("name")
        values = field("values", default_factory=lambda context: [])
        number = field("number", default="5", parser=lambda value, context: int(value))

    records = Defaults.parse([["name"], ["one"], ["two"]])

    assert records[0].values == records[1].values == []
    assert records[0].values is not records[1].values
    assert records[0].number == "5"


def test_table_fields_support_incomplete_reusable_declarations():
    class SharedFields(TableFields):
        value = field("Value")

    class CompleteColumns(ColumnTable, SharedFields):
        id = id_field("IDs")

    assert CompleteColumns.parse([["IDs", "1"], ["Value", "one"]])[0].value == "one"


@pytest.mark.parametrize("orientation", [RowTable, ColumnTable])
def test_unhashable_parsed_ids_are_reported_at_the_source_cell(orientation):
    class InvalidIds(orientation):
        id = id_field("id", parser=lambda value, context: [value])

    table = [["id"], ["one"]] if orientation is RowTable else [["id", "one"]]
    with pytest.raises(TableError) as captured:
        InvalidIds.parse(table)

    assert captured.value.code == "invalid_id"
    assert captured.value.row == (2 if orientation is RowTable else 1)
    assert captured.value.column == (1 if orientation is RowTable else 2)


def test_typed_duplicate_row_ids_are_rejected_and_duplicate_rows_are_skipped():
    parsed_values = []

    def parse_value(value, context):
        parsed_values.append(value)
        return value

    class IdentifiedRows(RowTable):
        id = id_field("id", parser=lambda value, context: int(value))
        value = field("value", parser=parse_value)

    with pytest.raises(TableErrors) as captured:
        IdentifiedRows.parse(
            [["id", "value"], ["1", "first"], ["01", "duplicate"]],
            error_mode="collect",
        )

    assert [error.code for error in captured.value] == ["duplicate_id"]
    assert parsed_values == ["first"]


def test_collect_mode_reports_each_unhashable_id_and_skips_the_records():
    parsed_values = []

    class InvalidRows(RowTable):
        id = id_field("id", parser=lambda value, context: [value])
        value = field(
            "value",
            parser=lambda value, context: parsed_values.append(value) or value,
        )

    with pytest.raises(TableErrors) as captured:
        InvalidRows.parse(
            [["id", "value"], ["one", "first"], ["two", "second"]],
            error_mode="collect",
        )

    assert [error.code for error in captured.value] == ["invalid_id", "invalid_id"]
    assert parsed_values == []
