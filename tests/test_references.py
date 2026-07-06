import pytest

from talika import ColumnTable, TableError, field, id_field, integer, reference


class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline")
    parent = reference("Parent", target="id")
    related = reference("Related", target="id", many=True)


def test_single_and_many_references_resolve_to_records():
    items = ContentTable.parse(
        [
            ["IDs", "1", "2", "3"],
            ["Headline", "Root", "Child", "Other"],
            ["Parent", "", "1", "1"],
            ["Related", "2, 3", "", "2"],
        ]
    )

    assert items[0].parent is None
    assert items[1].parent is items[0]
    assert items[2].parent is items[0]
    assert items[0].related == [items[1], items[2]]
    assert items[1].related == []


def test_references_are_available_to_record_validation():
    class ValidatedContentTable(ColumnTable):
        id = id_field("IDs")
        parent = reference("Parent")

        def validate_record(self, context):
            if self.parent is self:
                raise TableError.from_cell(
                    "Content cannot reference itself",
                    self.source_for("parent"),
                    schema=type(self),
                )

    with pytest.raises(TableError, match="cannot reference itself"):
        ValidatedContentTable.parse([["IDs", "1"], ["Parent", "1"]])


def test_missing_reference_points_to_the_reference_cell():
    with pytest.raises(TableError, match="was not found") as error:
        ContentTable.parse(
            [
                ["IDs", "1", "2"],
                ["Headline", "Root", "Child"],
                ["Parent", "", "99"],
                ["Related", "", ""],
            ]
        )

    assert error.value.row == 3
    assert error.value.column == 3
    assert error.value.value == "99"
    assert error.value.item_id == "2"


def test_reference_target_must_be_declared_and_unique():
    class MissingTargetTable(ColumnTable):
        id = id_field("IDs")
        parent = reference("Parent", target="slug")

    with pytest.raises(TableError, match="is not declared"):
        MissingTargetTable.parse([["IDs", "1"], ["Parent", ""]])

    class DuplicateTargetTable(ColumnTable):
        id = id_field("IDs")
        slug = field("Slug")
        parent = reference("Parent", target="slug")

    with pytest.raises(TableError, match="is not unique") as error:
        DuplicateTargetTable.parse(
            [
                ["IDs", "1", "2", "3"],
                ["Slug", "same", "same", "child"],
                ["Parent", "", "", "same"],
            ]
        )

    assert error.value.field == "Slug"
    assert error.value.row == 2
    assert error.value.column == 3


def test_reference_separator_cannot_be_empty():
    with pytest.raises(ValueError, match="separator cannot be empty"):
        reference("Related", many=True, separator="")


def test_references_use_the_target_fields_parser_for_typed_ids():
    class TypedContentTable(ColumnTable):
        id = id_field("IDs", parser=integer())
        parent = reference("Parent")

    items = TypedContentTable.parse([["IDs", "1", "2"], ["Parent", "", "1"]])

    assert items[0].id == 1
    assert items[1].parent is items[0]
