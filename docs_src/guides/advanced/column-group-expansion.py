# --8<-- [start:feature]
Feature: CMS grouped content

  Scenario: One compact column describes several content records
    Given the content table:
      | IDs      | 1..3      | 4        |
      | Type     | 3:Article | Poll     |
      | Headline | Shared    | Vote now |
    Then the grouped columns become ordinary content records
# --8<-- [end:feature]

# --8<-- [start:schema]
from talika import (
    ColumnGroupExpander,
    ColumnTable,
    NumericRange,
    ParseContext,
    PrefixRepeat,
    TableData,
    field,
    id_field,
)


class ContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(".."),
        repeat_rule=PrefixRepeat(":"),
    )

    id = id_field("IDs")
    content_type = field("Type")
    headline = field("Headline")


compact_content = [
    ["IDs", "1..3", "4"],
    ["Type", "3:Article", "Poll"],
    ["Headline", "Shared", "Vote now"],
]

items = ContentTable.parse_records(compact_content)
# --8<-- [end:schema]

# --8<-- [start:records-output]
>> [item.as_dict() for item in items]
[
    {'id': '1', 'content_type': 'Article', 'headline': 'Shared'},
    {'id': '2', 'content_type': 'Article', 'headline': 'Shared'},
    {'id': '3', 'content_type': 'Article', 'headline': 'Shared'},
    {'id': '4', 'content_type': 'Poll', 'headline': 'Vote now'},
]
# --8<-- [end:records-output]

# --8<-- [start:expanded-table-output]
>> ContentTable.table_transformer.transform(
...     TableData.from_rows(compact_content),
...     ParseContext(),
...     schema=ContentTable,
... ).to_rows()
[
    ['IDs', '1', '2', '3', '4'],
    ['Type', 'Article', 'Article', 'Article', 'Poll'],
    ['Headline', 'Shared', 'Shared', 'Shared', 'Vote now'],
]
# --8<-- [end:expanded-table-output]

# --8<-- [start:source-output]
>> items[2].source_for("content_type")
TableCell(value='Article', source_row=2, source_column=2, source_value='3:Article')

>> items[1].source_for("headline")
TableCell(value='Shared', source_row=3, source_column=2, source_value='Shared')
# --8<-- [end:source-output]

# --8<-- [start:alphabetic-suffix]
from talika import AlphabeticRange, ColumnGroupExpander, ColumnTable, SuffixRepeat
from talika import field, id_field


class LetterContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        key_row="IDs",
        range_rule=AlphabeticRange("-"),
        repeat_rule=SuffixRepeat(" x"),
    )

    id = id_field("IDs")
    content_type = field("Type")


letter_rows = [
    ["IDs", "A-C"],
    ["Type", "Article x3"],
]

letter_items = LetterContentTable.parse_records(letter_rows)
# --8<-- [end:alphabetic-suffix]

# --8<-- [start:alphabetic-suffix-output]
>> [item.as_dict() for item in letter_items]
[
    {'id': 'A', 'content_type': 'Article'},
    {'id': 'B', 'content_type': 'Article'},
    {'id': 'C', 'content_type': 'Article'},
]
# --8<-- [end:alphabetic-suffix-output]

# --8<-- [start:custom-rules]
from talika import ColumnGroupExpander, ParseContext, TableData


class LabelRange:
    def expand(self, cell, context):
        labels = context.user_data["labels"][cell.value]
        return [cell.with_value(label) for label in labels]


class CopyWithIndex:
    def expand(self, cell, expected_count, context):
        return [
            cell.with_value(f"{cell.value} {index}")
            for index in range(1, expected_count + 1)
        ]


custom_expander = ColumnGroupExpander(
    key_row="Slots",
    range_rule=LabelRange(),
    repeat_rule=CopyWithIndex(),
)

custom_table = TableData.from_rows(
    [
        ["Slots", "launch"],
        ["Headline", "Draft"],
    ]
)
custom_context = ParseContext.from_value(
    {"labels": {"launch": ["hero", "sidebar"]}}
)

custom_result = custom_expander.transform(custom_table, custom_context)
# --8<-- [end:custom-rules]

# --8<-- [start:custom-rules-output]
>> custom_result.to_rows()
[['Slots', 'hero', 'sidebar'], ['Headline', 'Draft 1', 'Draft 2']]
# --8<-- [end:custom-rules-output]

# --8<-- [start:repeat-error]
ContentTable.parse(
    [
        ["IDs", "1..3"],
        ["Type", "2:Article"],
    ]
)
# --8<-- [end:repeat-error]

# --8<-- [start:repeat-error-output]
Repeat expansion failed: Repeat count 2 does not match group size 3 (code=table_error, schema=ContentTable, row=2, column=2, value='2:Article')
# --8<-- [end:repeat-error-output]

# --8<-- [start:key-error-output]
Expected key row 'IDs' (code=table_error, schema=ContentTable, row=1, column=1, value='Keys')
# --8<-- [end:key-error-output]

# --8<-- [start:range-error-output]
Range expansion failed: Numeric range must be ascending (code=table_error, schema=ContentTable, row=1, column=2, value='3..1')
# --8<-- [end:range-error-output]
