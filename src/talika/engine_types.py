"""Small shared runtime types used by parsing engine stages."""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, ClassVar, Generic, Protocol, TypeVar

from .diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    TalikaWarning,
    ValidationResult,
)
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors
from .schema_plan import ErrorMode, SchemaPlan

INVALID = object()
ResultT = TypeVar("ResultT")


@dataclass
class DiagnosticCollector:
    """Collect lifecycle diagnostics while preserving parser error mode."""

    mode: ErrorMode
    items: list[TableError] = field(default_factory=list)

    @property
    def errors(self) -> tuple[TableError, ...]:
        """Return error-severity items in discovery order."""
        return tuple(
            item for item in self.items if item.severity is DiagnosticSeverity.ERROR
        )

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return every collected diagnostic in discovery order."""
        return tuple(item.diagnostic for item in self.items)


@dataclass(frozen=True)
class LifecycleOutcome(Generic[ResultT]):
    """Carry successful values and non-failing lifecycle diagnostics."""

    values: list[ResultT]
    diagnostics: tuple[Diagnostic, ...] = ()


def error_diagnostic(diagnostic: Diagnostic) -> Diagnostic:
    """Return ``diagnostic`` with error severity and preserved value presence."""
    values: dict[str, Any] = {
        "code": diagnostic.code,
        "message": diagnostic.message,
        "severity": DiagnosticSeverity.ERROR,
        "hint": diagnostic.hint,
        "schema_name": diagnostic.schema_name,
        "field_name": diagnostic.field_name,
        "field_label": diagnostic.field_label,
        "source_uri": diagnostic.source_uri,
        "row": diagnostic.row,
        "column": diagnostic.column,
        "cause": diagnostic.cause,
    }
    if diagnostic.has_item_id:
        values["item_id"] = diagnostic.item_id
    if diagnostic.has_source_value:
        values["source_value"] = diagnostic.source_value
    if diagnostic.has_logical_value:
        values["logical_value"] = diagnostic.logical_value
    return Diagnostic(**values)


def _emit_warnings(diagnostics: tuple[Diagnostic, ...]) -> None:
    """Emit warning-severity diagnostics through Python's warnings system."""
    for diagnostic in diagnostics:
        if diagnostic.severity is DiagnosticSeverity.WARNING:
            warnings.warn(TalikaWarning(diagnostic), stacklevel=4)


def raising_result(
    operation: Callable[[], LifecycleOutcome[ResultT]],
    *,
    schema_name: str,
    source_uri: str | None,
) -> list[ResultT]:
    """Run a raising parser operation and emit non-failing warnings."""
    try:
        outcome = operation()
    except TableErrors as exc:
        errors = tuple(
            item for item in exc.errors if item.severity is DiagnosticSeverity.ERROR
        )
        if errors:
            _emit_warnings(exc.diagnostics)
            raise TableErrors(errors) from exc
        promoted = tuple(
            TableError.from_diagnostic(error_diagnostic(item))
            for item in exc.diagnostics
        )
        raise TableErrors(promoted) from exc
    except TableError as exc:
        if exc.severity is DiagnosticSeverity.WARNING:
            raise TableError.from_diagnostic(error_diagnostic(exc.diagnostic)) from exc
        raise
    except SchemaDefinitionError:
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
    _emit_warnings(outcome.diagnostics)
    return outcome.values


def non_raising_result(
    operation: Callable[[], LifecycleOutcome[ResultT]],
    *,
    schema_name: str,
    source_uri: str | None,
) -> ValidationResult[ResultT]:
    """Run collect-mode record parsing and normalize its public result."""
    try:
        outcome = operation()
    except SchemaDefinitionError:
        raise
    except TableErrors as exc:
        if not any(
            item.severity is DiagnosticSeverity.ERROR for item in exc.diagnostics
        ):
            return ValidationResult(
                diagnostics=tuple(error_diagnostic(item) for item in exc.diagnostics)
            )
        return ValidationResult(diagnostics=exc.diagnostics)
    except TableError as exc:
        diagnostic = (
            error_diagnostic(exc.diagnostic)
            if exc.severity is DiagnosticSeverity.WARNING
            else exc.diagnostic
        )
        return ValidationResult(diagnostics=(diagnostic,))
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
    return ValidationResult(
        records=tuple(outcome.values),
        diagnostics=outcome.diagnostics,
    )


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
    def _report(
        cls,
        error: TableError,
        errors: DiagnosticCollector,
        *,
        allow_warning: bool = False,
    ) -> object: ...

    @classmethod
    def _raise_collected(cls, errors: DiagnosticCollector) -> None: ...

    @classmethod
    def _reject_duplicates(cls, cells: Any, errors: DiagnosticCollector) -> None: ...

    @classmethod
    def _validate_table_labels(
        cls, cells: Any, errors: DiagnosticCollector
    ) -> None: ...

    @classmethod
    def _validate_required_presence(
        cls, labels: Any, errors: DiagnosticCollector, **kwargs: Any
    ) -> None: ...

    @classmethod
    def _cell_for_field(cls, declared: Any, cells: Any) -> Any: ...

    @classmethod
    def _value_for(cls, declared: Any, **kwargs: Any) -> Any: ...

    @classmethod
    def _validate_id(
        cls, value: Any, cell: Any, declared: Any, errors: DiagnosticCollector
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
