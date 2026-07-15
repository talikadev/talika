from __future__ import annotations

import importlib
from types import MappingProxyType

import pytest

from talika import (
    RowTable,
    SchemaDefinitionError,
    TableError,
    TableFields,
    discriminator_field,
    field,
)


def test_schema_has_one_reused_immutable_plan():
    class UserTable(RowTable):
        name = field("name")

    plan = UserTable.__schema_plan__

    UserTable.parse([["name"], ["Alice"]])
    UserTable.parse([["name"], ["Bob"]])

    assert UserTable.__schema_plan__ is plan
    assert isinstance(plan.fields_by_name, MappingProxyType)
    assert isinstance(plan.fields_by_label, MappingProxyType)
    with pytest.raises(TypeError):
        plan.fields_by_name["other"] = plan.fields[0]  # type: ignore[index]


def test_compiled_field_metadata_and_schema_views_are_read_only():
    class UserTable(RowTable):
        name = field("name")

    with pytest.raises(AttributeError, match="frozen"):
        UserTable.name.label = "display name"
    with pytest.raises(TypeError):
        UserTable.__fields__["other"] = field("other")  # type: ignore[index]
    with pytest.raises(TypeError):
        UserTable.__variants__["other"] = UserTable  # type: ignore[index]
    with pytest.raises(AttributeError, match="frozen"):
        UserTable.unknown_fields = "forbid"
    with pytest.raises(AttributeError, match="frozen"):
        UserTable.parse = classmethod(lambda cls, table: [])

    UserTable.application_marker = "allowed"
    assert UserTable.application_marker == "allowed"


def test_subclass_configuration_is_independent_from_frozen_parent():
    class BaseRows(RowTable):
        value = field("value")

    parent_plan = BaseRows.__schema_plan__

    class SpecializedRows(BaseRows):
        value = field("special value")

        @classmethod
        def build_output(cls, record, context):
            return record.value.upper()

    assert BaseRows.__schema_plan__ is parent_plan
    assert BaseRows.value.label == "value"
    assert SpecializedRows.value.label == "special value"
    record = SpecializedRows.parse([["special value"], ["kept"]])[0]
    assert record.value == "kept"
    assert SpecializedRows.parse_as([["special value"], ["kept"]]) == ["KEPT"]


def test_parsed_records_remain_mutable():
    class UserTable(RowTable):
        name = field("name")

    record = UserTable.parse([["name"], ["Alice"]])[0]
    record.name = "Bob"

    assert record.name == "Bob"


@pytest.mark.parametrize(
    "reserved_name",
    [
        "parse",
        "parse_as",
        "describe",
        "variant",
        "variant_for",
        "transform_table",
        "validate_record",
        "validate_records",
        "build_output",
        "table_source",
        "table_extras",
        "source_for",
        "as_dict",
        "table_transformer",
        "output_model",
        "unknown_fields",
        "inapplicable_fields",
        "__fields__",
        "__variants__",
        "__schema_plan__",
    ],
)
def test_fields_cannot_shadow_framework_attributes(reserved_name):
    with pytest.raises(SchemaDefinitionError, match="reserved"):
        type("InvalidRows", (RowTable,), {reserved_name: field(reserved_name)})


def test_removed_parse_records_name_is_available_to_schema_fields():
    class LegacyVocabulary(RowTable):
        parse_records = field()

    record = LegacyVocabulary.parse([["parse_records"], ["project value"]])[0]

    assert record.parse_records == "project value"


def test_non_field_cannot_shadow_an_inherited_field():
    class SharedFields(TableFields):
        value = field("value")

    with pytest.raises(SchemaDefinitionError, match="non-field.*inherited field"):

        class InvalidRows(RowTable, SharedFields):
            value = "not a field"


def test_independent_inherited_fields_with_the_same_name_are_rejected():
    class LeftFields(TableFields):
        value = field("left")

    class RightFields(TableFields):
        value = field("right")

    with pytest.raises(SchemaDefinitionError, match="[Cc]onflicting inherited field"):

        class InvalidRows(RowTable, LeftFields, RightFields):
            pass


