import pytest

from talika import ColumnTable, RowTable, field, id_field


def test_row_records_expose_read_only_field_sources():
    class UserTable(RowTable):
        name = field("name")
        role = field("role")

    user = UserTable.parse([["name", "role"], ["Alice", "admin"]])[0]

    assert user.table_source.row == 2
    assert user.table_source.column is None
    assert user.source_for("role").source_value == "admin"
    assert user.source_for("role").source_column == 2
    with pytest.raises(TypeError):
        user.table_source.cells["role"] = None


def test_column_records_expose_item_and_transformed_sources():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        headline = field("Headline")

    item = ContentTable.parse([["IDs", "1"], ["Headline", "News"]])[0]

    assert item.table_source.item_id == "1"
    assert item.table_source.column == 2
    assert item.source_for("id").source_value == "1"
    assert item.source_for("headline").source_row == 2


def test_missing_optional_fields_have_no_source_cell():
    class UserTable(RowTable):
        name = field("name")
        role = field("role")

    user = UserTable.parse([["name"], ["Alice"]])[0]

    with pytest.raises(KeyError, match="No source cell"):
        user.source_for("role")
