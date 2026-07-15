from talika import RowTable, TableFields, boolean, discriminator, field


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


def test_describe_exposes_the_effective_boolean_contract():
    class FeatureFlags(RowTable):
        enabled = field("enabled", parser=boolean())
        visible = field(
            "visible",
            parser=boolean(
                true_values=("enabled", "yes"),
                false_values=("disabled", "no"),
                case_sensitive=True,
            ),
        )
        inferred: bool = field("inferred", required=True)

    contract = FeatureFlags.describe()

    assert contract.fields[0].parser == (
        "boolean(true_values=('true',), false_values=('false',), case_sensitive=False)"
    )
    assert contract.fields[1].parser == (
        "boolean(true_values=('enabled', 'yes'), "
        "false_values=('disabled', 'no'), case_sensitive=True)"
    )
    assert contract.fields[2].parser == contract.fields[0].parser
    assert contract.as_dict()["fields"][0]["parser"] == contract.fields[0].parser


def test_describe_exposes_resolved_labels_and_effective_empty_policies():
    class Users(RowTable):
        name = field(required=True)
        note = field()

    contract = Users.describe()

    assert [(item.label, item.empty) for item in contract.fields] == [
        ("name", "error"),
        ("note", "raw"),
    ]
