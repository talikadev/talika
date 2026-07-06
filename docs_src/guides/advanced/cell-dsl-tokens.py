# --8<-- [start:feature-content]
Feature: CMS generated content

  Scenario: Use project tokens in content setup
    Given the content items:
      | IDs      | A-1    |
      | Headline | random |
      | Status   | random |
    Then only the headline token is expanded
# --8<-- [end:feature-content]

# --8<-- [start:token-dsl]
from talika import CellDSL, ColumnTable, RowTable, field, id_field


content_cells = CellDSL()


@content_cells.token("random", fields=("headline",))
def random_headline(context):
    generator = context.user_data["generator"]
    return generator(context.item_id)
# --8<-- [end:token-dsl]

# --8<-- [start:content-schema]
class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", required=True, parser=content_cells)
    status = field("Status", parser=content_cells)
# --8<-- [end:content-schema]

# --8<-- [start:scope-example]
headline = field("Headline", parser=content_cells)
# --8<-- [end:scope-example]

# --8<-- [start:content-table]
content_table = [
    ["IDs", "A-1"],
    ["Headline", "random"],
    ["Status", "random"],
]
# --8<-- [end:content-table]

# --8<-- [start:token-parse]
record = ContentTable.parse(
    content_table,
    context={
        "generator": lambda item_id: f"Generated headline for {item_id}",
    },
)[0]
# --8<-- [end:token-parse]

# --8<-- [start:token-output]
>> record
ContentTable(id='A-1', headline='Generated headline for A-1', status='random')

>> record.headline
'Generated headline for A-1'

>> record.status
'random'
# --8<-- [end:token-output]

# --8<-- [start:context-dsl]
context_cells = CellDSL()


@context_cells.token("where")
def where(context):
    return {
        "field": context.field_name,
        "label": context.field_label,
        "row": context.row,
        "column": context.column,
        "item_id": context.item_id,
        "source": context.source_value,
    }
# --8<-- [end:context-dsl]

# --8<-- [start:context-schema]
class ContextTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=context_cells)
# --8<-- [end:context-schema]

# --8<-- [start:context-output]
>> ContextTable.parse([["IDs", "A-1"], ["Headline", "where"]])[0].headline
{'field': 'headline', 'label': 'Headline', 'row': 2, 'column': 2, 'item_id': 'A-1', 'source': 'where'}
# --8<-- [end:context-output]

# --8<-- [start:global-and-scoped]
scoped_cells = CellDSL()


@scoped_cells.token("random")
def global_random(context):
    return "global value"


@scoped_cells.token("random", fields=("headline",))
def scoped_random(context):
    return "headline value"
# --8<-- [end:global-and-scoped]

# --8<-- [start:scoped-schema]
class ScopedTable(RowTable):
    headline = field("headline", parser=scoped_cells)
    category = field("category", parser=scoped_cells)
# --8<-- [end:scoped-schema]

# --8<-- [start:scoped-output]
>> ScopedTable.parse([["headline", "category"], ["random", "random"]])[0]
ScopedTable(headline='headline value', category='global value')
# --8<-- [end:scoped-output]

# --8<-- [start:passthrough]
literal_cells = CellDSL()


class LiteralTable(RowTable):
    value = field("value", parser=literal_cells)
# --8<-- [end:passthrough]

# --8<-- [start:passthrough-output]
>> LiteralTable.parse([["value"], ["literal"]])[0].value
'literal'
# --8<-- [end:passthrough-output]

# --8<-- [start:empty-token]
cells = CellDSL()
cells.token("")
# --8<-- [end:empty-token]

# --8<-- [start:empty-token-output]
Cell DSL token cannot be empty
# --8<-- [end:empty-token-output]

# --8<-- [start:duplicate-token]
cells = CellDSL()


@cells.token("random")
def first_random(context):
    return "first"


@cells.token("random")
def second_random(context):
    return "second"
# --8<-- [end:duplicate-token]

# --8<-- [start:duplicate-token-output]
Cell DSL token 'random' is already registered for this scope
# --8<-- [end:duplicate-token-output]

# --8<-- [start:handler-error]
broken_cells = CellDSL()


@broken_cells.token("broken")
def broken(context):
    raise RuntimeError("generator unavailable")


class BrokenTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=broken_cells)
# --8<-- [end:handler-error]

# --8<-- [start:handler-error-call]
BrokenTable.parse([["IDs", "A-1"], ["Headline", "broken"]])
# --8<-- [end:handler-error-call]

# --8<-- [start:handler-error-output]
Field parser failed: generator unavailable (code=parser_failed, schema=BrokenTable, field='Headline', row=2, column=2, item_id='A-1', value='broken'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:handler-error-output]
