# --8<-- [start:schema]
from talika import RowTable, TableFields, discriminator, field


def split_choices(value, context):
    return [choice.strip() for choice in value.split(",")]


class ArticleFields(TableFields):
    body = field("Body", required=True)


class PollFields(TableFields):
    choices = field("Choices", parser=split_choices)


class ContentTable(RowTable):
    unknown_fields = "forbid"
    inapplicable_fields = "preserve"

    content_type = discriminator(
        "Type",
        variants={
            "Article": ArticleFields,
            "Poll": PollFields,
        },
    )
    headline = field("Headline", aliases=("Title",), required=True)
    status = field("Status", default="draft")
# --8<-- [end:schema]

# --8<-- [start:describe]
contract = ContentTable.describe()
# --8<-- [end:describe]

# --8<-- [start:identity-output]
>> (contract.schema_name, contract.orientation)
('ContentTable', 'row')

>> (contract.unknown_fields, contract.inapplicable_fields)
('forbid', 'preserve')
# --8<-- [end:identity-output]

# --8<-- [start:fields-output]
>> [
...     (field.name, field.label, field.aliases, field.required, field.has_default)
...     for field in contract.fields
... ]
[
    ('content_type', 'Type', (), True, False),
    ('headline', 'Headline', ('Title',), True, False),
    ('status', 'Status', (), False, True),
]
# --8<-- [end:fields-output]

# --8<-- [start:field-dict-output]
>> contract.as_dict()["fields"][1]
{
    'name': 'headline',
    'label': 'Headline',
    'aliases': ('Title',),
    'required': True,
    'is_id': False,
    'is_discriminator': False,
    'has_default': False,
    'default_repr': None,
    'default_factory': None,
    'parser': None,
    'reference_target': None,
    'reference_many': False,
    'empty': 'raw',
}
# --8<-- [end:field-dict-output]

# --8<-- [start:variants-output]
>> [(variant.value, variant.schema_name) for variant in contract.variants]
[('Article', 'ContentTable[Article]'), ('Poll', 'ContentTable[Poll]')]

>> [
...     (variant.value, [field.name for field in variant.fields])
...     for variant in contract.variants
... ]
[
    ('Article', ['body', 'content_type', 'headline', 'status']),
    ('Poll', ['choices', 'content_type', 'headline', 'status']),
]
# --8<-- [end:variants-output]

# --8<-- [start:variant-field-output]
>> contract.as_dict()["variants"][1]["fields"][0]
{
    'name': 'choices',
    'label': 'Choices',
    'aliases': (),
    'required': False,
    'is_id': False,
    'is_discriminator': False,
    'has_default': False,
    'default_repr': None,
    'default_factory': None,
    'parser': 'split_choices',
    'reference_target': None,
    'reference_many': False,
    'empty': 'raw',
}
# --8<-- [end:variant-field-output]

# --8<-- [start:hook-schema]
from dataclasses import dataclass

from talika import ColumnGroupExpander, ColumnTable, NumericRange, PrefixRepeat
from talika import field, id_field


@dataclass
class ContentItem:
    id: str
    headline: str


class GroupedContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        "IDs",
        NumericRange(".."),
        PrefixRepeat(":"),
    )
    output_model = ContentItem

    id = id_field("IDs")
    headline = field("Headline")


hook_contract = GroupedContentTable.describe()
# --8<-- [end:hook-schema]

# --8<-- [start:hook-output]
>> (
...     hook_contract.transformer,
...     hook_contract.output_model,
...     hook_contract.output_builder,
... )
('ColumnGroupExpander', 'ContentItem', 'BaseTable.build_output')
# --8<-- [end:hook-output]

# --8<-- [start:cli-text-command]
$ talika describe app.schemas:ContentTable
# --8<-- [end:cli-text-command]

# --8<-- [start:cli-text-output]
Schema: ContentTable
Orientation: row
Policies: unknown_fields=forbid, inapplicable_fields=preserve
Fields:
  - content_type: label='Type' (required, discriminator)
  - headline: label='Headline', aliases=['Title'] (required)
  - status: label='Status' (default)
Variants:
  - 'Article': ContentTable[Article]
    fields: body, content_type, headline, status
  - 'Poll': ContentTable[Poll]
    fields: choices, content_type, headline, status
# --8<-- [end:cli-text-output]

# --8<-- [start:cli-json-command]
$ talika describe app.schemas:ContentTable --format json
# --8<-- [end:cli-json-command]
