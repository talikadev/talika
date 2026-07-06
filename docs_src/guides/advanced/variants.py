# --8<-- [start:feature-content]
Feature: CMS content variants

  Scenario: Parse articles and polls from one table
    Given the content items:
      | IDs      | A-1          | P-1             |
      | Type     | Article      | Poll            |
      | Headline | Market brief | Reader question |
      | Body     | Full text    |                 |
      | Options  |              | Yes, No         |
    Then each item uses the fields for its content type
# --8<-- [end:feature-content]

# --8<-- [start:declarative-schema]
from dataclasses import dataclass

from talika import (
    ColumnTable,
    RowTable,
    TableFields,
    discriminator,
    discriminator_field,
    field,
    id_field,
    integer,
    split,
)


class ArticleFields(TableFields):
    body = field("Body", required=True)


class PollFields(TableFields):
    options = field("Options", required=True, parser=split(","))


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = discriminator(
        "Type",
        variants={"Article": ArticleFields, "Poll": PollFields},
    )
    headline = field("Headline", required=True)
# --8<-- [end:declarative-schema]

# --8<-- [start:content-table]
content_table = [
    ["IDs", "A-1", "P-1"],
    ["Type", "Article", "Poll"],
    ["Headline", "Market brief", "Reader question"],
    ["Body", "Full text", ""],
    ["Options", "", "Yes, No"],
]
# --8<-- [end:content-table]

# --8<-- [start:declarative-parse]
article, poll = ContentTable.parse(content_table)

assert isinstance(article, ContentTable)
assert isinstance(article, ArticleFields)
assert article.body == "Full text"

assert isinstance(poll, ContentTable)
assert isinstance(poll, PollFields)
assert poll.options == ["Yes", "No"]
# --8<-- [end:declarative-parse]

# --8<-- [start:declarative-output]
>> article.id
'A-1'

>> article.content_type
'Article'

>> article.body
'Full text'

>> poll.options
['Yes', 'No']
# --8<-- [end:declarative-output]

# --8<-- [start:variant-for]
article_schema = ContentTable.variant_for("Article")
poll_schema = ContentTable.variant_for("Poll")

assert isinstance(article, article_schema)
assert isinstance(poll, poll_schema)
# --8<-- [end:variant-for]

# --8<-- [start:explicit-schema]
class ExplicitContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = discriminator_field("Type")
    headline = field("Headline", required=True)


@ExplicitContentTable.variant("Article")
class ArticleContent(ExplicitContentTable):
    body = field("Body", required=True)


@ExplicitContentTable.variant("Video")
class VideoContent(ExplicitContentTable):
    url = field("URL", required=True)
# --8<-- [end:explicit-schema]

# --8<-- [start:explicit-parse]
article, video = ExplicitContentTable.parse(
    [
        ["IDs", "A-1", "V-1"],
        ["Type", "Article", "Video"],
        ["Headline", "Market brief", "Launch clip"],
        ["Body", "Full text", ""],
        ["URL", "", "/launch-video"],
    ]
)
# --8<-- [end:explicit-parse]

# --8<-- [start:explicit-output]
>> type(article).__name__
'ArticleContent'

>> article.body
'Full text'

>> type(video).__name__
'VideoContent'

>> video.url
'/launch-video'
# --8<-- [end:explicit-output]

# --8<-- [start:unknown-variant]
ContentTable.parse(
    [
        ["IDs", "X-1"],
        ["Type", "Video"],
        ["Headline", "Clip"],
        ["Body", ""],
        ["Options", ""],
    ]
)
# --8<-- [end:unknown-variant]

# --8<-- [start:unknown-variant-output]
Unknown variant 'Video'; expected one of: 'Article', 'Poll' (code=unknown_variant, schema=ContentTable, field='Type', row=2, column=2, item_id='X-1', value='Video'). Hint: Use a discriminator value registered on this schema.
# --8<-- [end:unknown-variant-output]

# --8<-- [start:missing-variant-field]
ContentTable.parse(
    [
        ["IDs", "A-1"],
        ["Type", "Article"],
        ["Headline", "Market brief"],
    ]
)
# --8<-- [end:missing-variant-field]

# --8<-- [start:missing-variant-field-output]
Required field is missing from the table (code=missing_required, schema=ContentTable[Article], field='Body', item_id='A-1'). Hint: Add this field to the table, or make the schema field optional if the project should supply it.
# --8<-- [end:missing-variant-field-output]

# --8<-- [start:inapplicable-field]
ContentTable.parse(
    [
        ["IDs", "P-1"],
        ["Type", "Poll"],
        ["Headline", "Reader question"],
        ["Body", "Unexpected article text"],
        ["Options", "Yes, No"],
    ]
)
# --8<-- [end:inapplicable-field]

# --8<-- [start:inapplicable-field-output]
Field does not apply to variant 'Poll' (code=inapplicable_field, schema=ContentTable[Poll], field='Body', row=4, column=2, item_id='P-1', value='Unexpected article text'). Hint: Move this value to a record with the matching variant, leave the cell empty, or change inapplicable_fields policy.
# --8<-- [end:inapplicable-field-output]

# --8<-- [start:parsed-selector]
class NormalizedContentTable(RowTable):
    content_type = discriminator_field(
        "type",
        parser=lambda value, context: value.casefold(),
    )


@NormalizedContentTable.variant("article")
class NormalizedArticle(NormalizedContentTable):
    body = field("body")
# --8<-- [end:parsed-selector]

# --8<-- [start:parsed-selector-output]
>> NormalizedContentTable.parse([["type", "body"], ["ARTICLE", "News"]])
[NormalizedArticle(content_type='article', body='News')]
# --8<-- [end:parsed-selector-output]

# --8<-- [start:variant-output-models]
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


class OutputContentTable(RowTable):
    content_type = discriminator_field("type")
    headline = field("headline", required=True)


@OutputContentTable.variant("Article")
class OutputArticle(OutputContentTable):
    output_model = Article
    body = field("body", required=True)


@OutputContentTable.variant("Poll")
class OutputPoll(OutputContentTable):
    output_model = Poll
    options = field("options", required=True, parser=split(","))
# --8<-- [end:variant-output-models]

# --8<-- [start:variant-output-models-output]
>> OutputContentTable.parse(
...     [
...         ["type", "headline", "body", "options"],
...         ["Article", "News", "Text", ""],
...         ["Poll", "Choose", "", "Yes, No"],
...     ]
... )
[Article(content_type='Article', headline='News', body='Text'), Poll(content_type='Poll', headline='Choose', options=['Yes', 'No'])]
# --8<-- [end:variant-output-models-output]

# --8<-- [start:row-variants]
class PaymentTable(RowTable):
    payment_type = discriminator_field("type")
    amount = field("amount", parser=integer())


@PaymentTable.variant("card")
class CardPayment(PaymentTable):
    last_four = field("last_four", required=True)


@PaymentTable.variant("bank")
class BankPayment(PaymentTable):
    account = field("account", required=True)
# --8<-- [end:row-variants]

# --8<-- [start:row-variants-output]
>> PaymentTable.parse(
...     [
...         ["type", "amount", "last_four", "account"],
...         ["card", "25", "4242", ""],
...         ["bank", "50", "", "QA-001"],
...     ]
... )
[CardPayment(payment_type='card', amount=25, last_four='4242'), BankPayment(payment_type='bank', amount=50, account='QA-001')]
# --8<-- [end:row-variants-output]
