"""Row-oriented table traversal for the internal parsing engine."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .context import ParseContext
from .engine_types import INVALID, ErrorCollector, SchemaRuntime
from .errors import TableError, TableErrorCode
from .schema_compiler import seal_schema_family
from .schema_plan import ErrorMode
from .table import RawTable, TableCell, TableData


def parse_row_table(
    schema: type[SchemaRuntime],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None,
    error_mode: str,
    convert_output: bool,
) -> list[Any]:
    """Parse row-oriented records through shared compiled schema helpers."""
    mode = schema._validate_error_mode(error_mode)
    seal_schema_family(schema)
    errors: ErrorCollector = [] if mode is ErrorMode.COLLECT else None
    parse_context = schema._parse_context(context)
    table = schema._prepare_table(datatable, parse_context)
    header_cells = table.rows[0]
    headers = [cell.value for cell in header_cells]
    schema._reject_duplicates(header_cells, errors)
    schema._validate_table_labels(header_cells, errors)
    if len(table.rows) == 1:
        schema._validate_required_presence(
            headers,
            errors,
            source_uri=table.source_uri,
        )

    plan = schema.__schema_plan__
    id_item = plan.id_field
    preparse_id = id_item is not None
    records: list[Any] = []
    seen_ids: set[Any] = set()
    for row_number, row_cells in enumerate(table.rows[1:], start=2):
        if len(row_cells) != len(headers):
            source_row = row_cells[0].source_row if row_cells else row_number
            schema._report(
                TableError(
                    f"Ragged row: expected {len(headers)} cells, got {len(row_cells)}",
                    schema=schema,
                    row=source_row,
                    source_uri=table.source_uri,
                    code=TableErrorCode.RAGGED_ROW,
                    hint=(
                        "Make every data row contain the same number of cells "
                        "as the header row."
                    ),
                ),
                errors,
            )
            continue

        item_id = None
        cells_by_label = dict(zip(headers, row_cells, strict=True))
        parsed_values: dict[str, Any] = {}
        parsed_sources: dict[str, TableCell] = {}
        if preparse_id:
            if id_item is None:  # pragma: no cover - narrowed above
                raise RuntimeError("Compiled ID field disappeared")
            id_name = id_item.name
            id_declared = id_item.declaration
            id_cell = schema._cell_for_field(id_declared, cells_by_label)
            item_id = schema._value_for(
                id_declared,
                present=id_cell is not None,
                cell=id_cell,
                parse_context=parse_context,
                item_id=id_cell.value if id_cell is not None else None,
                source_uri=id_cell.source_uri
                if id_cell is not None
                else table.source_uri,
                errors=errors,
            )
            if item_id is INVALID:
                continue
            if id_cell is None:
                raise RuntimeError("A parsed ID must have a source cell")
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
                        hint="Use one unique item ID per parsed row.",
                    ),
                    errors,
                )
                continue
            seen_ids.add(item_id)
            parsed_values[id_name] = item_id
            parsed_sources[id_name] = id_cell

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
        parsed_values.update(parsed_selector)
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
                row=row_cells[0].source_row if row_cells else row_number,
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
