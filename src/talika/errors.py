"""Structured table errors with source location details.

The package raises errors that are useful both to humans and to tools. Human
messages explain what failed; stable codes and source coordinates let pytest,
CLIs, and editor integrations render diagnostics without scraping strings.

!!! info
    Row and column coordinates are one-based and refer to the original source
    table whenever a ``TableCell`` is available.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import Enum
from typing import Any

from .diagnostics import Diagnostic, DiagnosticSeverity, stable_text_value
from .table import TableCell

_UNSET = object()


class TableErrorCode(str, Enum):
    """Stable machine-readable categories for table failures.

    Human-readable messages may improve over time. Integrations should use
    these codes when grouping diagnostics or deciding how to present them.

    !!! warning
        Codes are part of the supported diagnostic contract. Prefer adding new
        codes over changing existing meanings.
    """

    TABLE_ERROR = "table_error"
    INVALID_TABLE_INPUT = "invalid_table_input"
    SCHEMA_DEFINITION = "schema_definition"
    INVALID_CONTEXT = "invalid_context"
    TABLE_EMPTY = "table_empty"
    HEADER_EMPTY = "header_empty"
    RAGGED_ROW = "ragged_row"
    DUPLICATE_LABEL = "duplicate_label"
    UNKNOWN_FIELD = "unknown_field"
    MISSING_REQUIRED = "missing_required"
    EMPTY_REQUIRED = "empty_required"
    EMPTY_OPTIONAL = "empty_optional"
    DEFAULT_FACTORY_FAILED = "default_factory_failed"
    PARSER_FAILED = "parser_failed"
    TRANSFORM_FAILED = "transform_failed"
    INVALID_TRANSFORM = "invalid_transform"
    UNKNOWN_VARIANT = "unknown_variant"
    INAPPLICABLE_FIELD = "inapplicable_field"
    DUPLICATE_ID = "duplicate_id"
    INVALID_ID = "invalid_id"
    REFERENCE_FAILED = "reference_failed"
    EXPANSION_LIMIT = "expansion_limit"
    CHECKER_FAILED = "checker_failed"
    RECORD_VALIDATION_FAILED = "record_validation_failed"
    TABLE_VALIDATION_FAILED = "table_validation_failed"
    OUTPUT_FAILED = "output_failed"
    INTERNAL_ERROR = "internal_error"


class TableError(ValueError):
    """Represent one source-aware table diagnostic.

    The structured attributes are intentionally public. Test runners and
    editor integrations can inspect them without parsing the human-readable
    error message.

    Attributes:
        message: Human-readable failure summary.
        schema: Schema display name when known.
        field: Legacy human-facing field label associated with the failure.
        field_name: Python attribute name associated with the failure.
        field_label: Authored field label associated with the failure.
        source_uri: URI of the source document when known.
        row: One-based source row.
        column: One-based source column.
        item_id: Parsed item ID when the failing record has one.
        value: Legacy alias for the offending source value.
        code: Stable machine-readable diagnostic code.
        hint: Optional remediation text.

    !!! info
        ``TableError`` inherits ``ValueError`` so project validators can
        raise ordinary value errors while the schema lifecycle wraps them in a
        table-aware diagnostic.

    """

    def __init__(
        self,
        message: str,
        *,
        schema: type | str | None = None,
        field: str | None = None,
        field_name: str | None = None,
        field_label: str | None = None,
        source_uri: str | None = None,
        row: int | None = None,
        column: int | None = None,
        item_id: Any = _UNSET,
        value: Any = _UNSET,
        source_value: Any = _UNSET,
        logical_value: Any = _UNSET,
        code: TableErrorCode | str = TableErrorCode.TABLE_ERROR,
        hint: str | None = None,
        severity: DiagnosticSeverity | str = DiagnosticSeverity.ERROR,
        cause: BaseException | None = None,
    ) -> None:
        """Initialize one structured table diagnostic.

        Args:
            message: Human-readable failure summary.
            schema: Schema class or display name associated with the failure.
            field: Legacy human-facing field label.
            field_name: Python attribute name for the declared field.
            field_label: Authored canonical or alias label for the field.
            source_uri: URI of the source document when known.
            row: One-based source row.
            column: One-based source column.
            item_id: Parsed item identifier when available.
            value: Offending source value. Omit to represent "no value".
            source_value: Original authored value, superseding ``value``.
            logical_value: Current value after table transformation.
            code: Stable diagnostic category.
            hint: Optional user-facing remediation.
            severity: Diagnostic severity.
            cause: Original exception when this error wraps another failure.

        !!! warning
            Passing ``value=None`` means the offending value is explicitly
            ``None``. Omit ``value`` entirely when no value should be reported.

        """
        if isinstance(schema, type):
            schema_name = schema.__dict__.get(
                "__schema_display_name__", schema.__name__
            )
        else:
            schema_name = schema
        if field_label is None:
            field_label = field
        if source_value is _UNSET and value is not _UNSET:
            source_value = value

        diagnostic_kwargs: dict[str, Any] = {
            "code": code.value if isinstance(code, TableErrorCode) else str(code),
            "message": message,
            "severity": severity,
            "hint": hint,
            "schema_name": schema_name,
            "field_name": field_name,
            "field_label": field_label,
            "source_uri": source_uri,
            "row": row,
            "column": column,
            "cause": cause,
        }
        # ``TableError`` historically used ``None`` as its omitted item ID.
        # Preserve that compatibility while ``Diagnostic`` itself can still
        # represent an explicit ``None`` through its sentinel-aware API.
        if item_id is not _UNSET and item_id is not None:
            diagnostic_kwargs["item_id"] = item_id
        if source_value is not _UNSET:
            diagnostic_kwargs["source_value"] = source_value
        if logical_value is not _UNSET:
            diagnostic_kwargs["logical_value"] = logical_value
        self.diagnostic = Diagnostic(**diagnostic_kwargs)
        super().__init__(self.__str__())
        if cause is not None:
            self.__cause__ = cause

    @classmethod
    def from_diagnostic(cls, diagnostic: Diagnostic) -> TableError:
        """Create a compatibility exception around an existing diagnostic."""
        error = cls.__new__(cls)
        error.diagnostic = diagnostic
        ValueError.__init__(error, error.__str__())
        if diagnostic.cause is not None:
            error.__cause__ = diagnostic.cause
        return error

    @classmethod
    def from_cell(
        cls,
        message: str,
        cell: TableCell,
        *,
        schema: type | str | None = None,
        field: str | None = None,
        field_name: str | None = None,
        field_label: str | None = None,
        source_uri: str | None = None,
        item_id: Any = _UNSET,
        code: TableErrorCode | str = TableErrorCode.TABLE_ERROR,
        hint: str | None = None,
        severity: DiagnosticSeverity | str = DiagnosticSeverity.ERROR,
        cause: BaseException | None = None,
    ) -> TableError:
        """Create an error located at a cell's original source.

        This helper is useful inside custom table transformations. It reports
        the source syntax, not merely the current transformed value.

        Args:
            message: Human-readable failure summary.
            cell: Source-aware cell that caused the error.
            schema: Schema class or display name associated with the failure.
            field: Legacy human-facing field label.
            field_name: Python attribute name for the declared field.
            field_label: Authored canonical or alias label for the field.
            source_uri: Source document URI, overriding the cell URI.
            item_id: Parsed item identifier when available.
            code: Stable diagnostic category.
            hint: Optional user-facing remediation.
            severity: Diagnostic severity.
            cause: Original exception when this error wraps another failure.

        Returns:
            A ``TableError`` populated from ``cell`` source coordinates.

        !!! example
            ```python
            raise TableError.from_cell(
                "Invalid compact range",
                source_cell,
                schema=ContentTable,
            )
            ```

        """
        return cls(
            message,
            schema=schema,
            field=field,
            field_name=field_name,
            field_label=field_label,
            source_uri=source_uri or cell.source_uri,
            row=cell.source_row,
            column=cell.source_column,
            item_id=item_id,
            source_value=cell.source_value,
            logical_value=cell.value,
            code=code,
            hint=hint,
            severity=severity,
            cause=cause,
        )

    @property
    def message(self) -> str:
        """Return the human-readable failure message."""
        return self.diagnostic.message

    @property
    def schema(self) -> str | None:
        """Return the schema display name when known."""
        return self.diagnostic.schema_name

    @property
    def field(self) -> str | None:
        """Return the legacy human-facing field identifier."""
        return self.diagnostic.field_label or self.diagnostic.field_name

    @property
    def field_name(self) -> str | None:
        """Return the declared Python field name when known."""
        return self.diagnostic.field_name

    @property
    def field_label(self) -> str | None:
        """Return the authored field label when known."""
        return self.diagnostic.field_label

    @property
    def source_uri(self) -> str | None:
        """Return the source document URI when known."""
        return self.diagnostic.source_uri

    @property
    def row(self) -> int | None:
        """Return the one-based source row when known."""
        return self.diagnostic.row

    @property
    def column(self) -> int | None:
        """Return the one-based source column when known."""
        return self.diagnostic.column

    @property
    def item_id(self) -> Any | None:
        """Return the parsed item identifier when present."""
        return self.diagnostic.item_id

    @property
    def has_item_id(self) -> bool:
        """Return whether an item identifier is present."""
        return self.diagnostic.has_item_id

    @property
    def value(self) -> Any | None:
        """Return the legacy alias for the original source value."""
        return self.diagnostic.source_value

    @property
    def source_value(self) -> Any | None:
        """Return the original authored value when present."""
        return self.diagnostic.source_value

    @property
    def logical_value(self) -> Any | None:
        """Return the current transformed value when present."""
        return self.diagnostic.logical_value

    @property
    def code(self) -> str:
        """Return the stable machine-readable diagnostic code."""
        return self.diagnostic.code

    @property
    def hint(self) -> str | None:
        """Return optional remediation text."""
        return self.diagnostic.hint

    @property
    def severity(self) -> DiagnosticSeverity:
        """Return the diagnostic severity."""
        return self.diagnostic.severity

    def __str__(self) -> str:
        """Return a compact message with structured context appended.

        Returns:
            The human-facing diagnostic text used by ``ValueError`` and CLI
            text output.

        !!! info
            The string is intentionally readable, but integrations should
            prefer attributes such as ``code``, ``row``, and ``field``.

        """
        details = []
        details.append(f"code={self.code}")
        if self.schema is not None:
            details.append(f"schema={self.schema}")
        if self.field is not None:
            details.append(f"field={self.field!r}")
        if self.row is not None:
            details.append(f"row={self.row}")
        if self.column is not None:
            details.append(f"column={self.column}")
        if self.item_id is not None:
            details.append(f"item_id={stable_text_value(self.item_id)}")
        if self.diagnostic.has_source_value:
            details.append(f"value={stable_text_value(self.value)}")
        if self.logical_value != self.value and self.diagnostic.has_logical_value:
            details.append(f"logical_value={stable_text_value(self.logical_value)}")
        if self.source_uri is not None:
            details.append(f"source={self.source_uri}")
        location = f" ({', '.join(details)})" if details else ""
        hint = f". Hint: {self.hint}" if self.hint else ""
        return f"{self.message}{location}{hint}"

    @property
    def has_value(self) -> bool:
        """Return whether the diagnostic contains an offending value.

        Returns:
            ``True`` when ``value`` was supplied to the error constructor.

        !!! info
            This distinguishes an omitted value from an explicit ``None``.

        """
        return self.diagnostic.has_source_value


class TableErrors(ValueError):
    """Aggregate raised when collect mode finds several table failures.

    The contained errors retain their normal structured attributes and source
    locations. The aggregate itself is intentionally small so test runners,
    editor extensions, and command-line tools can render diagnostics in the
    format most useful to their users.

    Attributes:
        errors: Immutable tuple of collected ``TableError`` objects.

    !!! info
        Collection preserves discovery order so rendered diagnostics follow
        the table as closely as possible.

    """

    def __init__(self, errors: list[TableError] | tuple[TableError, ...]):
        """Initialize an aggregate of one or more diagnostics.

        Args:
            errors: Non-empty sequence of structured table errors.

        Raises:
            ValueError: If ``errors`` is empty.

        !!! warning
            Empty aggregates are rejected because their string representation
            would imply a failure without any actionable diagnostic.

        """
        if not errors:
            raise ValueError("TableErrors requires at least one error")
        self.errors = tuple(errors)
        super().__init__(self.__str__())

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        """Return underlying immutable diagnostics in discovery order."""
        return tuple(error.diagnostic for error in self.errors)

    def __iter__(self) -> Iterator[TableError]:
        """Iterate over diagnostics in discovery order.

        Returns:
            Iterator over contained ``TableError`` objects.

        !!! info
            This lets callers use ``list(exc)`` or simple loops without
            reaching into ``exc.errors`` directly.

        """
        return iter(self.errors)

    def __len__(self) -> int:
        """Return the number of collected diagnostics.

        Returns:
            Count of contained ``TableError`` objects.

        !!! info
            ``len(exc)`` mirrors the number reported in the aggregate message.

        """
        return len(self.errors)

    def __str__(self) -> str:
        """Return a numbered multi-line diagnostic summary.

        Returns:
            Human-readable text containing every collected error.

        !!! info
            The aggregate string is convenient for test failures; structured
            renderers should iterate over ``errors`` instead.

        """
        lines = [f"Table contains {len(self.errors)} errors:"]
        lines.extend(
            f"  {index}. {error}" for index, error in enumerate(self.errors, 1)
        )
        return "\n".join(lines)


class SchemaDefinitionError(ValueError):
    """Report an invalid schema declaration before table input is parsed.

    Attributes:
        message: Human-readable declaration problem.
        schema: Name of the schema being created when available.

    !!! warning
        These errors normally occur during class creation. Explicit variant
        families may be completed by decorators, so their family-wide checks
        run when the family is described or first finalized for parsing.

    """

    def __init__(self, message: str, *, schema: str | None = None) -> None:
        """Initialize a schema-definition failure.

        Args:
            message: Human-readable declaration problem.
            schema: Optional schema name associated with the problem.

        !!! info
            The formatted exception includes the schema name because these
            failures often occur during import before any table is parsed.

        """
        self.message = message
        self.schema = schema
        self.diagnostic = Diagnostic(
            code=TableErrorCode.SCHEMA_DEFINITION.value,
            message=message,
            schema_name=schema,
        )
        detail = f" (schema={schema})" if schema else ""
        super().__init__(f"{message}{detail}")
