"""Column-oriented table traversal for the internal parsing engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .context import ParseContext
from .engine_types import INVALID, ErrorCollector, SchemaRuntime
from .errors import TableError, TableErrorCode
from .schema_compiler import seal_schema_family
from .schema_plan import ErrorMode
from .table import RawTable, TableData


def parse_column_table(
    schema: type[SchemaRuntime],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None,
    error_mode: str,
    convert_output: bool,
) -> list[Any]:
    """Parse column-oriented records through shared compiled schema helpers."""
    mode = schema._validate_error_mode(error_mode)
    seal_schema_family(schema)
    errors: ErrorCollector = [] if mode is ErrorMode.COLLECT else None
    parse_context = schema._parse_context(context)
    table = schema._prepare_table(datatable, parse_context)
    id_item = schema.__schema_plan__.id_field
    if id_item is None:
        raise RuntimeError("A compiled ColumnTable must have exactly one ID field")
    id_declared = id_item.declaration

    width = len(table.rows[0])
    id_label_cell = table.rows[0][0]
    if id_label_cell.value not in id_declared.labels:
        raise TableError.from_cell(
            "The first row must be the declared id field",
            id_label_cell,
            schema=schema,
            field_name=id_item.name,
            field_label=id_declared.label,
            code=TableErrorCode.INVALID_ID,
            hint="Move the declared id_field label into the first cell.",
        )
    for row_number, row_cells in enumerate(table.rows, start=1):
        if len(row_cells) != width:
            source_row = row_cells[0].source_row if row_cells else row_number
            schema._report(
                TableError(
                    f"Ragged row: expected {width} cells, got {len(row_cells)}",
                    schema=schema,
                    row=source_row,
                    source_uri=table.source_uri,
                    code=TableErrorCode.RAGGED_ROW,
                    hint=(
                        "Make every table row contain the same number of cells "
                        "as the ID row."
                    ),
                ),
                errors,
            )
    schema._raise_collected(errors)

    label_cells = [row[0] for row in table.rows]
    labels = [cell.value for cell in label_cells]
    schema._reject_duplicates(label_cells, errors)
    schema._validate_table_labels(label_cells, errors)
    if width == 1:
        schema._validate_required_presence(
            labels,
            errors,
            source_uri=table.source_uri,
        )
    records: list[Any] = []
    seen_ids: set[Any] = set()
    for column_index in range(1, width):
        id_cell = table.rows[0][column_index]
        item_id = schema._value_for(
            id_declared,
            present=True,
            cell=id_cell,
            parse_context=parse_context,
            item_id=id_cell.value or None,
            source_uri=id_cell.source_uri or table.source_uri,
            errors=errors,
        )
        if item_id is INVALID:
            continue
        if not schema._validate_id(item_id, id_cell, id_declared, errors):
            continue
        if item_id in seen_ids:
            schema._report(
                TableError.from_cell(
                    "Duplicate item ID",
                    id_cell,
                    schema=schema,
                    field_name=id_item.name,
                    field_label=id_declared.label,
                    item_id=item_id,
                    code=TableErrorCode.DUPLICATE_ID,
                    hint="Use one unique item ID per parsed column.",
                ),
                errors,
            )
            continue
        seen_ids.add(item_id)

        cells_by_label = {
            label: table.rows[row_index][column_index]
            for row_index, label in enumerate(labels)
        }
        record_cls, parsed_selector = schema._select_record_schema(
            cells_by_label,
            parse_context=parse_context,
            item_id=item_id,
            errors=errors,
        )
        if record_cls is None:
            continue
        extras = schema._reject_inapplicable_values(
            record_cls,
            cells_by_label,
            item_id=item_id,
            errors=errors,
        )
        parsed_values = {id_item.name: item_id, **parsed_selector}
        parsed_sources = {id_item.name: id_cell}
        valid_record, values, source_cells, item_id = schema._parse_record_values(
            record_cls,
            cells_by_label,
            parse_context=parse_context,
            item_id=item_id,
            errors=errors,
            parsed_values=parsed_values,
            parsed_sources=parsed_sources,
        )
        if not valid_record:
            continue
        records.append(
            record_cls._record_from_values(
                values,
                cells=source_cells,
                column=id_cell.source_column,
                item_id=item_id,
                extras=extras,
            )
        )
    return schema._finalize_records(
        records,
        parse_context,
        errors,
        convert_output=convert_output,
    )
