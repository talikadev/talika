# --8<-- [start:feature-source]
Feature: Source-aware table diagnostics

  Scenario: Inspect where parsed content values came from
    Given the content items:
      | IDs      | A-1          |
      | Headline | Market brief |
    Then the parsed record keeps source cell metadata
# --8<-- [end:feature-source]

# --8<-- [start:tabledata-basic]
from talika import (
    ColumnTable,
    RowTable,
    TableCell,
    TableData,
    TableError,
    field,
    id_field,
)


raw_rows = [
    ["name", "role"],
    ["Alice", "admin"],
]

table = TableData.from_rows(raw_rows)
role_cell = table.cell(2, 2)
# --8<-- [end:tabledata-basic]

# --8<-- [start:tabledata-output]
>> table.to_rows()
[['name', 'role'], ['Alice', 'admin']]

>> role_cell
TableCell(value='admin', source_row=2, source_column=2, source_value='admin')

>> (role_cell.value, role_cell.source_row, role_cell.source_column, role_cell.source_value)
('admin', 2, 2, 'admin')
# --8<-- [end:tabledata-output]

# --8<-- [start:with-value]
changed_role = role_cell.with_value("ADMIN")

changed_table = TableData.from_cells(
    [
        [table.cell(1, 1), table.cell(1, 2)],
        [table.cell(2, 1), changed_role],
    ]
)
# --8<-- [end:with-value]

# --8<-- [start:with-value-output]
>> changed_role
TableCell(value='ADMIN', source_row=2, source_column=2, source_value='admin')

>> changed_table.to_rows()
[['name', 'role'], ['Alice', 'ADMIN']]
# --8<-- [end:with-value-output]

# --8<-- [start:row-schema]
class UserTable(RowTable):
    name = field("name")
    role = field("role")
# --8<-- [end:row-schema]

# --8<-- [start:row-source]
user = UserTable.parse(raw_rows)[0]
role_source = user.source_for("role")
# --8<-- [end:row-source]

# --8<-- [start:row-source-output]
>> user
UserTable(name='Alice', role='admin')

>> (user.table_source.row, user.table_source.column, user.table_source.item_id)
(2, None, None)

>> role_source
TableCell(value='admin', source_row=2, source_column=2, source_value='admin')
# --8<-- [end:row-source-output]

# --8<-- [start:column-schema]
class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline")
    status = field("Status", default="draft")
# --8<-- [end:column-schema]

# --8<-- [start:column-source]
content = ContentTable.parse(
    [
        ["IDs", "A-1"],
        ["Headline", "Market brief"],
    ]
)[0]
# --8<-- [end:column-source]

# --8<-- [start:column-source-output]
>> content
ContentTable(id='A-1', headline='Market brief', status='draft')

>> (content.table_source.item_id, content.table_source.column, content.table_source.row)
('A-1', 2, None)

>> content.source_for("id")
TableCell(value='A-1', source_row=1, source_column=2, source_value='A-1')

>> content.source_for("headline")
TableCell(value='Market brief', source_row=2, source_column=2, source_value='Market brief')
# --8<-- [end:column-source-output]

# --8<-- [start:missing-source]
content.source_for("status")
# --8<-- [end:missing-source]

# --8<-- [start:missing-source-output]
KeyError: "No source cell is available for field 'status'"
# --8<-- [end:missing-source-output]

# --8<-- [start:readonly-source]
user.table_source.cells["role"] = None
# --8<-- [end:readonly-source]

# --8<-- [start:readonly-source-output]
TypeError: 'mappingproxy' object does not support item assignment
# --8<-- [end:readonly-source-output]

# --8<-- [start:transform-schema]
class UpperRoleTable(RowTable):
    name = field("name")
    role = field("role")

    @classmethod
    def transform_table(cls, table, context):
        rows = [list(row) for row in table.rows]
        rows[1][1] = rows[1][1].with_value(rows[1][1].value.upper())
        return TableData.from_cells(rows)
# --8<-- [end:transform-schema]

# --8<-- [start:transform-output]
>> record = UpperRoleTable.parse(raw_rows)[0]
>> record.role
'ADMIN'

>> record.source_for("role")
TableCell(value='ADMIN', source_row=2, source_column=2, source_value='admin')
# --8<-- [end:transform-output]

# --8<-- [start:error-from-cell]
source = TableCell.from_value("invalid-range", row=3, column=4)
error = TableError.from_cell(
    "Invalid range",
    source,
    schema="ContentTable",
)
# --8<-- [end:error-from-cell]

# --8<-- [start:error-from-cell-output]
>> str(error)
"Invalid range (code=table_error, schema=ContentTable, row=3, column=4, value='invalid-range')"

>> (error.row, error.column, error.value)
(3, 4, 'invalid-range')
# --8<-- [end:error-from-cell-output]

# --8<-- [start:parser-error-after-transform]
def reject_role(value, context):
    raise ValueError("role unavailable")


class BrokenRoleTable(RowTable):
    name = field("name")
    role = field("role", parser=reject_role)

    @classmethod
    def transform_table(cls, table, context):
        rows = [list(row) for row in table.rows]
        rows[1][1] = rows[1][1].with_value(rows[1][1].value.upper())
        return TableData.from_cells(rows)
# --8<-- [end:parser-error-after-transform]

# --8<-- [start:parser-error-after-transform-call]
BrokenRoleTable.parse(raw_rows)
# --8<-- [end:parser-error-after-transform-call]

# --8<-- [start:parser-error-after-transform-output]
Field parser failed: role unavailable (code=parser_failed, schema=BrokenRoleTable, field='role', row=2, column=2, value='admin'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:parser-error-after-transform-output]
