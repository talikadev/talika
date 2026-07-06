"""Pytest integration for talika.

Installing the package registers a ``talika`` fixture. The fixture is a
small facade around schema classmethods, useful when pytest dependency
injection keeps BDD step functions cleaner.

!!! info
    Direct schema parsing remains independent from pytest. This plugin adds
    convenience only; it does not create a separate table lifecycle.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar

import pytest

from .context import ParseContext
from .schema import BaseTable
from .table import RawTable, TableData

TableT = TypeVar("TableT", bound=BaseTable)


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

    def parse(
        self,
        datatable: RawTable | TableData,
        *,
        schema: type[BaseTable],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]:
        """Parse a table with the requested schema.

        Args:
            datatable: Raw pytest-bdd table or source-aware ``TableData``.
            schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Public parse results, including output-model conversion when the
            schema configures one.

        !!! info
            This method delegates directly to ``schema.parse``.

        """
        return schema.parse(datatable, context=context, error_mode=error_mode)

    def parse_records(
        self,
        datatable: RawTable | TableData,
        *,
        schema: type[TableT],
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a table and return validated schema records.

        This mirrors ``schema.parse_records(...)`` for pytest and pytest-bdd
        steps that want type-checker-friendly schema instances instead of
        optional output-model conversion.

        Args:
            datatable: Raw pytest-bdd table or source-aware ``TableData``.
            schema: Concrete ``RowTable`` or ``ColumnTable`` subclass.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of ``schema``.

        !!! warning
            This bypasses output-model conversion by design. Use ``parse`` when
            the step should operate on the schema's public output objects.

        """
        return schema.parse_records(datatable, context=context, error_mode=error_mode)


@pytest.fixture
def talika() -> TalikaParser:
    """Provide the schema parsing facade to pytest tests.

    Returns:
        A new ``TalikaParser`` facade.

    !!! info
        The facade is stateless, so creating one per fixture request is cheap
        and avoids hidden state between tests.

    """
    return TalikaParser()
