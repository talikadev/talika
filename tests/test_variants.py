from dataclasses import dataclass

import pytest

from talika import (
    ColumnTable,
    RowTable,
    TableError,
    TableFields,
    discriminator,
    discriminator_field,
    field,
    id_field,
    reference,
    split,
)


def test_discriminator_mapping_composes_table_field_components():
    class ArticleFields(TableFields):
        body = field("Body", required=True)

    class PollFields(TableFields):
        options: list[str] = field("Options", required=True, parser=split(","))

    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = discriminator(
            "Type",
            variants={"Article": ArticleFields, "Poll": PollFields},
        )
        headline = field("Headline", required=True)

    records = ContentTable.parse(
        [
            ["IDs", "1", "2"],
            ["Type", "Article", "Poll"],
            ["Headline", "News", "Choose"],
            ["Body", "Article body", ""],
            ["Options", "", "Yes, No"],
        ]
    )

    assert isinstance(records[0], ArticleFields)
    assert isinstance(records[0], ContentTable)
    assert records[0].body == "Article body"
    assert isinstance(records[1], PollFields)
    assert records[1].options == ["Yes", "No"]
    assert ContentTable.variant_for("Article") is type(records[0])


def test_discriminator_component_supplies_validation_and_output_model():
    @dataclass(frozen=True)
    class Article:
        content_type: str
        body: str

    class ArticleFields(TableFields):
        output_model = Article
        body = field("body", required=True)

        def validate_record(self, context):
            if len(self.body) < context.user_data["minimum"]:
                raise ValueError("body is too short")

    class ContentTable(RowTable):
        content_type = discriminator(
            "type",
            variants={"Article": ArticleFields},
        )

    with pytest.raises(TableError, match="too short") as error:
        ContentTable.parse(
            [["type", "body"], ["Article", "short"]],
            context={"minimum": 10},
        )

    assert error.value.schema == "ContentTable[Article]"

    records = ContentTable.parse(
        [["type", "body"], ["Article", "A sufficiently long body"]],
        context={"minimum": 10},
    )
    assert records == [Article("Article", "A sufficiently long body")]


def test_discriminator_mapping_uses_parsed_selector_values():
    class ArticleFields(TableFields):
        body = field("body")

    class ContentTable(RowTable):
        content_type = discriminator(
            "type",
            variants={"article": ArticleFields},
            parser=lambda value, context: value.casefold(),
        )

    record = ContentTable.parse([["type", "body"], ["ARTICLE", "News"]])[0]

    assert isinstance(record, ArticleFields)
    assert record.content_type == "article"


def test_discriminator_mapping_rejects_non_components():
    with pytest.raises(TypeError, match="TableFields subclasses"):

        class ContentTable(RowTable):
            content_type = discriminator(
                "type",
                variants={"Article": object},
            )


def test_discriminator_requires_a_nonempty_mapping():
    with pytest.raises(ValueError, match="cannot be empty"):
        discriminator("type", variants={})


def test_column_table_selects_variant_schema_for_each_item():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = discriminator_field("Type*")
        headline = field("Headline*", required=True)

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        body = field("Body*", required=True)

    @ContentTable.variant("Poll")
    class PollContent(ContentTable):
        options: list[str] = field("Options*", required=True, parser=split(","))

    records = ContentTable.parse(
        [
            ["IDs", "1", "2"],
            ["Type*", "Article", "Poll"],
            ["Headline*", "News", "Choose one"],
            ["Body*", "Article body", ""],
            ["Options*", "", "Yes, No"],
        ]
    )

    assert isinstance(records[0], ArticleContent)
    assert records[0].body == "Article body"
    assert not hasattr(records[0], "options")
    assert isinstance(records[1], PollContent)
    assert records[1].options == ["Yes", "No"]
    assert not hasattr(records[1], "body")


def test_row_table_supports_variants():
    class PaymentTable(RowTable):
        payment_type = discriminator_field("type")
        amount: int = field("amount", required=True)

    @PaymentTable.variant("card")
    class CardPayment(PaymentTable):
        last_four = field("last_four", required=True)

    @PaymentTable.variant("bank")
    class BankPayment(PaymentTable):
        account = field("account", required=True)

    records = PaymentTable.parse(
        [
            ["type", "amount", "last_four", "account"],
            ["card", "25", "4242", ""],
            ["bank", "50", "", "QA-001"],
        ]
    )

    assert isinstance(records[0], CardPayment)
    assert records[0].amount == 25
    assert isinstance(records[1], BankPayment)
    assert records[1].account == "QA-001"


