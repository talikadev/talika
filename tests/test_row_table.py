import pytest

from talika import RowTable, TableError, field, id_field


class UserTable(RowTable):
    name = field("name", required=True)
    role = field("role", required=True)
    active = field("active", default=True)


def test_parses_rows_into_schema_records():
    users = UserTable.parse(
        [
            ["name", "role", "active"],
            ["Alice", "admin", "yes"],
            ["Bob", "editor", ""],
        ]
    )

    assert users[0].name == "Alice"
    assert users[0].as_dict() == {
        "name": "Alice",
        "role": "admin",
        "active": "yes",
    }
    assert users[1].active == ""
    assert repr(users[0]).startswith("UserTable(name='Alice'")


def test_missing_optional_header_uses_default():
    users = UserTable.parse([["name", "role"], ["Alice", "admin"]])

    assert users[0].active is True


def test_missing_required_header_is_rejected():
    with pytest.raises(TableError, match="Required field is missing") as error:
        UserTable.parse([["name"], ["Alice"]])

    assert "field='role'" in str(error.value)


def test_missing_required_header_is_rejected_without_data_rows():
    with pytest.raises(TableError, match="Required field is missing"):
        UserTable.parse([["name"]])


def test_empty_required_cell_is_rejected():
    with pytest.raises(TableError, match="empty value") as error:
        UserTable.parse([["name", "role"], ["Alice", ""]])

    message = str(error.value)
    assert "row=2" in message
    assert "column=2" in message
    assert "value=''" in message


def test_row_id_field_is_available_before_later_field_parsers():
    seen_item_ids = []

    def parser(value, context):
        seen_item_ids.append(context.item_id)
        raise ValueError("not accepted")

    class OrderedRowTable(RowTable):
        value = field("value", parser=parser)
        item = id_field("id")

    with pytest.raises(TableError, match="not accepted") as error:
        OrderedRowTable.parse([["value", "id"], ["bad", "row-1"]])

    assert seen_item_ids == ["row-1"]
    assert error.value.item_id == "row-1"


def test_row_id_field_reaches_default_factories_and_sources():
    seen_item_ids = []

    def default(context):
        seen_item_ids.append(context.item_id)
        return f"generated-{context.item_id}"

    class DefaultedRowTable(RowTable):
        value = field("value", default_factory=default)
        item = id_field("id")

    record = DefaultedRowTable.parse_records([["id"], ["row-7"]])[0]

    assert record.value == "generated-row-7"
    assert record.table_source.item_id == "row-7"
    assert seen_item_ids == ["row-7"]
