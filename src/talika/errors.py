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
    REFERENCE_FAILED = "reference_failed"
    RECORD_VALIDATION_FAILED = "record_validation_failed"
    TABLE_VALIDATION_FAILED = "table_validation_failed"
    OUTPUT_FAILED = "output_failed"


class TableError(ValueError):
    """Represent one source-aware table diagnostic.

    The structured attributes are intentionally public. Test runners and
    editor integrations can inspect them without parsing the human-readable
    error message.

    Attributes:
        message: Human-readable failure summary.
        schema: Schema display name when known.
        field: Schema attribute name associated with the failure.
        row: One-based source row.
        column: One-based source column.
        item_id: Parsed item ID when the failing record has one.
        value: Offending source value, or an internal unset sentinel.
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
        row: int | None = None,
        column: int | None = None,
        item_id: Any | None = None,
        value: Any = _UNSET,
        code: TableErrorCode | str = TableErrorCode.TABLE_ERROR,
        hint: str | None = None,
    ) -> None:
        """Initialize one structured table diagnostic.

        Args:
            message: Human-readable failure summary.
            schema: Schema class or display name associated with the failure.
            field: Schema attribute name associated with the failure.
            row: One-based source row.
            column: One-based source column.
            item_id: Parsed item identifier when available.
            value: Offending source value. Omit to represent "no value".
            code: Stable diagnostic category.
            hint: Optional user-facing remediation.

        !!! warning
            Passing ``value=None`` means the offending value is explicitly
            ``None``. Omit ``value`` entirely when no value should be reported.

        """
        self.message = message
        if isinstance(schema, type):
            self.schema = schema.__dict__.get(
                "__schema_display_name__", schema.__name__
            )
        else:
            self.schema = schema
        self.field = field
        self.row = row
        self.column = column
        self.item_id = item_id
        self.value = value
        self.code = code.value if isinstance(code, TableErrorCode) else str(code)
        self.hint = hint
        super().__init__(self.__str__())

    @classmethod
    def from_cell(
        cls,
        message: str,
        cell: TableCell,
        *,
        schema: type | str | None = None,
        field: str | None = None,
        item_id: Any | None = None,
        code: TableErrorCode | str = TableErrorCode.TABLE_ERROR,
        hint: str | None = None,
    ) -> TableError:
        """Create an error located at a cell's original source.

        This helper is useful inside custom table transformations. It reports
        the source syntax, not merely the current transformed value.

        Args:
            message: Human-readable failure summary.
            cell: Source-aware cell that caused the error.
            schema: Schema class or display name associated with the failure.
            field: Schema attribute name associated with the failure.
            item_id: Parsed item identifier when available.
            code: Stable diagnostic category.
            hint: Optional user-facing remediation.

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
            row=cell.source_row,
            column=cell.source_column,
            item_id=item_id,
            value=cell.source_value,
            code=code,
            hint=hint,
        )

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
            details.append(f"item_id={self.item_id!r}")
        if self.value is not _UNSET:
            details.append(f"value={self.value!r}")
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
        return self.value is not _UNSET


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
    """Report an invalid schema declaration at class creation time.

    Attributes:
        message: Human-readable declaration problem.
        schema: Name of the schema being created when available.

    !!! warning
        These errors indicate Python schema code is ambiguous, not that a
        feature file table contains invalid data.

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
        detail = f" (schema={schema})" if schema else ""
        super().__init__(f"{message}{detail}")
