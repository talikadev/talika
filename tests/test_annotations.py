from decimal import Decimal
from enum import Enum
from typing import Literal

import pytest

from talika import (
    RowTable,
    SchemaDefinitionError,
    TableError,
    TableFields,
    discriminator,
    field,
    split,
    string,
)


class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


def test_annotations_infer_supported_scalar_parsers():
    class TypedTable(RowTable):
        count: int = field("count", required=True)
        ratio: float = field("ratio", required=True)
        price: Decimal = field("price", required=True)
        active: bool = field("active", required=True)
        status: Status = field("status", required=True)

    record = TypedTable.parse(
        [
            ["count", "ratio", "price", "active", "status"],
            ["3", "1.5", "12.30", "true", "published"],
        ]
    )[0]

    assert record.count == 3
    assert record.ratio == 1.5
    assert record.price == Decimal("12.30")
    assert record.active is True
    assert record.status is Status.PUBLISHED


def test_annotations_infer_optional_and_literal_parsers():
    class TypedTable(RowTable):
        age: int | None = field("age", empty="parse")
        state: Literal["draft", "published"] = field("state", required=True)

    records = TypedTable.parse(
        [
            ["age", "state"],
            ["", "draft"],
            ["30", "published"],
        ]
    )

    assert records[0].age is None
    assert records[1].age == 30


def test_unsupported_annotations_require_an_explicit_parser():
    with pytest.raises(SchemaDefinitionError, match="has no parser"):

        class InvalidTable(RowTable):
            tags: list[str] = field("tags", required=True)

    class ParsedTable(RowTable):
        tags: list[str] = field("tags", required=True, parser=split(","))

    assert ParsedTable.parse([["tags"], ["news, featured"]])[0].tags == [
        "news",
        "featured",
    ]


def test_explicit_parser_takes_precedence_over_annotation():
    class TypedTable(RowTable):
        count: int = field("count", required=True, parser=string(upper=True))

    assert TypedTable.parse([["count"], ["many"]])[0].count == "MANY"


def test_unsupported_annotations_reject_implicit_raw_text():
    class CustomType:
        pass

    with pytest.raises(SchemaDefinitionError, match="does not accept raw str"):

        class TypedTable(RowTable):
            value: CustomType = field("value", required=True)


def test_inferred_parser_errors_keep_cell_location():
    class TypedTable(RowTable):
        count: int = field("count", required=True)

    with pytest.raises(TableError, match="invalid literal") as error:
        TypedTable.parse([["count"], ["many"]])

    assert error.value.row == 2
    assert error.value.column == 1


def test_one_unresolved_annotation_does_not_disable_other_inference():
    class MixedTable(RowTable):
        __annotations__ = {
            "unavailable": "UnavailableDomainType",
            "count": int,
            "active": bool,
        }
        unavailable = field("unavailable")
        count = field("count", required=True)
        active = field("active", required=True)

    record = MixedTable.parse(
        [["unavailable", "count", "active"], ["raw", "3", "true"]]
    )[0]

    assert record.unavailable == "raw"
    assert record.count == 3
    assert record.active is True


def test_inferred_boolean_uses_the_same_strict_default_vocabulary():
    class TypedTable(RowTable):
        active: bool = field("active", required=True)

    with pytest.raises(TableError, match=r"Expected one of \['false', 'true'\]"):
        TypedTable.parse([["active"], ["yes"]])


def test_inherited_annotations_resolve_from_the_declaring_class():
    class BaseTypedRows(RowTable):
        count: int = field("count", required=True)

    class TypedRows(BaseTypedRows):
        name = field("name")

    record = TypedRows.parse([["count", "name"], ["7", "item"]])[0]

    assert record.count == 7


def test_explicit_parser_skips_an_unresolvable_annotation():
    class ExplicitTable(RowTable):
        __annotations__ = {"value": "UnavailableDomainType"}
        value = field("value", parser=lambda value, context: value.upper())

    assert ExplicitTable.parse([["value"], ["kept"]])[0].value == "KEPT"


def test_optional_typed_fields_must_allow_missing_and_empty_outcomes():
    with pytest.raises(SchemaDefinitionError, match="may be missing and become None"):

        class MissingCanBeNone(RowTable):
            age: int = field("age", empty="error")

    with pytest.raises(SchemaDefinitionError, match="empty='raw'"):

        class BlankCanBeText(RowTable):
            age: int | None = field("age")


def test_static_defaults_must_match_resolved_annotations():
    with pytest.raises(SchemaDefinitionError, match="default does not match"):

        class InvalidDefault(RowTable):
            age: int = field("age", default="unknown", empty="error")


def test_default_factories_and_explicit_parsers_are_trusted():
    class TrustedExtensions(RowTable):
        generated: int = field(
            "generated",
            default_factory=lambda context: "project-owned",
            empty="error",
        )
        parsed: int = field(
            "parsed",
            required=True,
            parser=lambda value, context: f"project:{value}",
        )

    record = TrustedExtensions.parse([["parsed"], ["value"]])[0]

    assert record.generated == "project-owned"
    assert record.parsed == "project:value"


def test_strict_annotations_apply_through_components_and_inheritance():
    class SharedFields(TableFields):
        age: int = field(required=True)

    class UserRows(RowTable, SharedFields):
        name = field(required=True)

    record = UserRows.parse([["age", "name"], ["34", "Alice"]])[0]

    assert record.age == 34
    assert UserRows.age.label == "age"


def test_strict_annotations_apply_to_declarative_variants():
    class ArticleFields(TableFields):
        score: int = field(required=True)

    class ContentRows(RowTable):
        kind = discriminator("kind", variants={"article": ArticleFields})

    record = ContentRows.parse([["kind", "score"], ["article", "7"]])[0]

    assert isinstance(record, ArticleFields)
    assert record.score == 7
