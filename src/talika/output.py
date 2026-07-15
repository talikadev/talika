"""Output conversion stage for the internal parsing engine."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from .context import ParseContext
from .diagnostics import stable_callable_name
from .engine_types import DiagnosticCollector, SchemaRuntime
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors


def build_outputs(
    schema: type[SchemaRuntime],
    records: list[Any],
    parse_context: ParseContext,
    errors: DiagnosticCollector,
    output_model: Callable[..., Any] | None = None,
) -> list[Any]:
    """Convert validated records with an explicit or compiled output hook.

    Args:
        schema: Root schema responsible for reporting output failures.
        records: Validated schema records to convert.
        parse_context: Context shared with configured custom builders.
        errors: Active lifecycle diagnostic collector.
        output_model: Explicit callable applied to every record. When omitted,
            each record uses its compiled output model or custom builder.

    Returns:
        Successfully converted public output objects.

    Raises:
        TableError: In fail-fast mode when output construction fails.
        TableErrors: When project output code raises a deliberate aggregate.
        SchemaDefinitionError: When project output code raises a deliberate
            schema definition error.

    """
    converted: list[Any] = []
    for record in records:
        source = record.table_source
        record_cls = cast(Any, type(record))
        plan = record_cls.__schema_plan__
        builder = plan.hooks.build_output
        target = output_model if output_model is not None else plan.hooks.output_model
        if target is None and builder is None:
            schema._report(
                TableError(
                    "No output model or custom output builder is configured for "
                    f"{plan.display_name}",
                    schema=record_cls,
                    row=source.row,
                    column=source.column,
                    item_id=source.item_id,
                    source_uri=source.source_uri,
                    code=TableErrorCode.OUTPUT_FAILED,
                    hint=(
                        "Pass a callable to parse_as(), configure output_model, "
                        "or override build_output()."
                    ),
                ),
                errors,
            )
            continue
        try:
            if target is not None:
                converted.append(target(**record.as_dict()))
            else:
                converted.append(builder(record, parse_context))
        except TableError as exc:
            schema._report(exc, errors)
        except (TableErrors, SchemaDefinitionError):
            raise
        except Exception as exc:
            failed_target = target if target is not None else builder
            target_name = stable_callable_name(failed_target)
            subject = "Output model" if target is not None else "Output builder"
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
