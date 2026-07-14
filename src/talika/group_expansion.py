"""Declarative expansion helpers for grouped column-oriented Gherkin data tables.

The helpers in this module cover a common table shape: the first row contains
one key or ID cell per source group, and every other row contains one value for
that same group. A key cell may expand into several logical item columns. The
corresponding value cells are then repeated or copied across those columns.

The package supplies reusable mechanics and a few explicit rule objects. It
does not require these conventions. Projects can provide their own range and
repeat rules, or bypass this layer by overriding ``transform_table()``.

!!! info
    Expansion preserves source coordinates. Logical cells produced from a
    compact source cell still point back to the feature text that created them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from .context import ParseContext
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors
from .table import TableCell, TableData

_MAX_NUMERIC_RANGE_KEYS = 10_000


class _ExpansionLimitError(ValueError):
    """Signal that a built-in expansion exceeded its private safety bound."""


class RangeRule(Protocol):
    """Contract for turning one key cell into one or more logical keys.

    !!! info
        Custom range rules can implement any project convention, such as
        numeric ranges, alphabetic ranges, or domain-specific IDs.
    """

    def expand(self, cell: TableCell, context: ParseContext) -> Sequence[TableCell]:
        """Return logical key cells derived from ``cell``.

        A value that does not use the rule's special syntax should normally
        return ``[cell]``. Invalid recognized syntax may raise ``ValueError``;
        ``ColumnGroupExpander`` converts it into a source-aware
        ``TableError``.

        Args:
            cell: Source key cell from the grouped table.
            context: Parse context for the current schema parse.

        Returns:
            One or more ``TableCell`` objects representing logical item keys.

        !!! warning
            Return ``TableCell`` objects, not raw strings. Use
            ``cell.with_value(...)`` so diagnostics still point to the compact
            source cell.

        """


class RepeatRule(Protocol):
    """Contract for spreading one value cell across a logical key group.

    !!! info
        Repeat rules own value syntax only. The expander owns table shape,
        row iteration, count checks, and ``TableData`` construction.
    """

    def expand(
        self,
        cell: TableCell,
        expected_count: int,
        context: ParseContext,
    ) -> Sequence[TableCell]:
        """Return exactly ``expected_count`` logical value cells.

        A value without repeat syntax should normally be copied across the
        group. Invalid recognized syntax may raise ``ValueError``.

        Args:
            cell: Source value cell aligned with a grouped key cell.
            expected_count: Number of logical key cells in the group.
            context: Parse context for the current schema parse.

        Returns:
            Exactly ``expected_count`` logical value cells.

        !!! warning
            Count mismatches are treated as table errors because they would
            produce ambiguous record values.

        """


def _validate_separator(separator: str, rule_name: str) -> None:
    """Reject empty separators.

    Args:
        separator: Separator configured on a range or repeat rule.
        rule_name: Human-readable rule name for the error message.

    Raises:
        ValueError: If ``separator`` is empty.

    !!! warning
        Empty separators would make every cell look like rule syntax, so they
        are rejected at rule construction time.

    """
    if not separator:
        raise ValueError(f"{rule_name} separator cannot be empty")


@dataclass(frozen=True)
class NumericRange:
    """Expand inclusive ascending integer ranges such as ``1..4``.

    Values without the configured separator are treated as one literal key.
    Once the separator is present, both endpoints must be integers and the
    first endpoint must not exceed the second.

    Attributes:
        separator: Text separating the inclusive start and end values.

    !!! example
        ```python
        NumericRange(separator="..").expand(cell, context)
        ```

    """

    separator: str = ".."

    def __post_init__(self) -> None:
        """Validate the configured separator after dataclass initialization.

        Raises:
            ValueError: If ``separator`` is empty.

        !!! warning
            Validation happens eagerly so an invalid schema fails during setup
            rather than during the first feature parse.

        """
        _validate_separator(self.separator, type(self).__name__)

    def expand(self, cell: TableCell, context: ParseContext) -> list[TableCell]:
        """Return one literal key or an inclusive integer-key sequence.

        Args:
            cell: Key cell to inspect for range syntax.
            context: Parse context for the current schema parse.

        Returns:
            ``[cell]`` for literal values, or generated cells for every integer
            in the inclusive range.

        Raises:
            ValueError: If recognized range syntax is malformed or descending.

        !!! info
            Generated cells keep the source row, source column, and source
            value from ``cell``.

        """
        if self.separator not in cell.value:
            return [cell]

        parts = cell.value.split(self.separator)
        if len(parts) != 2:
            raise ValueError(f"Invalid numeric range {cell.value!r}")

        try:
            start, end = (int(part) for part in parts)
        except ValueError as exc:
            raise ValueError(f"Invalid numeric range {cell.value!r}") from exc

        if start > end:
            raise ValueError("Numeric range must be ascending")

        key_count = end - start + 1
        if key_count > _MAX_NUMERIC_RANGE_KEYS:
            raise _ExpansionLimitError(
                "Numeric range expands to "
                f"{key_count} keys; the maximum is {_MAX_NUMERIC_RANGE_KEYS}"
            )

        return [cell.with_value(str(value)) for value in range(start, end + 1)]


@dataclass(frozen=True)
class AlphabeticRange:
    """Expand inclusive ASCII letter ranges such as ``A-D`` or ``a-d``.

    Endpoints must each be one ASCII letter and use the same case. Values
    without the configured separator remain literal keys.

    Attributes:
        separator: Text separating the inclusive start and end letters.

    !!! warning
        Only single ASCII letters are supported. Use a custom range rule for
        multi-character labels, Unicode collation, or domain-specific IDs.

    """

    separator: str = "-"

    def __post_init__(self) -> None:
        """Validate the configured separator after dataclass initialization.

        Raises:
            ValueError: If ``separator`` is empty.

        !!! info
            Keeping this check on the rule object makes custom expander
            failures easier to diagnose.

        """
        _validate_separator(self.separator, type(self).__name__)

    def expand(self, cell: TableCell, context: ParseContext) -> list[TableCell]:
        """Return one literal key or an inclusive letter-key sequence.

        Args:
            cell: Key cell to inspect for alphabetic range syntax.
            context: Parse context for the current schema parse.

        Returns:
            ``[cell]`` for literal values, or generated cells for each ASCII
            letter in the inclusive range.

        Raises:
            ValueError: If recognized range syntax is malformed or descending.

        !!! info
            Case must match between endpoints so ``A-D`` and ``a-d`` are clear,
            while ``A-d`` is rejected.

        """
        if self.separator not in cell.value:
            return [cell]

        parts = cell.value.split(self.separator)
        valid_endpoints = all(
            len(part) == 1 and part.isascii() and part.isalpha() for part in parts
        )
        valid = (
            len(parts) == 2
            and valid_endpoints
            and parts[0].isupper() == parts[1].isupper()
        )
        if not valid:
            raise ValueError(f"Invalid alphabetic range {cell.value!r}")

        start, end = (ord(part) for part in parts)
        if start > end:
            raise ValueError("Alphabetic range must be ascending")

        return [cell.with_value(chr(value)) for value in range(start, end + 1)]


@dataclass(frozen=True)
class PrefixRepeat:
    """Expand count-before-value syntax such as ``3:Article``.

    If the text before the separator is not an integer, the entire value is
    treated as a literal and copied across the key group. This allows normal
    text containing the separator, such as ``News: Europe``, to remain valid.

    Attributes:
        separator: Text between repeat count and repeated value.

    !!! example
        ```python
        PrefixRepeat(separator=":")  # 3:Article
        ```

    """

    separator: str = ":"

    def __post_init__(self) -> None:
        """Validate the configured separator after dataclass initialization.

        Raises:
            ValueError: If ``separator`` is empty.

        !!! warning
            A blank separator would make prefix parsing ambiguous for every
            cell value.

        """
        _validate_separator(self.separator, type(self).__name__)

    def expand(
        self,
        cell: TableCell,
        expected_count: int,
        context: ParseContext,
    ) -> list[TableCell]:
        """Repeat recognized syntax or copy a literal value across a group.

        Args:
            cell: Value cell aligned with a grouped key cell.
            expected_count: Number of logical keys in the group.
            context: Parse context for the current schema parse.

        Returns:
            One logical value cell per key in the group.

        Raises:
            ValueError: If recognized repeat syntax is empty or has the wrong
                count.

        !!! info
            Non-numeric prefixes are treated as literal values so ordinary text
            containing the separator remains usable in feature files.

        """
        count_text, separator, value = cell.value.partition(self.separator)
        if not separator or not count_text.isdigit():
            return [cell] * expected_count
        if not value:
            raise ValueError("Repeated value cannot be empty")

        declared_count = int(count_text)
        if declared_count != expected_count:
            raise ValueError(
                f"Repeat count {declared_count} does not match "
                f"group size {expected_count}"
            )

        return [cell.with_value(value) for _ in range(declared_count)]


@dataclass(frozen=True)
class SuffixRepeat:
    """Expand value-before-count syntax such as ``Article x3``.

    If the text after the final separator is not an integer, the entire value
    is treated as a literal and copied across the key group.

    Attributes:
        separator: Text between repeated value and repeat count.

    !!! example
        ```python
        SuffixRepeat(separator=" x")  # Article x3
        ```

    """

    separator: str = " x"

    def __post_init__(self) -> None:
        """Validate the configured separator after dataclass initialization.

        Raises:
            ValueError: If ``separator`` is empty.

        !!! info
            Eager validation keeps invalid rule configuration close to schema
            import time.

        """
        _validate_separator(self.separator, type(self).__name__)

    def expand(
        self,
        cell: TableCell,
        expected_count: int,
        context: ParseContext,
    ) -> list[TableCell]:
        """Repeat recognized syntax or copy a literal value across a group.

        Args:
            cell: Value cell aligned with a grouped key cell.
            expected_count: Number of logical keys in the group.
            context: Parse context for the current schema parse.

        Returns:
            One logical value cell per key in the group.

        Raises:
            ValueError: If recognized repeat syntax is empty or has the wrong
                count.

        !!! warning
            The final occurrence of ``separator`` is used. Choose separators
            that do not naturally appear at the end of domain values.

        """
        value, separator, count_text = cell.value.rpartition(self.separator)
        if not separator or not count_text.isdigit():
            return [cell] * expected_count
        if not value:
            raise ValueError("Repeated value cannot be empty")

        declared_count = int(count_text)
        if declared_count != expected_count:
            raise ValueError(
                f"Repeat count {declared_count} does not match "
                f"group size {expected_count}"
            )

        return [cell.with_value(value) for _ in range(declared_count)]


@dataclass(frozen=True)
class ColumnGroupExpander:
    """Expand grouped columns using replaceable range and repeat rules.

    Args:
        key_row: Literal label expected in the first cell of the first row.
        range_rule: Object implementing :class:`RangeRule`.
        repeat_rule: Object implementing :class:`RepeatRule`.

    The expander owns the repetitive table mechanics: rectangular-shape
    checks, group iteration, source preservation, count validation, and
    ``TableData`` construction. Rule objects own syntax recognition and value
    expansion.

    !!! example
        ```python
        table_transformer = ColumnGroupExpander(
            key_row="IDs",
            range_rule=NumericRange(separator=".."),
            repeat_rule=PrefixRepeat(separator=":"),
        )
        ```

    """

    key_row: str
    range_rule: RangeRule
    repeat_rule: RepeatRule

    def transform(
        self,
        table: TableData,
        context: ParseContext,
        *,
        schema: type | str | None = None,
    ) -> TableData:
        """Return an expanded logical table ready for schema parsing.

        Args:
            table: Source-aware grouped table.
            context: Parse context for the current schema parse.
            schema: Optional schema identity used in diagnostics.

        Returns:
            A rectangular ``TableData`` where grouped columns have been
            expanded into one logical record column per key.

        Raises:
            TableError: If the table is empty, non-rectangular, has the
                wrong key row, or a custom rule returns invalid cells.

        !!! warning
            This transformer expects a column-oriented grouped shape. Use a
            custom ``transform_table()`` override for unrelated compact table
            conventions.

        """
        if not table.rows or not table.rows[0]:
            raise TableError(
                "Grouped table is empty",
                schema=schema,
                source_uri=table.source_uri,
                code=TableErrorCode.TABLE_EMPTY,
            )

        source_width = len(table.rows[0])
        for row_number, row in enumerate(table.rows, start=1):
            if len(row) == source_width:
                continue
            if row:
                raise TableError.from_cell(
                    "Column group expansion requires a rectangular table",
                    row[0],
                    schema=schema,
                    code=TableErrorCode.RAGGED_ROW,
                )
            raise TableError(
                "Column group expansion requires a rectangular table",
                schema=schema,
                row=row_number,
                source_uri=table.source_uri,
                code=TableErrorCode.RAGGED_ROW,
            )

        key_label = table.rows[0][0]
        if key_label.value != self.key_row:
            raise TableError.from_cell(
                f"Expected key row {self.key_row!r}",
                key_label,
                schema=schema,
                code=TableErrorCode.INVALID_TRANSFORM,
            )

        expanded_rows: list[list[TableCell]] = [[row[0]] for row in table.rows]
        for source_column in range(1, source_width):
            key_cell = table.rows[0][source_column]
            key_cells = self._expand_range(key_cell, context, schema)
            if not key_cells:
                raise TableError.from_cell(
                    "Range rule produced no keys",
                    key_cell,
                    schema=schema,
                    code=TableErrorCode.INVALID_TRANSFORM,
                )
            expanded_rows[0].extend(key_cells)

            for row_index in range(1, len(table.rows)):
                value_cell = table.rows[row_index][source_column]
                value_cells = self._expand_repeat(
                    value_cell,
                    len(key_cells),
                    context,
                    schema,
                )
                if len(value_cells) != len(key_cells):
                    raise TableError.from_cell(
                        f"Repeat rule produced {len(value_cells)} values for "
                        f"a group of {len(key_cells)} keys",
                        value_cell,
                        schema=schema,
                        code=TableErrorCode.INVALID_TRANSFORM,
                    )
                expanded_rows[row_index].extend(value_cells)

        return TableData.from_cells(expanded_rows, source=table.source_uri)

    def _expand_range(
        self,
        cell: TableCell,
        context: ParseContext,
        schema: type | str | None,
    ) -> list[TableCell]:
        """Run a range rule and normalize its errors.

        Args:
            cell: Source key cell to expand.
            context: Parse context for the current schema parse.
            schema: Optional schema identity used in diagnostics.

        Returns:
            A list of ``TableCell`` objects produced by the range rule.

        Raises:
            TableError: If the rule raises a table error, raises another
                exception, or returns non-cell values.

        !!! info
            Custom ``ValueError`` failures are wrapped with source-cell
            coordinates so feature authors see the compact key cell.

        """
        try:
            cells = list(self.range_rule.expand(cell, context))
        except (TableError, TableErrors, SchemaDefinitionError):
            raise
        except _ExpansionLimitError as exc:
            raise TableError.from_cell(
                str(exc),
                cell,
                schema=schema,
                code=TableErrorCode.EXPANSION_LIMIT,
            ) from exc
        except Exception as exc:
            raise TableError.from_cell(
                f"Range expansion failed: {exc}",
                cell,
                schema=schema,
                code=TableErrorCode.TRANSFORM_FAILED,
                cause=exc,
            ) from exc
        self._require_cells(cells, cell, "Range", schema)
        return cells

    def _expand_repeat(
        self,
        cell: TableCell,
        expected_count: int,
        context: ParseContext,
        schema: type | str | None,
    ) -> list[TableCell]:
        """Run a repeat rule and normalize its errors.

        Args:
            cell: Source value cell to expand.
            expected_count: Number of logical cells required.
            context: Parse context for the current schema parse.
            schema: Optional schema identity used in diagnostics.

        Returns:
            A list of ``TableCell`` objects produced by the repeat rule.

        Raises:
            TableError: If the rule raises a table error, raises another
                exception, or returns non-cell values.

        !!! warning
            This method validates object type only. The public ``transform``
            method additionally checks that the returned count matches the key
            group size.

        """
        try:
            cells = list(self.repeat_rule.expand(cell, expected_count, context))
        except (TableError, TableErrors, SchemaDefinitionError):
            raise
        except Exception as exc:
            raise TableError.from_cell(
                f"Repeat expansion failed: {exc}",
                cell,
                schema=schema,
                code=TableErrorCode.TRANSFORM_FAILED,
                cause=exc,
            ) from exc
        self._require_cells(cells, cell, "Repeat", schema)
        return cells

    @staticmethod
    def _require_cells(
        cells: Sequence[object],
        source: TableCell,
        rule_name: str,
        schema: type | str | None,
    ) -> None:
        """Ensure custom rules return ``TableCell`` instances.

        Args:
            cells: Objects returned by a range or repeat rule.
            source: Source cell used when reporting invalid return values.
            rule_name: Human-readable rule family for diagnostics.
            schema: Optional schema identity used in diagnostics.

        Raises:
            TableError: If any returned object is not a ``TableCell``.

        !!! warning
            Returning raw strings would lose source coordinates. Custom rules
            should call ``source.with_value(...)`` for transformed cells.

        """
        if all(isinstance(cell, TableCell) for cell in cells):
            return
        raise TableError.from_cell(
            f"{rule_name} rule must return TableCell values",
            source,
            schema=schema,
            code=TableErrorCode.INVALID_TRANSFORM,
        )
