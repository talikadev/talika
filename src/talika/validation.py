"""Record and table validation stages for the internal parsing engine."""

from __future__ import annotations

from typing import Any, cast

from .context import ParseContext
from .diagnostics import DiagnosticSeverity
from .engine_types import DiagnosticCollector, SchemaRuntime
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors


def run_validation(
    schema: type[SchemaRuntime],
    records: list[Any],
    parse_context: ParseContext,
    errors: DiagnosticCollector,
) -> None:
    """Run compiled record hooks in order, followed by the table hook."""
    for record in records:
        source = record.table_source
        record_cls = cast(Any, type(record))
        validator = record_cls.__schema_plan__.hooks.validate_record
        if validator is None:
            continue
        try:
            validator(record, parse_context)
        except TableError as exc:
            schema._report(exc, errors, allow_warning=True)
        except TableErrors as exc:
            if not any(
                item.severity is DiagnosticSeverity.WARNING for item in exc.errors
            ):
                raise
            for item in exc.errors:
                schema._report(item, errors, allow_warning=True)
        except SchemaDefinitionError:
            raise
        except Exception as exc:
            error = TableError(
                f"Record validation failed: {exc}",
                schema=record_cls,
                row=source.row,
                column=source.column,
                item_id=source.item_id,
                source_uri=source.source_uri,
                code=TableErrorCode.RECORD_VALIDATION_FAILED,
                cause=exc,
            )
            schema._report(error, errors, allow_warning=True)

    table_validator = schema.__schema_plan__.hooks.validate_records
    if table_validator is None:
        return
    try:
        table_validator(records, parse_context)
    except TableError as exc:
        schema._report(exc, errors, allow_warning=True)
    except TableErrors as exc:
        if not any(item.severity is DiagnosticSeverity.WARNING for item in exc.errors):
            raise
        for item in exc.errors:
            schema._report(item, errors, allow_warning=True)
    except SchemaDefinitionError:
        raise
    except Exception as exc:
        error = TableError(
            f"Table validation failed: {exc}",
            schema=schema,
            code=TableErrorCode.TABLE_VALIDATION_FAILED,
            source_uri=(records[0].table_source.source_uri if records else None),
            cause=exc,
        )
        schema._report(error, errors, allow_warning=True)
