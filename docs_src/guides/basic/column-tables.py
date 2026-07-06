# --8<-- [start:feature-basic]
Given the content exists
  | IDs      | A-1          | P-1             |
  | Type     | Article      | Poll            |
  | Headline | Market brief | Reader question |
  | Status   | draft        | published       |
# --8<-- [end:feature-basic]

# --8<-- [start:datatable-basic]
datatable = [
    ["IDs", "A-1", "P-1"],
    ["Type", "Article", "Poll"],
    ["Headline", "Market brief", "Reader question"],
    ["Status", "draft", "published"],
]
# --8<-- [end:datatable-basic]

# --8<-- [start:contract-basic]
from talika import ColumnTable, field, id_field


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type", required=True)
    headline = field("Headline", required=True)
    status = field("Status")
# --8<-- [end:contract-basic]

# --8<-- [start:parse-basic]
items = ContentTable.parse(datatable)

assert [item.id for item in items] == ["A-1", "P-1"]
assert items[0].content_type == "Article"
assert items[0].headline == "Market brief"
assert items[1].content_type == "Poll"
assert items[1].status == "published"
# --8<-- [end:parse-basic]

# --8<-- [start:record-output]
>> items[0]
ContentTable(id='A-1', content_type='Article', headline='Market brief', status='draft')

>> items[0].as_dict()
{'id': 'A-1', 'content_type': 'Article', 'headline': 'Market brief', 'status': 'draft'}

>> items[0].table_source.item_id
'A-1'
# --8<-- [end:record-output]

# --8<-- [start:missing-optional]
items = ContentTable.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article", "Poll"],
        ["Headline", "Market brief", "Reader question"],
    ]
)

assert [item.status for item in items] == [None, None]
# --8<-- [end:missing-optional]

# --8<-- [start:empty-optional]
items = ContentTable.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article", "Poll"],
        ["Headline", "Market brief", "Reader question"],
        ["Status", "", "published"],
    ]
)

assert [item.status for item in items] == ["", "published"]
# --8<-- [end:empty-optional]

# --8<-- [start:missing-required]
ContentTable.parse(
    [
        ["IDs", "A-1"],
        ["Type", "Article"],
    ]
)
# --8<-- [end:missing-required]

# --8<-- [start:missing-required-output]
Required field is missing from the table 
(code=missing_required, schema=ContentTable, field='Headline', 
item_id='A-1'). 
Hint: Add this field to the table, or make the schema field optional if the project should supply it.
# --8<-- [end:missing-required-output]

# --8<-- [start:empty-required]
ContentTable.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article", "Poll"],
        ["Headline", "Market brief", ""],
    ]
)
# --8<-- [end:empty-required]

# --8<-- [start:empty-required-output]
Required field has an empty value 
(code=empty_required, schema=ContentTable, field='Headline', 
row=3, column=3, item_id='P-1', value=''). 
Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:empty-required-output]

# --8<-- [start:wrong-first-row]
ContentTable.parse(
    [
        ["Type", "Article"],
        ["IDs", "A-1"],
        ["Headline", "Market brief"],
    ]
)
# --8<-- [end:wrong-first-row]

# --8<-- [start:wrong-first-row-output]
The first row must be the declared id field 
(code=table_error, schema=ContentTable, field='IDs', 
row=1, column=1, value='Type'). 
Hint: Move the declared id_field label into the first cell.
# --8<-- [end:wrong-first-row-output]

# --8<-- [start:duplicate-id]
ContentTable.parse(
    [
        ["IDs", "A-1", "A-1"],
        ["Type", "Article", "Poll"],
        ["Headline", "Market brief", "Duplicate poll"],
    ]
)
# --8<-- [end:duplicate-id]

# --8<-- [start:duplicate-id-output]
Duplicate item ID 
(code=duplicate_id, schema=ContentTable, field='IDs', 
row=1, column=3, item_id='A-1', value='A-1'). 
Hint: Use one unique item ID per parsed column.
# --8<-- [end:duplicate-id-output]

# --8<-- [start:ragged-row]
ContentTable.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article"],
        ["Headline", "Market brief", "Reader question"],
    ]
)
# --8<-- [end:ragged-row]

# --8<-- [start:ragged-row-output]
Ragged row: expected 3 cells, got 2 
(code=ragged_row, schema=ContentTable, row=2). 
Hint: Make every table row contain the same number of cells as the ID row.
# --8<-- [end:ragged-row-output]

# --8<-- [start:column-metadata]
# Create a fast lookup dict mapping ID to the parsed item
items_by_id = {item.id: item for item in items}
assert items_by_id["A-1"].content_type == "Article"

# Access column metadata
# Unlike row tables (which store .row), column records store .column (1-based index)
col_number = items[0].table_source.column
assert col_number == 2
# --8<-- [end:column-metadata]