def test_explicit_child_field_resolves_an_inherited_name_conflict():
    class LeftFields(TableFields):
        value = field("left")

    class RightFields(TableFields):
        value = field("right")

    class ResolvedRows(RowTable, LeftFields, RightFields):
        value = field("resolved")

    assert list(ResolvedRows.__fields__) == ["value"]
    assert ResolvedRows.parse([["resolved"], ["ok"]])[0].value == "ok"


def test_diamond_inheritance_deduplicates_the_original_field():
    class CommonFields(TableFields):
        common = field("common")

    class LeftFields(CommonFields):
        left = field("left")

    class RightFields(CommonFields):
        right = field("right")

    class CombinedRows(RowTable, LeftFields, RightFields):
        own = field("own")

    assert list(CombinedRows.__fields__) == ["common", "left", "right", "own"]


def test_bound_field_instance_cannot_be_reused_by_an_unrelated_schema():
    shared = field("shared")

    class FirstRows(RowTable):
        value = shared

    assert FirstRows.value is shared

    with pytest.raises(SchemaDefinitionError, match="already bound"):

        class SecondRows(RowTable):
            value = shared


def test_describe_does_not_seal_explicit_variant_registration():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    initial_plan = ContentTable.__schema_plan__
    ContentTable.describe()

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        body = field("body")

    registered_plan = ContentTable.__schema_plan__
    assert registered_plan is not initial_plan
    assert not initial_plan.variants
    assert registered_plan.variants["article"].schema_type is ArticleContent
    assert ContentTable.variant_for("article") is ArticleContent


def test_successful_schema_finalization_seals_variant_registration():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        body = field("body")

    plan_before_parse = ContentTable.__schema_plan__
    ContentTable.parse([["type", "body"], ["article", "News"]])

    assert ContentTable.__schema_plan__ is plan_before_parse
    with pytest.raises(SchemaDefinitionError, match="sealed"):

        @ContentTable.variant("poll")
        class PollContent(ContentTable):
            question = field("question")


def test_invalid_family_finalization_does_not_seal_registration():
    class ContentTable(RowTable):
        content_type = field("type")

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(SchemaDefinitionError, match="exactly one discriminator"):
        ContentTable.parse([["type"], ["article"]])

    @ContentTable.variant("poll")
    class PollContent(ContentTable):
        pass

    assert ContentTable.variant_for("poll") is PollContent


def test_invalid_table_input_still_seals_a_valid_schema_family():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(TableError, match="Invalid table input"):
        ContentTable.parse("not a table")

    with pytest.raises(SchemaDefinitionError, match="sealed"):

        @ContentTable.variant("poll")
        class PollContent(ContentTable):
            pass


def test_compiler_rejects_invalid_configured_hooks():
    with pytest.raises(SchemaDefinitionError, match="table_transformer"):

        class InvalidTransformer(RowTable):
            table_transformer = object()
            value = field("value")

    with pytest.raises(SchemaDefinitionError, match="output_model"):

        class InvalidOutput(RowTable):
            output_model = object()
            value = field("value")

    with pytest.raises(SchemaDefinitionError, match="validate_record"):

        class InvalidValidator(RowTable):
            validate_record = 1
            value = field("value")


def test_internal_architecture_modules_import_without_cycles():
    modules = (
        "talika.schema_plan",
        "talika.schema_compiler",
        "talika.engine_types",
        "talika.row_orientation",
        "talika.column_orientation",
        "talika.references",
        "talika.validation",
        "talika.output",
        "talika.engine",
        "talika.schema",
    )

    assert all(importlib.import_module(name) is not None for name in modules)


def test_internal_plan_types_are_not_top_level_exports():
    import talika

    assert not hasattr(talika, "SchemaPlan")
    assert not hasattr(talika, "parse_table_records")
    assert RowTable.__module__ == "talika.schema"

    class UserTable(RowTable):
        name = field("name", empty="none")

    assert not hasattr(UserTable, "parse_records")
    plan = UserTable.__schema_plan__
    assert plan.orientation.value == "row"
    assert plan.policies.unknown_fields.value == "forbid"
    assert plan.fields[0].empty.value == "none"
