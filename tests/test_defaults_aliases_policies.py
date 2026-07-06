import pytest

from talika import (
    ColumnTable,
    RowTable,
    SchemaDefinitionError,
    TableError,
    TableFields,
    discriminator,
    field,
    id_field,
)


def test_default_factory_receives_item_and_project_context():
    seen = []

    def generated(context):
        seen.append(context)
        return f"generated-{context.item_id}-{context.user_data['suffix']}"

    class ContentTable(ColumnTable):
        id = id_field("IDs")
        headline = field("Headline", default_factory=generated)

    items = ContentTable.parse([["IDs", "7"]], context={"suffix": "qa"})

    assert items[0].headline == "generated-7-qa"
    assert seen[0].field_name == "headline"
    assert seen[0].field_label == "Headline"


def test_default_factory_failure_has_structured_error_code():
    def broken(context):
        raise RuntimeError("generator unavailable")

    class ContentTable(RowTable):
        headline = field("headline", default_factory=broken)

    with pytest.raises(TableError) as error:
        ContentTable.parse([["other"], ["value"]])

    assert error.value.code == "unknown_field"

    class FailingFactoryContentTable(RowTable):
        title = field("title")
        headline = field("headline", default_factory=broken)

    with pytest.raises(TableError, match="generator unavailable") as error:
        FailingFactoryContentTable.parse([["title"], ["other"]])

    assert error.value.code == "default_factory_failed"
    assert isinstance(error.value.__cause__, RuntimeError)


def test_field_aliases_work_in_both_orientations():
    class UserTable(RowTable):
        name = field("name", aliases=("full name",), required=True)

    class ContentTable(ColumnTable):
        id = id_field("IDs", aliases=("Keys",))
        headline = field("Headline", aliases=("Title",))

    assert UserTable.parse([["full name"], ["Alice"]])[0].name == "Alice"
    item = ContentTable.parse([["Keys", "A"], ["Title", "News"]])[0]
    assert item.id == "A"
    assert item.headline == "News"


def test_canonical_label_and_alias_cannot_appear_together():
    class UserTable(RowTable):
        name = field("name", aliases=("full name",))

    with pytest.raises(TableError, match="one of its aliases") as error:
        UserTable.parse([["name", "full name"], ["Alice", "Alice"]])

    assert error.value.code == "duplicate_label"


def test_alias_collisions_are_rejected_when_schema_is_defined():
    with pytest.raises(SchemaDefinitionError, match="already used"):

        class InvalidTable(RowTable):
            name = field("name", aliases=("title",))
            title = field("title")


def test_unknown_field_labels_are_rejected_by_default():
    class UserTable(RowTable):
        name = field("name")

    with pytest.raises(TableError) as error:
        UserTable.parse([["name", "team"], ["Alice", "News"]])

    assert error.value.code == "unknown_field"
    assert error.value.field == "team"


def test_inapplicable_variant_policy_can_preserve_values():
    class ArticleFields(TableFields):
        body = field("body")

    class PollFields(TableFields):
        options = field("options")

    class ContentTable(RowTable):
        inapplicable_fields = "preserve"
        kind = discriminator(
            "type", variants={"Article": ArticleFields, "Poll": PollFields}
        )

    poll = ContentTable.parse(
        [["type", "body", "options"], ["Poll", "legacy", "Yes,No"]]
    )[0]

    assert poll.options == "Yes,No"
    assert poll.table_extras == {"body": "legacy"}


@pytest.mark.parametrize("policy", ["ignore", "preserve", "sometimes"])
def test_unknown_field_policy_only_accepts_forbid(policy):
    with pytest.raises(SchemaDefinitionError, match="unknown_fields.*'forbid'"):

        class InvalidTable(RowTable):
            unknown_fields = policy
            value = field("value")


def test_inapplicable_field_policy_rejects_ignore():
    with pytest.raises(
        SchemaDefinitionError,
        match="inapplicable_fields.*'forbid'.*'preserve'",
    ):

        class InvalidTable(RowTable):
            inapplicable_fields = "ignore"
            value = field("value")


def test_field_rejects_conflicting_default_options():
    with pytest.raises(ValueError, match="both default and default_factory"):
        field("value", default="x", default_factory=lambda context: "y")

    with pytest.raises(ValueError, match="required fields cannot"):
        field("value", required=True, default="x")
