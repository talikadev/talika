"""Functional parsing helpers for projects that prefer explicit APIs.

The schema methods remain the primary interface:

``UserTable.parse(datatable)``

Some teams prefer a parser-function style because it makes the schema an
argument rather than the object receiving the call. The helpers in this module
support that style without creating another parsing implementation.

!!! info
    These helpers are thin delegates. The schema class still owns orientation,
    validation, transformation, references, and output conversion.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, TypeVar, overload

from .context import ParseContext
from .diagnostics import ValidationResult
from .schema import BaseTable
from .table import RawTable, TableData

TableT = TypeVar("TableT", bound=BaseTable)
OutputT = TypeVar("OutputT")


def parse_table(
    schema: type[TableT],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[TableT]:
    """Parse a Gherkin data table using a schema class.

    This is the functional equivalent of ``schema.parse(datatable)``. It is
    useful in codebases that prefer explicit parser functions over classmethod
    calls. It always returns validated schema records; output conversion uses
    :func:`parse_table_as`.

    Args:
        schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
        datatable: Raw ``list[list[str]]`` table or source-aware ``TableData``.
        context: Optional project data or existing parse context.
        error_mode: ``"first"`` for fail-fast parsing or ``"collect"`` for
            aggregate diagnostics.

    Returns:
        Validated instances of ``schema``.

    Raises:
        ValueError: If ``error_mode`` is unsupported.
        SchemaDefinitionError: If the schema family is invalid.
        TableError: If parsing or validation fails in first-error mode.
        TableErrors: If collect mode finds error-severity failures.

    !!! note
        Warning-severity validation diagnostics are emitted as
        ``TalikaWarning`` and records are still returned.

    !!! example
        ```python
        users = parse_table(UserTable, datatable)
        ```

    """
    return schema.parse(datatable, context=context, error_mode=error_mode)


@overload
def parse_table_as(
    schema: type[BaseTable],
    datatable: RawTable | TableData,
    output_model: Callable[..., OutputT],
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[OutputT]: ...


@overload
def parse_table_as(
    schema: type[BaseTable],
    datatable: RawTable | TableData,
    output_model: None = None,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[Any]: ...


def parse_table_as(
    schema: type[BaseTable],
    datatable: RawTable | TableData,
    output_model: Callable[..., OutputT] | None = None,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[OutputT] | list[Any]:
    """Parse a Gherkin data table and build public output objects.

    This is the functional equivalent of ``schema.parse_as(...)``. An explicit
    callable overrides configured schema and variant output hooks. Omitting it
    uses the schema's ``output_model`` or custom ``build_output()``.

    Args:
        schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
        datatable: Raw ``list[list[str]]`` table or source-aware ``TableData``.
        output_model: Optional callable receiving parsed record fields as
            keyword arguments.
        context: Optional project data or existing parse context.
        error_mode: ``"first"`` for fail-fast parsing or ``"collect"`` for
            aggregate diagnostics.

    Returns:
        Converted public output objects.

    Raises:
        TypeError: If ``output_model`` is not callable.
        ValueError: If no explicit or configured output conversion exists.
        TableError: If parsing, validation, or output construction fails.
        TableErrors: If collect mode finds multiple failures.

    !!! note
        Warning-severity validation diagnostics are emitted as
        ``TalikaWarning`` and converted objects are still returned.

    """
    return schema.parse_as(
        datatable,
        output_model,
        context=context,
        error_mode=error_mode,
    )


def validate_table(
    schema: type[TableT],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
) -> ValidationResult[TableT]:
    """Validate a table and return records or diagnostics without raising.

    This is the functional equivalent of ``schema.validate(datatable)``.
    Output-model conversion is skipped, and invalid results never expose
    partially parsed records.

    Args:
        schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
        datatable: Raw string rows or source-aware ``TableData``.
        context: Optional project data or existing parse context.

    Returns:
        A frozen validation result containing complete records and ordered
        diagnostics. Warning-only results remain valid and retain records.

    !!! note
        Schema declaration errors and API misuse still raise because they are
        not authored table-data diagnostics.

    """
    return schema.validate(datatable, context=context)
