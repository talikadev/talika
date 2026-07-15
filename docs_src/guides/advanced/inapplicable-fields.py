# --8<-- [start:feature-content]
Feature: CMS variant cleanup

  Scenario: A poll row contains an old article-only value
    Given the content items:
      | IDs      | P-1             |
      | Type     | Poll            |
      | Headline | Reader question |
      | Body     | copied note     |
      | Options  | Yes, No         |
    Then the table policy decides whether the Body value is allowed
# --8<-- [end:feature-content]

# --8<-- [start:base-fields]
from talika import (
    ColumnTable,
    RowTable,
    TableFields,
    discriminator,
    field,
    id_field,
    split,
)


class ArticleFields(TableFields):
    body = field("Body", required=True)


class PollFields(TableFields):
    options = field("Options", required=True, parser=split(","))
# --8<-- [end:base-fields]

# --8<-- [start:strict-schema]
class StrictContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = discriminator(
        "Type",
        variants={"Article": ArticleFields, "Poll": PollFields},
    )
    headline = field("Headline", required=True)
# --8<-- [end:strict-schema]

# --8<-- [start:bad-table]
poll_with_body = [
    ["IDs", "P-1"],
    ["Type", "Poll"],
    ["Headline", "Reader question"],
    ["Body", "copied note"],
    ["Options", "Yes, No"],
]
# --8<-- [end:bad-table]

# --8<-- [start:forbid-call]
StrictContentTable.parse(poll_with_body)
# --8<-- [end:forbid-call]

# --8<-- [start:forbid-output]
Field does not apply to variant 'Poll' (code=inapplicable_field, schema=StrictContentTable[Poll], field='Body', row=4, column=2, item_id='P-1', value='copied note'). Hint: Move this value to a record with the matching variant, leave the cell empty, or change inapplicable_fields policy.
# --8<-- [end:forbid-output]

# --8<-- [start:empty-table]
clean_poll = [
    ["IDs", "P-1"],
    ["Type", "Poll"],
    ["Headline", "Reader question"],
    ["Body", ""],
    ["Options", "Yes, No"],
]
# --8<-- [end:empty-table]

# --8<-- [start:empty-output]
>> StrictContentTable.parse(clean_poll)
[StrictContentTablePollFieldsVariant(options=['Yes', 'No'], id='P-1', content_type='Poll', headline='Reader question')]
# --8<-- [end:empty-output]

# --8<-- [start:preserve-schema]
class PreserveContentTable(ColumnTable):
    inapplicable_fields = "preserve"

    id = id_field("IDs")
    content_type = discriminator(
        "Type",
        variants={"Article": ArticleFields, "Poll": PollFields},
    )
    headline = field("Headline", required=True)
# --8<-- [end:preserve-schema]

# --8<-- [start:preserve-call]
poll = PreserveContentTable.parse(poll_with_body)[0]
# --8<-- [end:preserve-call]

# --8<-- [start:preserve-output]
>> poll
PreserveContentTablePollFieldsVariant(options=['Yes', 'No'], id='P-1', content_type='Poll', headline='Reader question')

>> poll.options
['Yes', 'No']

>> dict(poll.table_extras)
{'Body': 'copied note'}
# --8<-- [end:preserve-output]

# --8<-- [start:as-dict]
>> poll.as_dict()
{'options': ['Yes', 'No'], 'id': 'P-1', 'content_type': 'Poll', 'headline': 'Reader question'}
# --8<-- [end:as-dict]

# --8<-- [start:readonly-extras]
poll.table_extras["Body"] = "changed"
# --8<-- [end:readonly-extras]

# --8<-- [start:readonly-extras-output]
TypeError: 'mappingproxy' object does not support item assignment
# --8<-- [end:readonly-extras-output]

# --8<-- [start:empty-extras-output]
>> clean = PreserveContentTable.parse(clean_poll)[0]
>> dict(clean.table_extras)
{}
# --8<-- [end:empty-extras-output]

# --8<-- [start:alias-schema]
class AliasArticleFields(TableFields):
    body = field("Body", aliases=("Article body",))


class AliasPollFields(TableFields):
    options = field("Options")


class AliasContentTable(RowTable):
    inapplicable_fields = "preserve"
    kind = discriminator(
        "type",
        variants={"Article": AliasArticleFields, "Poll": AliasPollFields},
    )
# --8<-- [end:alias-schema]

# --8<-- [start:alias-output]
>> poll = AliasContentTable.parse(
...     [["type", "Article body", "Options"], ["Poll", "legacy", "Yes, No"]]
... )[0]
>> dict(poll.table_extras)
{'Article body': 'legacy'}
# --8<-- [end:alias-output]

# --8<-- [start:invalid-policy]
class InvalidTable(RowTable):
    inapplicable_fields = "ignore"
    value = field("value")
# --8<-- [end:invalid-policy]

# --8<-- [start:invalid-policy-output]
inapplicable_fields must be 'forbid' or 'preserve' (schema=InvalidTable)
# --8<-- [end:invalid-policy-output]
