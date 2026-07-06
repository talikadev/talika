# --8<-- [start:feature-composition]
Feature: CMS shared and content-specific cell vocabulary

  Scenario: Compose shared tokens with content generated values
    Given the content items:
      | IDs      | A-1  | A-2       | A-3     | A-4   |
      | Headline | none | fake:hero | Literal | today |
    Then the first matching DSL owns each value
# --8<-- [end:feature-composition]

# --8<-- [start:shared-dsl]
from talika import (
    CellDSL,
    ColumnTable,
    RowTable,
    compose_cell_dsls,
    field,
    id_field,
)


shared_cells = CellDSL()


@shared_cells.token("none")
def none_value(context):
    return None


@shared_cells.token("today")
def today_value(context):
    return context.user_data["today"]
# --8<-- [end:shared-dsl]

# --8<-- [start:content-dsl]
content_cells = CellDSL()


@content_cells.pattern(r"fake:(.+)")
def fake_value(match, context):
    return f"Generated {match[1]} for {context.item_id}"
# --8<-- [end:content-dsl]

# --8<-- [start:compose-parser]
headline_parser = compose_cell_dsls(shared_cells, content_cells)
# --8<-- [end:compose-parser]

# --8<-- [start:content-schema]
class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=headline_parser)
# --8<-- [end:content-schema]

# --8<-- [start:compose-call]
records = ContentTable.parse(
    [
        ["IDs", "A-1", "A-2", "A-3", "A-4"],
        ["Headline", "none", "fake:hero", "Literal", "today"],
    ],
    context={"today": "2026-07-04"},
)
# --8<-- [end:compose-call]

# --8<-- [start:compose-output]
>> [record.headline for record in records]
[None, 'Generated hero for A-2', 'Literal', '2026-07-04']
# --8<-- [end:compose-output]

# --8<-- [start:order-dsls]
shared_conflict = CellDSL()
project_conflict = CellDSL()


@shared_conflict.token("draft")
def shared_draft(context):
    return "DRAFT"


@project_conflict.token("draft")
def project_draft(context):
    return "project-draft"
# --8<-- [end:order-dsls]

# --8<-- [start:order-schema]
class SharedFirstTable(RowTable):
    value = field(
        "value",
        parser=compose_cell_dsls(shared_conflict, project_conflict),
    )


class ProjectFirstTable(RowTable):
    value = field(
        "value",
        parser=compose_cell_dsls(project_conflict, shared_conflict),
    )
# --8<-- [end:order-schema]

# --8<-- [start:order-output]
>> SharedFirstTable.parse([["value"], ["draft"]])[0].value
'DRAFT'

>> ProjectFirstTable.parse([["value"], ["draft"]])[0].value
'project-draft'
# --8<-- [end:order-output]

# --8<-- [start:method-compose]
headline_parser = content_cells.compose(shared_cells)


class MethodTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", parser=headline_parser)
# --8<-- [end:method-compose]

# --8<-- [start:method-equivalent]
compose_cell_dsls(content_cells, shared_cells)
# --8<-- [end:method-equivalent]

# --8<-- [start:method-output]
>> records = MethodTable.parse(
...     [["IDs", "A-1", "A-2"], ["Headline", "fake:hero", "none"]]
... )
>> [record.headline for record in records]
['Generated hero for A-1', None]
# --8<-- [end:method-output]

# --8<-- [start:fallback-dsls]
fallback_first = CellDSL()
later_cells = CellDSL()


@fallback_first.fallback
def fallback(value, context):
    return f"fallback:{value}"


@later_cells.token("none")
def later_none(context):
    return None
# --8<-- [end:fallback-dsls]

# --8<-- [start:fallback-schema]
class FallbackFirstTable(RowTable):
    value = field(
        "value",
        parser=compose_cell_dsls(fallback_first, later_cells),
    )


class FallbackLastTable(RowTable):
    value = field(
        "value",
        parser=compose_cell_dsls(later_cells, fallback_first),
    )
# --8<-- [end:fallback-schema]

# --8<-- [start:fallback-output]
>> FallbackFirstTable.parse([["value"], ["none"], ["literal"]])
[FallbackFirstTable(value='fallback:none'), FallbackFirstTable(value='fallback:literal')]

>> FallbackLastTable.parse([["value"], ["none"], ["literal"]])
[FallbackLastTable(value=None), FallbackLastTable(value='fallback:literal')]
# --8<-- [end:fallback-output]

# --8<-- [start:invalid-empty]
compose_cell_dsls()
# --8<-- [end:invalid-empty]

# --8<-- [start:invalid-empty-output]
CellDSLChain requires at least one DSL
# --8<-- [end:invalid-empty-output]

# --8<-- [start:invalid-type]
compose_cell_dsls(CellDSL(), object())
# --8<-- [end:invalid-type]

# --8<-- [start:invalid-type-output]
CellDSLChain accepts only CellDSL instances
# --8<-- [end:invalid-type-output]
