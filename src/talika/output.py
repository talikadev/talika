"""Output conversion stage for the internal parsing engine."""

from __future__ import annotations

from typing import Any, cast

from .context import ParseContext
from .diagnostics import stable_callable_name
from .engine_types import ErrorCollector, SchemaRuntime
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors


def build_outputs(
    schema: type[SchemaRuntime],
    records: list[Any],
    parse_context: ParseContext,
    errors: ErrorCollector,
) -> list[Any]:
    """Convert validated records with their compiled output hooks."""
    converted: list[Any] = []
    for record in records:
        source = record.table_source
        record_cls = cast(Any, type(record))
        plan = record_cls.__schema_plan__
        builder = plan.hooks.build_output
        if builder is None:
            converted.append(record)
            continue
        try:
            converted.append(builder(record, parse_context))
        except TableError as exc:
            schema._report(exc, errors)
        except (TableErrors, SchemaDefinitionError):
            raise
        except Exception as exc:
            target = plan.hooks.output_model or builder
            target_name = stable_callable_name(target)
            subject = "Output model" if plan.hooks.output_model else "Output builder"
            error = TableError(
                f"{subject} {target_name} rejected the record: {exc}",
                schema=record_cls,
                row=source.row,
                column=source.column,
                item_id=source.item_id,
                source_uri=source.source_uri,
                code=TableErrorCode.OUTPUT_FAILED,
                cause=exc,
            )
            schema._report(error, errors)
    return converted
