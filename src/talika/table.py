"""Source-aware table values used by parsing and table transformations.

The public schema API accepts ordinary ``list[list[str]]`` values because that
is what pytest-bdd supplies to step functions. Internally, every raw string is
wrapped in :class:`TableCell` so later stages can report the location of the
original feature-file cell.

Projects that implement a custom table transformation may use these classes
directly. A transformed cell should normally be created with
``source_cell.with_value(new_value)``. That keeps diagnostics attached to the
cell syntax the user actually wrote.

!!! info
    Raw input is accepted as ordinary ``Sequence[Sequence[str]]``. The parser
    upgrades it to ``TableData`` before running transformations or schema
    validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

RawTable = Sequence[Sequence[str]]


@dataclass(frozen=True)
class TableCell:
    """One current table value and the feature cell from which it originated.

    Attributes:
        value: The value currently consumed by schema parsing. A transformer
            may change this value.
        source_row: One-based row number of the original BDD table cell.
        source_column: One-based column number of the original BDD table cell.
        source_value: The exact value before any table transformation.

    A transformer may produce several cells from one source cell. Each new
    cell can therefore have a different ``value`` while sharing the same
    source location and ``source_value``.

    !!! example
        ```python
        expanded = source_cell.with_value("Article")
        assert expanded.source_value == "3:Article"
        ```

    """

    value: str
    source_row: int
    source_column: int
    source_value: str

    @classmethod
    def from_value(cls, value: str, *, row: int, column: int) -> TableCell:
        """Create an untransformed cell at a source location.

        Args:
            value: Raw text from the table.
            row: One-based source row.
            column: One-based source column.

        Returns:
            A ``TableCell`` whose current value and source value are the same.

        !!! info
            One-based coordinates match feature-file diagnostics and user
            expectations when reading BDD tables.

        """
        return cls(
            value=value,
            source_row=row,
            source_column=column,
            source_value=value,
        )

    def with_value(self, value: str) -> TableCell:
        """Return a changed cell that still points to this cell's source.

        This is the preferred way for a table transformer to replace or
        expand syntax. For example, a source cell containing ``3:Article``
        may produce three cells whose current value is ``Article`` while all
        three still point back to the original ``3:Article`` cell.

        Args:
            value: New logical value consumed by later parsing stages.

        Returns:
            A new ``TableCell`` with updated ``value`` and preserved source
            location/value.

        !!! warning
            Constructing fresh cells manually can lose original coordinates.
            Use this method inside transformers whenever a logical value
            derives from an existing source cell.

        """
        return TableCell(
            value=value,
            source_row=self.source_row,
            source_column=self.source_column,
            source_value=self.source_value,
        )


@dataclass(frozen=True)
class TableData:
    """An immutable, source-aware representation of a BDD data table.

    ``TableData`` intentionally provides only a few explicit operations. It is
    not a second table-processing framework. Its job is to carry current cell
    values and original source locations through the schema lifecycle.

    Attributes:
        rows: Immutable rows of immutable ``TableCell`` tuples.

    !!! info
        ``TableData`` is immutable by convention and dataclass shape, but the
        values it contains may still be arbitrary strings produced by project
        transformations.

    """

    rows: tuple[tuple[TableCell, ...], ...]

    @classmethod
    def from_rows(cls, rows: RawTable) -> TableData:
        """Wrap ordinary string rows while recording source locations.

        Args:
            rows: Raw BDD table rows, typically from pytest-bdd.

        Returns:
            A source-aware ``TableData`` instance.

        !!! example
            ```python
            table = TableData.from_rows([["name"], ["Alice"]])
            assert table.cell(2, 1).source_row == 2
            ```

        """
        return cls(
            rows=tuple(
                tuple(
                    TableCell.from_value(value, row=row_number, column=column_number)
                    for column_number, value in enumerate(row, start=1)
                )
                for row_number, row in enumerate(rows, start=1)
            )
        )

    @classmethod
    def from_cells(cls, rows: Sequence[Sequence[TableCell]]) -> TableData:
        """Build a table from cells whose source information already exists.

        Custom transformers use this constructor after arranging existing or
        transformed cells into their new logical table shape.

        Args:
            rows: Logical rows of source-aware cells.

        Returns:
            A ``TableData`` instance containing immutable row/cell tuples.

        !!! warning
            This constructor trusts that cells already preserve useful source
            information. Prefer ``cell.with_value(...)`` when transforming.

        """
        return cls(rows=tuple(tuple(row) for row in rows))

    @classmethod
    def ensure(cls, table: RawTable | TableData) -> TableData:
        """Return ``table`` as ``TableData``.

        Args:
            table: Existing source-aware table or raw string rows.

        Returns:
            ``table`` unchanged when already source-aware, otherwise a new
            ``TableData`` created from raw rows.

        !!! info
            Schema parsing calls this at the boundary so downstream code can
            work only with source-aware cells.

        """
        if isinstance(table, cls):
            return table
        return cls.from_rows(cast(RawTable, table))

    def cell(self, row: int, column: int) -> TableCell:
        """Return a cell using one-based row and column indexes.

        One-based indexes match the coordinates shown in BDD table errors and
        make transformer code easier to compare with a feature file.

        Args:
            row: One-based row number.
            column: One-based column number.

        Returns:
            The requested ``TableCell``.

        Raises:
            IndexError: If indexes are less than one or outside the table.

        !!! warning
            This helper is for human-facing coordinates. Use ``rows`` directly
            for zero-based Python iteration.

        """
        if row < 1 or column < 1:
            raise IndexError("TableData cell indexes start at 1")
        try:
            return self.rows[row - 1][column - 1]
        except IndexError as exc:
            message = f"No table cell exists at row {row}, column {column}"
            raise IndexError(message) from exc

    def to_rows(self) -> list[list[str]]:
        """Return current values as ordinary mutable string rows.

        Returns:
            A new ``list[list[str]]`` containing each cell's current value.

        !!! info
            Source metadata is intentionally dropped. This method is useful for
            display, debugging, and compatibility with code expecting raw rows.

        """
        return [[cell.value for cell in row] for row in self.rows]
