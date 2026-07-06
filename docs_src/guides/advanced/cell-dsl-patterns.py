# --8<-- [start:feature-patterns]
Feature: CMS generated text syntax

  Scenario: Generate headline words from a compact cell
    Given the content items:
      | IDs      | A-1     |
      | Headline | 3 words |
    Then the headline text is generated from the count
# --8<-- [end:feature-patterns]

# --8<-- [start:pattern-dsl]
from talika import CellDSL, ColumnTable, RowTable, field, id_field


content_cells = CellDSL()


@content_cells.pattern(r"(?P<count>\d+) words")
def generated_words(match, context):
    count = int(match["count"])
    return " ".join(
        f"{context.item_id}-{number}"
        for number in range(1, count + 1)
    )
# --8<-- [end:pattern-dsl]

# --8<-- [start:pattern-schema]
class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", required=True, parser=content_cells)
# --8<-- [end:pattern-schema]

# --8<-- [start:pattern-table]
content_table = [
    ["IDs", "A-1"],
    ["Headline", "3 words"],
]
# --8<-- [end:pattern-table]

# --8<-- [start:pattern-output]
>> ContentTable.parse(content_table)[0]
ContentTable(id='A-1', headline='A-1-1 A-1-2 A-1-3')

>> ContentTable.parse(content_table)[0].headline
'A-1-1 A-1-2 A-1-3'
# --8<-- [end:pattern-output]

# --8<-- [start:fullmatch-table]
records = ContentTable.parse(
    [
        ["IDs", "A-1", "A-2", "A-3"],
        ["Headline", "3 words", "prefix 3 words", "3 words please"],
    ]
)
# --8<-- [end:fullmatch-table]

# --8<-- [start:fullmatch-output]
>> [record.headline for record in records]
['A-1-1 A-1-2 A-1-3', 'prefix 3 words', '3 words please']
# --8<-- [end:fullmatch-output]

# --8<-- [start:pattern-order]
priority_cells = CellDSL()


@priority_cells.pattern(r"\d+ words")
def specific(match, context):
    return "specific"


@priority_cells.pattern(r".*")
def catch_all(match, context):
    return "catch-all"


class PriorityTable(RowTable):
    value = field("value", parser=priority_cells)
# --8<-- [end:pattern-order]

# --8<-- [start:pattern-order-output]
>> PriorityTable.parse([["value"], ["3 words"], ["anything else"]])
[PriorityTable(value='specific'), PriorityTable(value='catch-all')]
# --8<-- [end:pattern-order-output]

# --8<-- [start:predicate-dsl]
predicate_cells = CellDSL()


@predicate_cells.when(
    lambda value, context: value.startswith("CMS:"),
    fields=("headline",),
)
def cms_headline(value, context):
    return value.removeprefix("CMS:").replace("-", " ").title()
# --8<-- [end:predicate-dsl]

# --8<-- [start:predicate-schema]
class PredicateContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=predicate_cells)
    status = field("Status", parser=predicate_cells)
# --8<-- [end:predicate-schema]

# --8<-- [start:predicate-output]
>> PredicateContentTable.parse(
...     [
...         ["IDs", "A-1"],
...         ["Headline", "CMS:market-brief"],
...         ["Status", "CMS:draft"],
...     ]
... )[0]
PredicateContentTable(id='A-1', headline='Market Brief', status='CMS:draft')
# --8<-- [end:predicate-output]

# --8<-- [start:fallback-dsl]
status_cells = CellDSL()


@status_cells.token("published")
def published(context):
    return "PUBLISHED"


@status_cells.fallback
def normalize_status(value, context):
    return value.strip().casefold().replace(" ", "-")
# --8<-- [end:fallback-dsl]

# --8<-- [start:fallback-schema]
class StatusTable(ColumnTable):
    id = id_field("IDs")
    status = field("Status", parser=status_cells)
# --8<-- [end:fallback-schema]

# --8<-- [start:fallback-output]
>> records = StatusTable.parse(
...     [
...         ["IDs", "A-1", "A-2", "A-3"],
...         ["Status", "Drafted", "Ready For Review", "published"],
...     ]
... )
>> [record.status for record in records]
['drafted', 'ready-for-review', 'PUBLISHED']
# --8<-- [end:fallback-output]

# --8<-- [start:duplicate-pattern]
cells = CellDSL()


@cells.pattern(r"\d+ words")
def first_words(match, context):
    return "first"


@cells.pattern(r"\d+ words")
def second_words(match, context):
    return "second"
# --8<-- [end:duplicate-pattern]

# --8<-- [start:duplicate-pattern-output]
Cell DSL pattern '\\d+ words' is already registered for this scope
# --8<-- [end:duplicate-pattern-output]

# --8<-- [start:duplicate-fallback]
cells = CellDSL()


@cells.fallback
def first_fallback(value, context):
    return value


@cells.fallback
def second_fallback(value, context):
    return value
# --8<-- [end:duplicate-fallback]

# --8<-- [start:duplicate-fallback-output]
Cell DSL fallback is already registered
# --8<-- [end:duplicate-fallback-output]

# --8<-- [start:pattern-error]
broken_cells = CellDSL()


@broken_cells.pattern(r"(?P<count>\d+) words")
def broken_words(match, context):
    raise RuntimeError("word generator unavailable")


class BrokenTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=broken_cells)
# --8<-- [end:pattern-error]

# --8<-- [start:pattern-error-call]
BrokenTable.parse([["IDs", "A-1"], ["Headline", "3 words"]])
# --8<-- [end:pattern-error-call]

# --8<-- [start:pattern-error-output]
Field parser failed: word generator unavailable (code=parser_failed, schema=BrokenTable, field='Headline', row=2, column=2, item_id='A-1', value='3 words'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:pattern-error-output]
