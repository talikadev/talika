"""Small shared runtime types used by parsing engine stages."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, ClassVar, Protocol, TypeAlias, TypeVar

from .diagnostics import Diagnostic, ValidationResult
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors
from .schema_plan import ErrorMode, SchemaPlan

INVALID = object()
ErrorCollector: TypeAlias = list[TableError] | None
ResultT = TypeVar("ResultT")


def raising_result(
    operation: Callable[[], ResultT],
    *,
    schema_name: str,
    source_uri: str | None,
) -> ResultT:
    """Run a raising parser operation with an internal-error boundary."""
    try:
        return operation()
    except (TableError, TableErrors, SchemaDefinitionError):
        raise
    except Exception as exc:
        raise TableError(
            f"Unexpected Talika internal error: {type(exc).__name__}",
            schema=schema_name,
            source_uri=source_uri,
            code=TableErrorCode.INTERNAL_ERROR,
            hint="Inspect the exception cause and report this as a Talika bug.",
            cause=exc,
        ) from exc


def non_raising_result(
    operation: Callable[[], list[ResultT]],
    *,
    schema_name: str,
    source_uri: str | None,
) -> ValidationResult[ResultT]:
    """Run collect-mode record parsing and normalize its public result."""
    try:
        records = operation()
    except SchemaDefinitionError:
        raise
    except TableErrors as exc:
        return ValidationResult(diagnostics=exc.diagnostics)
    except TableError as exc:
        return ValidationResult(diagnostics=(exc.diagnostic,))
    except Exception as exc:
        diagnostic = Diagnostic(
            code=TableErrorCode.INTERNAL_ERROR.value,
            message=f"Unexpected Talika internal error: {type(exc).__name__}",
            schema_name=schema_name,
            source_uri=source_uri,
            hint="Inspect diagnostic.cause and report this as a Talika bug.",
            cause=exc,
        )
        return ValidationResult(diagnostics=(diagnostic,))
    return ValidationResult(records=tuple(records))


class SchemaRuntime(Protocol):
    """Structural type shared by orientation and lifecycle stage modules."""

    __schema_plan__: ClassVar[SchemaPlan]
    __variants__: ClassVar[Mapping[Any, type]]

    @classmethod
    def _validate_error_mode(cls, error_mode: str) -> ErrorMode: ...

    @classmethod
    def _parse_context(cls, context: Any) -> Any: ...

    @classmethod
    def _prepare_table(cls, datatable: Any, parse_context: Any) -> Any: ...

    @classmethod
    def _report(cls, error: TableError, errors: ErrorCollector) -> None: ...

    @classmethod
    def _raise_collected(cls, errors: ErrorCollector) -> None: ...

    @classmethod
    def _reject_duplicates(cls, cells: Any, errors: ErrorCollector) -> None: ...

    @classmethod
    def _validate_table_labels(cls, cells: Any, errors: ErrorCollector) -> None: ...

    @classmethod
    def _validate_required_presence(
        cls, labels: Any, errors: ErrorCollector, **kwargs: Any
    ) -> None: ...

    @classmethod
    def _cell_for_field(cls, declared: Any, cells: Any) -> Any: ...

    @classmethod
    def _value_for(cls, declared: Any, **kwargs: Any) -> Any: ...

    @classmethod
    def _validate_id(
        cls, value: Any, cell: Any, declared: Any, errors: ErrorCollector
    ) -> bool: ...

    @classmethod
    def _select_record_schema(cls, cells: Any, **kwargs: Any) -> Any: ...

    @classmethod
    def _reject_inapplicable_values(
        cls, record_cls: Any, cells: Any, **kwargs: Any
    ) -> dict[str, Any]: ...

    @classmethod
    def _parse_record_values(
        cls, record_cls: Any, cells: Any, **kwargs: Any
    ) -> Any: ...

    @classmethod
    def _finalize_records(
        cls, records: Any, *args: Any, **kwargs: Any
    ) -> list[Any]: ...