def test_discriminator_parser_runs_before_variant_lookup():
    class ContentTable(RowTable):
        content_type = discriminator_field(
            "type", parser=lambda value, context: value.casefold()
        )

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        body = field("body")

    record = ContentTable.parse([["type", "body"], ["ARTICLE", "Hello"]])[0]

    assert isinstance(record, ArticleContent)
    assert record.content_type == "article"


def test_unknown_variant_reports_discriminator_cell():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = discriminator_field("Type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(TableError, match="Unknown variant") as error:
        ContentTable.parse([["IDs", "7"], ["Type", "Video"]])

    assert error.value.schema == "ContentTable"
    assert error.value.field == "Type"
    assert error.value.row == 2
    assert error.value.column == 2
    assert error.value.item_id == "7"
    assert error.value.value == "Video"


def test_row_unknown_variant_reports_preparsed_item_id():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")
        item = id_field("id")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(TableError, match="Unknown variant") as error:
        ContentTable.parse([["type", "id"], ["Video", "row-7"]])

    assert error.value.item_id == "row-7"


def test_required_variant_field_is_checked_only_for_selected_variant():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = discriminator_field("Type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        body = field("Body", required=True)

    @ContentTable.variant("Poll")
    class PollContent(ContentTable):
        question = field("Question", required=True)

    poll = ContentTable.parse([["IDs", "1"], ["Type", "Poll"], ["Question", "Ready?"]])[
        0
    ]
    assert isinstance(poll, PollContent)

    with pytest.raises(TableError, match="Required field is missing") as error:
        ContentTable.parse([["IDs", "1"], ["Type", "Article"]])

    assert error.value.schema == "ArticleContent"
    assert error.value.field == "Body"


def test_nonempty_field_for_another_variant_is_rejected():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        body = field("body")

    @ContentTable.variant("Poll")
    class PollContent(ContentTable):
        options = field("options")

    with pytest.raises(TableError, match="does not apply") as error:
        ContentTable.parse(
            [["type", "body", "options"], ["Poll", "unexpected", "Yes,No"]]
        )

    assert error.value.schema == "PollContent"
    assert error.value.field == "body"
    assert error.value.row == 2
    assert error.value.column == 2


def test_variant_validation_uses_selected_schema_and_context():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        body = field("body", required=True)

        def validate_record(self, context):
            if len(self.body) < context.user_data["minimum_body_length"]:
                raise ValueError("Article body is too short")

    with pytest.raises(TableError, match="too short") as error:
        ContentTable.parse(
            [["type", "body"], ["Article", "short"]],
            context={"minimum_body_length": 10},
        )

    assert error.value.schema == "ArticleContent"
    assert error.value.row == 2


def test_each_variant_can_construct_its_own_output_model():
    @dataclass(frozen=True)
    class Article:
        content_type: str
        headline: str
        body: str

    @dataclass(frozen=True)
    class Poll:
        content_type: str
        headline: str
        options: list[str]

    class ContentTable(RowTable):
        content_type = discriminator_field("type")
        headline = field("headline", required=True)

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        output_model = Article
        body = field("body", required=True)

    @ContentTable.variant("Poll")
    class PollContent(ContentTable):
        output_model = Poll
        options: list[str] = field("options", required=True, parser=split(","))

    items = ContentTable.parse(
        [
            ["type", "headline", "body", "options"],
            ["Article", "News", "Text", ""],
            ["Poll", "Choose", "", "Yes, No"],
        ]
    )

    assert items == [
        Article(content_type="Article", headline="News", body="Text"),
        Poll(content_type="Poll", headline="Choose", options=["Yes", "No"]),
    ]


def test_variant_local_references_resolve_before_validation():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = discriminator_field("Type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        related = reference("Related")

    @ContentTable.variant("Poll")
    class PollContent(ContentTable):
        pass

    records = ContentTable.parse(
        [
            ["IDs", "1", "2"],
            ["Type", "Article", "Poll"],
            ["Related", "2", ""],
        ]
    )

    assert records[0].related is records[1]


def test_registering_variants_requires_one_discriminator_field():
    class ContentTable(RowTable):
        content_type = field("type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(TableError, match="exactly one discriminator_field"):
        ContentTable.parse([["type"], ["Article"]])


def test_duplicate_variant_values_are_rejected_at_registration():
    class ContentTable(RowTable):
        content_type = discriminator_field("type")

    @ContentTable.variant("Article")
    class ArticleContent(ContentTable):
        pass

    with pytest.raises(ValueError, match="already registered"):

        @ContentTable.variant("Article")
        class OtherArticleContent(ContentTable):
            pass
