"""Local record-reference resolution for the internal parsing engine."""

from __future__ import annotations

from typing import Any, cast

from .context import CellContext, ParseContext
from .diagnostics import stable_text_value
from .engine_types import DiagnosticCollector, SchemaRuntime
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors
from .fields import Field


def resolve_references(
    schema: type[SchemaRuntime],
    records: list[Any],
    parse_context: ParseContext,
    errors: DiagnosticCollector,
) -> None:
    """Resolve references deterministically using compiled family metadata."""
    records_with_references = [
        record
        for record in records
        if any(
            item.reference is not None
            for item in cast(Any, type(record)).__schema_plan__.fields
        )
    ]
    if not records_with_references:
        return

    target_fields = {
        name: item.declaration
        for name, item in schema.__schema_plan__.reference_targets.items()
    }
    indexes: dict[str, dict[Any, Any]] = {}
    invalid_targets: set[str] = set()
    for source_record in records_with_references:
        for item in cast(Any, type(source_record)).__schema_plan__.fields:
            spec = item.reference
            if spec is None or spec.target in indexes:
                continue
            index: dict[Any, Any] = {}
            for record in records:
                record_plan = cast(Any, type(record)).__schema_plan__
                if spec.target not in record_plan.fields_by_name:
                    continue
                target_value = getattr(record, spec.target)
                target_item = record_plan.fields_by_name[spec.target]
                cell = record.table_source.cells.get(spec.target)
                try:
                    hash(target_value)
                except TypeError as exc:
                    if cell is not None:
                        error = TableError.from_cell(
                            "Reference target "
                            f"{stable_text_value(target_value)} must be hashable",
                            cell,
                            schema=type(record),
                            field_name=target_item.name,
                            field_label=target_item.label,
                            code=TableErrorCode.REFERENCE_FAILED,
                            cause=exc,
                        )
                    else:
                        error = TableError(
                            "Reference target "
                            f"{stable_text_value(target_value)} must be hashable",
                            schema=type(record),
                            field_name=target_item.name,
                            field_label=target_item.label,
                            source_uri=record.table_source.source_uri,
                            row=record.table_source.row,
                            column=record.table_source.column,
                            code=TableErrorCode.REFERENCE_FAILED,
                            cause=exc,
                        )
                    schema._report(error, errors)
                    invalid_targets.add(spec.target)
                    continue
                if target_value in index:
                    if cell is not None:
                        error = TableError.from_cell(
                            "Reference target "
                            f"{stable_text_value(target_value)} is not unique",
                            cell,
                            schema=type(record),
                            field_name=target_item.name,
                            field_label=target_item.label,
                            code=TableErrorCode.REFERENCE_FAILED,
                        )
                    else:
                        error = TableError(
                            "Reference target "
                            f"{stable_text_value(target_value)} is not unique",
                            schema=type(record),
                            field_name=target_item.name,
                            field_label=target_item.label,
                            source_uri=record.table_source.source_uri,
                            row=record.table_source.row,
                            column=record.table_source.column,
                            code=TableErrorCode.REFERENCE_FAILED,
                        )
                    schema._report(error, errors)
                    invalid_targets.add(spec.target)
                    continue
                index[target_value] = record
            indexes[spec.target] = index

    for record in records:
        for item in cast(Any, type(record)).__schema_plan__.fields:
            spec = item.reference
            if spec is None:
                continue
            raw = getattr(record, item.name)
            if raw in (None, ""):
                setattr(record, item.name, [] if spec.many else None)
                continue
            if spec.target in invalid_targets:
                continue
            keys = (
                [part.strip() for part in str(raw).split(spec.separator)]
                if spec.many
                else [raw]
            )
            resolved: list[Any] = []
            field_failed = False
            for key in keys:
                try:
                    key = _parse_reference_key(
                        key,
                        target_field=target_fields[spec.target],
                        source_record=record,
                        source_field=item.name,
                        parse_context=parse_context,
                    )
                except TableError as exc:
                    schema._report(exc, errors)
                    field_failed = True
                    continue
                try:
                    resolved.append(indexes[spec.target][key])
                except (KeyError, TypeError) as exc:
                    cell = record.source_for(item.name)
                    error = TableError.from_cell(
                        f"Reference target {stable_text_value(key)} was not found",
                        cell,
                        schema=schema,
                        field_name=item.name,
                        field_label=item.label,
                        item_id=record.table_source.item_id,
                        code=TableErrorCode.REFERENCE_FAILED,
                        cause=exc,
                    )
                    schema._report(error, errors)
                    field_failed = True
            if not field_failed:
                setattr(record, item.name, resolved if spec.many else resolved[0])


def _parse_reference_key(
    value: Any,
    *,
    target_field: Field,
    source_record: Any,
    source_field: str,
    parse_context: ParseContext,
) -> Any:
    """Convert one reference key with the compiled target parser contract."""
    if target_field.parser is None:
        return value
    source_cell = source_record.source_for(source_field)
    source_item = cast(Any, type(source_record)).__schema_plan__.fields_by_name[
        source_field
    ]
    cell_context = CellContext(
        schema=type(source_record),
        field_name=source_field,
        field_label=source_item.label,
        row=source_cell.source_row,
        column=source_cell.source_column,
        item_id=source_record.table_source.item_id,
        source_value=source_cell.source_value,
        user_data=parse_context.user_data,
        source_uri=source_cell.source_uri,
    )
    try:
        return target_field.parser(value, cell_context)
    except (TableError, TableErrors, SchemaDefinitionError):
        raise
    except Exception as exc:
        raise TableError.from_cell(
            f"Reference key conversion failed: {exc}",
            source_cell,
            schema=type(source_record),
            field_name=source_item.name,
            field_label=source_item.label,
            item_id=source_record.table_source.item_id,
            code=TableErrorCode.REFERENCE_FAILED,
            cause=exc,
        ) from exc
