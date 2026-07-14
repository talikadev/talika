import pytest

from talika import (
    ColumnTable,
    SchemaDefinitionError,
    TableError,
    TableErrors,
    TableFields,
    discriminator_field,
    field,
    id_field,
    integer,
    reference,
)


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
    with pytest.raises(SchemaDefinitionError, match="is not declared"):

        class MissingTargetTable(ColumnTable):
            id = id_field("IDs")
            parent = reference("Parent", target="slug")

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


@pytest.mark.parametrize(
    "factory",
    [
        lambda: reference("Parent", target=1),
        lambda: reference("Parent", target=""),
        lambda: reference("Parent", separator=1),
    ],
)
def test_reference_options_are_validated_immediately(factory):
    with pytest.raises((TypeError, ValueError)):
        factory()


def test_references_use_the_target_fields_parser_for_typed_ids():
    class TypedContentTable(ColumnTable):
        id = id_field("IDs", parser=integer())
        parent = reference("Parent")

    items = TypedContentTable.parse([["IDs", "1", "2"], ["Parent", "", "1"]])

    assert items[0].id == 1
    assert items[1].parent is items[0]


def test_collect_mode_reports_every_reference_key_failure_in_order():
    class TypedReferences(ColumnTable):
        id = id_field("IDs", parser=integer())
        related = reference("Related", many=True)

    with pytest.raises(TableErrors) as captured:
        TypedReferences.parse(
            [["IDs", "1", "2"], ["Related", "bad, 99", "98, also-bad"]],
            error_mode="collect",
        )

    assert [error.code for error in captured.value] == ["reference_failed"] * 4
    assert [error.column for error in captured.value] == [2, 2, 3, 3]
    assert "conversion failed" in captured.value.errors[0].message
    assert "99" in captured.value.errors[1].message
    assert "98" in captured.value.errors[2].message
    assert "conversion failed" in captured.value.errors[3].message


def test_many_reference_assignment_is_atomic_when_any_key_fails():
    created = []

    class AtomicReferences(ColumnTable):
        id = id_field("IDs", parser=integer())
        related = reference("Related", many=True)

        @classmethod
        def _record_from_values(cls, *args, **kwargs):
            record = super()._record_from_values(*args, **kwargs)
            created.append(record)
            return record

    with pytest.raises(TableErrors):
        AtomicReferences.parse(
            [["IDs", "1", "2"], ["Related", "", "1, bad, 99"]],
            error_mode="collect",
        )

    assert created[1].related == "1, bad, 99"


def test_reference_errors_skip_dependent_validation_and_output():
    events = []

    class DependentTable(ColumnTable):
        id = id_field("IDs")
        parent = reference("Parent")

        def validate_record(self, context):
            events.append("record")

        @classmethod
        def validate_records(cls, records, context):
            events.append("table")

        @classmethod
        def build_output(cls, record, context):
            events.append("output")
            return record

    with pytest.raises(TableErrors):
        DependentTable.parse(
            [["IDs", "1", "2"], ["Parent", "99", "98"]],
            error_mode="collect",
        )

    assert events == []


def test_unhashable_reference_targets_are_controlled_errors():
    class UnhashableTargets(ColumnTable):
        id = id_field("IDs")
        key = field("Key", parser=lambda value, context: [value])
        parent = reference("Parent", target="key")

    with pytest.raises(TableError) as captured:
        UnhashableTargets.parse([["IDs", "1"], ["Key", "one"], ["Parent", ""]])

    assert captured.value.code == "reference_failed"
    assert "hashable" in captured.value.message


def test_late_variant_reference_targets_are_validated_when_parsing_begins():
    class VariantReferences(ColumnTable):
        id = id_field("IDs")
        kind = discriminator_field("Kind")
        parent = reference("Parent", target="slug")

    with pytest.raises(TableError, match="is not declared"):
        VariantReferences.parse([["IDs", "1"], ["Kind", "article"], ["Parent", ""]])


def test_variant_reference_targets_require_the_same_parser_object():
    class VariantReferences(ColumnTable):
        id = id_field("IDs")
        kind = discriminator_field("Kind")
        parent = reference("Parent", target="slug")

    @VariantReferences.variant("article")
    class Article(VariantReferences):
        slug = field("Slug", parser=lambda value, context: value.lower())

    @VariantReferences.variant("poll")
    class Poll(VariantReferences):
        slug = field("Slug", parser=lambda value, context: value.lower())

    with pytest.raises(TableError, match="ambiguous parsers") as captured:
        VariantReferences.parse(
            [
                ["IDs", "1", "2"],
                ["Kind", "article", "poll"],
                ["Slug", "one", "two"],
                ["Parent", "", "one"],
            ]
        )

    assert "common base" in captured.value.hint


def test_variant_reference_target_can_be_exposed_by_one_selected_variant():
    class VariantReferences(ColumnTable):
        id = id_field("IDs")
        kind = discriminator_field("Kind")
        parent = reference("Parent", target="slug")

    @VariantReferences.variant("article")
    class Article(VariantReferences):
        slug = field("Slug")

    @VariantReferences.variant("folder")
    class Folder(VariantReferences):
        pass

    records = VariantReferences.parse(
        [
            ["IDs", "1", "2"],
            ["Kind", "article", "folder"],
            ["Slug", "root", ""],
            ["Parent", "", "root"],
        ]
    )

    assert records[1].parent is records[0]


def test_reference_components_can_defer_targets_to_a_concrete_schema():
    class ParentFields(TableFields):
        parent = reference("Parent", target="slug")

    class ContentWithParents(ColumnTable, ParentFields):
        id = id_field("IDs")
        slug = field("Slug")

    records = ContentWithParents.parse(
        [["IDs", "1", "2"], ["Slug", "root", "child"], ["Parent", "", "root"]]
    )

    assert records[1].parent is records[0]
