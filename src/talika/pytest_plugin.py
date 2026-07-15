"""Pytest integration for talika.

Installing the package registers a ``talika`` fixture. The fixture is a
small facade around schema classmethods, useful when pytest dependency
injection keeps BDD step functions cleaner.

!!! info
    Direct schema parsing remains independent from pytest. This plugin adds
    convenience only; it does not create a separate table lifecycle.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, TypeVar, overload

import pytest

from .context import ParseContext
from .diagnostics import ValidationResult
from .schema import BaseTable
from .table import RawTable, TableCell, TableData

TableT = TypeVar("TableT", bound=BaseTable)
OutputT = TypeVar("OutputT")


class TalikaParser:
    """Convenience facade exposed through the ``talika`` fixture.

    This facade intentionally delegates to the schema class. It does not own
    a second parser, registry, or pytest-specific table lifecycle.

    !!! example
        ```python
        def step(datatable, talika):
            users = talika.parse(datatable, schema=UserTable)
        ```
    """

    def __init__(self) -> None:
        self._bound_tables: dict[int, tuple[object, TableData]] = {}

    def _bind_table(self, raw: object, table: TableData) -> None:
        self._bound_tables[id(raw)] = (raw, table)

    def _source_table(self, datatable: RawTable | TableData) -> RawTable | TableData:
        if isinstance(datatable, TableData):
            return datatable
        bound = self._bound_tables.get(id(datatable))
        if bound is not None and bound[0] is datatable:
            return bound[1]
        return datatable

    def _clear_bound_tables(self) -> None:
        self._bound_tables.clear()

    def parse(
        self,
        datatable: RawTable | TableData,
        *,
        schema: type[TableT],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a table into validated schema records.

        Args:
            datatable: Raw pytest-bdd table or source-aware ``TableData``.
            schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of ``schema``.

        Raises:
            ValueError: If ``error_mode`` is unsupported.
            TableError: If parsing or validation fails in first-error mode.
            TableErrors: If collect mode finds error-severity failures.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` and records are still returned.

        !!! info
            This method delegates directly to ``schema.parse``.

        """
        return schema.parse(
            self._source_table(datatable),
            context=context,
            error_mode=error_mode,
        )

    @overload
    def parse_as(
        self,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT],
        *,
        schema: type[BaseTable],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT]: ...

    @overload
    def parse_as(
        self,
        datatable: RawTable | TableData,
        output_model: None = None,
        *,
        schema: type[TableT],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]: ...

    def parse_as(
        self,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT] | None = None,
        *,
        schema: type[BaseTable],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT] | list[Any]:
        """Parse a table and convert records into public output objects.

        Args:
            datatable: Raw pytest-bdd table or source-aware ``TableData``.
            output_model: Optional callable receiving parsed record fields as
                keyword arguments. When omitted, use configured output hooks.
            schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Converted output objects.

        Raises:
            TypeError: If ``output_model`` is not callable.
            ValueError: If no explicit or configured conversion exists.
            TableError: If parsing, validation, or output construction fails.
            TableErrors: If collect mode finds multiple failures.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` and converted objects are still returned.

        """
        return schema.parse_as(
            self._source_table(datatable),
            output_model,
            context=context,
            error_mode=error_mode,
        )

    def validate(
        self,
        datatable: RawTable | TableData,
        *,
        schema: type[TableT],
        context: Mapping[str, Any] | ParseContext | None = None,
    ) -> ValidationResult[TableT]:
        """Validate a table without output conversion or raised table errors.

        Args:
            datatable: Raw pytest-bdd table or source-aware ``TableData``.
            schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
            context: Optional project data or existing parse context.

        Returns:
            Complete schema records and ordered table diagnostics.
            Warning-only results remain valid and retain records.

        """
        return schema.validate(self._source_table(datatable), context=context)


def _talika_parsers(step_func_args: Mapping[str, object]) -> list[TalikaParser]:
    return [
        value for value in step_func_args.values() if isinstance(value, TalikaParser)
    ]


@pytest.hookimpl(optionalhook=True)
def pytest_bdd_before_step_call(
    feature: Any,
    step: Any,
    step_func_args: dict[str, object],
) -> None:
    """Bind pytest-bdd feature provenance to the step's raw datatable."""
    raw = step_func_args.get("datatable")
    data_table = getattr(step, "datatable", None)
    parsers = _talika_parsers(step_func_args)
    if raw is None or data_table is None or not parsers:
        return

    raw_rows = list(raw) if isinstance(raw, (list, tuple)) else []
    source_rows = getattr(data_table, "rows", ())
    if len(raw_rows) != len(source_rows):
        return

    rows: list[list[TableCell]] = []
    for raw_row, source_row in zip(raw_rows, source_rows, strict=True):
        raw_values = list(raw_row) if isinstance(raw_row, (list, tuple)) else []
        source_cells = getattr(source_row, "cells", ())
        if len(raw_values) != len(source_cells):
            return
        cells: list[TableCell] = []
        for value, source_cell in zip(raw_values, source_cells, strict=True):
            if not isinstance(value, str):
                return
            location = source_cell.location
            cells.append(
                TableCell(
                    value=value,
                    source_row=location.line,
                    source_column=location.column,
                    source_value=value,
                )
            )
        rows.append(cells)

    source = Path(feature.filename).resolve()
    table = TableData.from_cells(rows, source=source)
    for parser in parsers:
        parser._bind_table(raw, table)


def _clear_step_parsers(step_func_args: Mapping[str, object]) -> None:
    for parser in _talika_parsers(step_func_args):
        parser._clear_bound_tables()


@pytest.hookimpl(optionalhook=True)
def pytest_bdd_after_step(step_func_args: dict[str, object]) -> None:
    """Clear source bindings after a successful pytest-bdd step."""
    _clear_step_parsers(step_func_args)


@pytest.hookimpl(optionalhook=True)
def pytest_bdd_step_error(step_func_args: dict[str, object]) -> None:
    """Clear source bindings after a failed pytest-bdd step."""
    _clear_step_parsers(step_func_args)


@pytest.fixture
def talika() -> TalikaParser:
    """Provide the schema parsing facade to pytest tests.

    Returns:
        A new ``TalikaParser`` facade.

    !!! info
        Each fixture instance briefly stores pytest-bdd provenance for the
        current step, then clears it after success or failure. Instance-local
        state prevents source bindings from leaking between parallel tests.

    """
    return TalikaParser()
