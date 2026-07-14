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

from collections.abc import Mapping
from typing import Any, TypeVar

from .context import ParseContext
from .diagnostics import ValidationResult
from .schema import BaseTable
from .table import RawTable, TableData

TableT = TypeVar("TableT", bound=BaseTable)


def parse_table(
    schema: type[BaseTable],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[Any]:
    """Parse a Gherkin data table using a schema class.

    This is the functional equivalent of ``schema.parse(datatable)``. It is
    useful in codebases that prefer explicit parser functions over classmethod
    calls, and it returns the same public result as the schema method,
    including output-model conversion when configured.

    Args:
        schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
        datatable: Raw ``list[list[str]]`` table or source-aware ``TableData``.
        context: Optional project data or existing parse context.
        error_mode: ``"first"`` for fail-fast parsing or ``"collect"`` for
            aggregate diagnostics.

    Returns:
        Parsed public result objects from ``schema.parse``.

    !!! example
        ```python
        users = parse_table(UserTable, datatable)
        ```

    """
    return schema.parse(datatable, context=context, error_mode=error_mode)


def parse_table_records(
    schema: type[TableT],
    datatable: RawTable | TableData,
    *,
    context: Mapping[str, Any] | ParseContext | None = None,
    error_mode: str = "first",
) -> list[TableT]:
    """Parse a Gherkin data table and return validated schema record instances.

    This is the functional equivalent of ``schema.parse_records(datatable)``.
    It intentionally skips optional output-model conversion, making the return
    type useful for static type checkers and tests that need source metadata or
    intermediate schema records.

    Args:
        schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
        datatable: Raw ``list[list[str]]`` table or source-aware ``TableData``.
        context: Optional project data or existing parse context.
        error_mode: ``"first"`` for fail-fast parsing or ``"collect"`` for
            aggregate diagnostics.

    Returns:
        Validated instances of ``schema``.

    !!! warning
        Use ``parse_table`` or ``Schema.parse`` when callers should receive
        configured output-model objects instead of intermediate schema records.

    """
    return schema.parse_records(datatable, context=context, error_mode=error_mode)


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
        A frozen validation result containing complete records or diagnostics.

    !!! note
        Schema declaration errors and API misuse still raise because they are
        not authored table-data diagnostics.

    """
    return schema.validate(datatable, context=context)
