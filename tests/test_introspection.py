from talika import RowTable, TableFields, discriminator, field


def test_describe_returns_complete_machine_readable_contract():
    class ArticleFields(TableFields):
        body = field("body", required=True)

    class ContentTable(RowTable):
        inapplicable_fields = "preserve"
        content_type = discriminator(
            "type",
            variants={"Article": ArticleFields},
        )
        headline = field(
            "headline",
            aliases=("title",),
            default_factory=lambda context: "generated",
        )

    contract = ContentTable.describe()

    assert contract.schema_name == "ContentTable"
    assert contract.orientation == "row"
    assert contract.unknown_fields == "forbid"
    assert contract.inapplicable_fields == "preserve"
    headline = next(field for field in contract.fields if field.name == "headline")
    assert headline.aliases == ("title",)
    assert headline.has_default is True
    assert headline.default_factory is not None
    assert contract.variants[0].value == "Article"
    assert contract.variants[0].schema_name == "ContentTable[Article]"
    assert contract.as_dict()["fields"][0]["name"] == "content_type"
