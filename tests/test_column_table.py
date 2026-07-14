import pytest

from talika import ColumnTable, TableError, field, id_field


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)
    headline = field("Headline*", required=True)
    category = field("Category")


def test_parses_columns_and_preserves_ids():
    items = ContentTable.parse(
        [
            ["IDs", "1", "2"],
            ["Type*", "Article", "Poll"],
            ["Headline*", "Hello", "QA Poll"],
            ["Category", "Markets", ""],
        ]
    )

    assert [item.id for item in items] == ["1", "2"]
    assert items[0].content_type == "Article"
    assert items[1].category == ""


def test_missing_optional_row_is_none():
    items = ContentTable.parse(
        [
            ["IDs", "1"],
            ["Type*", "Article"],
            ["Headline*", "Hello"],
        ]
    )

    assert items[0].category is None


def test_missing_required_row_is_rejected_with_item_id():
    with pytest.raises(TableError, match="Required field is missing") as error:
        ContentTable.parse([["IDs", "1"], ["Type*", "Article"]])

    message = str(error.value)
    assert "field='Headline*'" in message
    assert "item_id='1'" in message


def test_missing_required_row_is_rejected_without_item_columns():
    with pytest.raises(TableError, match="Required field is missing"):
        ContentTable.parse([["IDs"], ["Type*"]])


def test_empty_required_cell_has_column_location_and_item_id():
    with pytest.raises(TableError, match="empty value") as error:
        ContentTable.parse(
            [
                ["IDs", "1", "2"],
                ["Type*", "Article", "Poll"],
                ["Headline*", "Hello", ""],
            ]
        )

    message = str(error.value)
    assert "row=3" in message
    assert "column=3" in message
    assert "item_id='2'" in message


def test_first_row_must_be_the_id_row():
    with pytest.raises(TableError, match="first row"):
        ContentTable.parse(
            [
                ["Type*", "Article"],
                ["IDs", "1"],
                ["Headline*", "Hello"],
            ]
        )


def test_duplicate_ids_are_rejected():
    with pytest.raises(TableError, match="Duplicate item ID"):
        ContentTable.parse(
            [
                ["IDs", "1", "1"],
                ["Type*", "Article", "Poll"],
                ["Headline*", "Hello", "Poll"],
            ]
        )


def test_duplicate_ids_are_checked_after_parsing():
    class TypedIds(ColumnTable):
        id = id_field("IDs", parser=lambda value, context: int(value))

    with pytest.raises(TableError) as captured:
        TypedIds.parse([["IDs", "1", "01"]])

    assert captured.value.code == "duplicate_id"
    assert captured.value.item_id == 1
