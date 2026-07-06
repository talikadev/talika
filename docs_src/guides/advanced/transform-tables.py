# --8<-- [start:feature]
Feature: CMS table normalization

  Scenario: Normalize authored content values before parsing
    Given the content table:
      | IDs      | a-1              |
      | Headline | market brief     |
      | Status   | Ready For Review |
    Then the parsed content record uses normalized values
# --8<-- [end:feature]

# --8<-- [start:direct-hook]
from talika import ColumnTable, TableData, field, id_field


raw_content = [
    ["IDs", "a-1"],
    ["Headline", "market brief"],
    ["Status", "Ready For Review"],
]


class NormalizedContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline")
    status = field("Status")

    @classmethod
    def transform_table(cls, table, context):
        rows = [list(row) for row in table.rows]

        rows[0][1] = rows[0][1].with_value(rows[0][1].value.upper())
        rows[1][1] = rows[1][1].with_value(rows[1][1].value.title())
        rows[2][1] = rows[2][1].with_value(
            rows[2][1].value.casefold().replace(" ", "-")
        )

        return TableData.from_cells(rows)


record = NormalizedContentTable.parse_records(raw_content)[0]
# --8<-- [end:direct-hook]

# --8<-- [start:direct-output]
>> record
NormalizedContentTable(id='A-1', headline='Market Brief', status='ready-for-review')

>> (record.id, record.headline, record.status)
('A-1', 'Market Brief', 'ready-for-review')
# --8<-- [end:direct-output]

# --8<-- [start:source-preserved-output]
>> record.source_for("status")
TableCell(value='ready-for-review', source_row=3, source_column=2, source_value='Ready For Review')

>> (record.source_for("status").value, record.source_for("status").source_value)
('ready-for-review', 'Ready For Review')
# --8<-- [end:source-preserved-output]

# --8<-- [start:pipeline]
from talika import ColumnTable, TableData, compose_transformers, field, id_field


class PrefixFromContext:
    def transform(self, table, context, *, schema=None):
        rows = [list(row) for row in table.rows]
        prefix = context.user_data.get("id_prefix", "")
        rows[0][1] = rows[0][1].with_value(prefix + rows[0][1].value)
        return TableData.from_cells(rows)


class TitleHeadline:
    def transform(self, table, context, *, schema=None):
        rows = [list(row) for row in table.rows]
        rows[1][1] = rows[1][1].with_value(rows[1][1].value.title())
        return TableData.from_cells(rows)


class PipelineContentTable(ColumnTable):
    table_transformer = compose_transformers(PrefixFromContext(), TitleHeadline())

    id = id_field("IDs")
    headline = field("Headline")


pipeline_raw = [
    ["IDs", "42"],
    ["Headline", "release notes"],
]

pipeline_record = PipelineContentTable.parse_records(
    pipeline_raw,
    context={"id_prefix": "DOC-"},
)[0]
# --8<-- [end:pipeline]

# --8<-- [start:pipeline-output]
>> pipeline_record
PipelineContentTable(id='DOC-42', headline='Release Notes')

>> pipeline_record.source_for("id")
TableCell(value='DOC-42', source_row=1, source_column=2, source_value='42')
# --8<-- [end:pipeline-output]

# --8<-- [start:invalid-return]
from talika import RowTable, field


class InvalidTransformTable(RowTable):
    value = field("value")

    @classmethod
    def transform_table(cls, table, context):
        return table.to_rows()


InvalidTransformTable.parse([["value"], ["one"]])
# --8<-- [end:invalid-return]

# --8<-- [start:invalid-return-output]
Table transformation must return TableData (code=invalid_transform, schema=InvalidTransformTable)
# --8<-- [end:invalid-return-output]

# --8<-- [start:intentional-error]
from talika import RowTable, TableError, field


class RangeTable(RowTable):
    value = field("value")

    @classmethod
    def transform_table(cls, table, context):
        cell = table.cell(2, 1)
        raise TableError.from_cell("Invalid range", cell, schema=cls)


RangeTable.parse([["value"], ["3..1"]])
# --8<-- [end:intentional-error]

# --8<-- [start:intentional-error-output]
Invalid range (code=table_error, schema=RangeTable, row=2, column=1, value='3..1')
# --8<-- [end:intentional-error-output]

# --8<-- [start:pipeline-invalid-output]
Table transformer stage 1 (BadStage) must return TableData (code=invalid_transform, schema=PipelineFailureTable)
# --8<-- [end:pipeline-invalid-output]
