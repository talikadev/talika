"""Read-only source metadata attached to parsed schema records.

The parser stores original table cells separately from parsed values so custom
validators and tools can report precise feature-file coordinates.

!!! info
    Metadata is immutable after record construction. Transformation may change
    current values, but source cells preserve the original location and text.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from .table import TableCell


@dataclass(frozen=True)
class RecordSource:
    """Original table locations associated with one parsed schema record.

    Attributes:
        item_id: Parsed local ID for column-oriented records when available.
        row: Source row for a row-oriented record.
        column: Source key/ID column for a column-oriented record.
        cells: Mapping from schema attribute names to their source cells.

    !!! warning
        Some fields may not have source cells, especially values produced by
        defaults for omitted optional fields.

    """

    item_id: Any | None
    row: int | None
    column: int | None
    cells: Mapping[str, TableCell]

    @classmethod
    def create(
        cls,
        *,
        item_id: Any | None = None,
        row: int | None = None,
        column: int | None = None,
        cells: Mapping[str, TableCell] | None = None,
    ) -> RecordSource:
        """Create immutable metadata from parser-owned source values.

        Args:
            item_id: Parsed record ID when available.
            row: Source row for row-oriented records.
            column: Source key/ID column for column-oriented records.
            cells: Mapping from schema field names to source cells.

        Returns:
            A frozen ``RecordSource`` with a read-only cell mapping.

        !!! info
            The mapping is copied so later caller mutations cannot change
            record provenance.

        """
        return cls(
            item_id=item_id,
            row=row,
            column=column,
            cells=MappingProxyType(dict(cells or {})),
        )

    def source_for(self, field_name: str) -> TableCell:
        """Return the source cell for one schema attribute name.

        Args:
            field_name: Python schema attribute name.

        Returns:
            ``TableCell`` that supplied the parsed value.

        Raises:
            KeyError: If the field has no recorded source cell.

        !!! warning
            Missing optional fields with defaults do not have source cells.
            Use this method when a validator is responding to a value that came
            from the feature table itself.

        """
        try:
            return self.cells[field_name]
        except KeyError as exc:
            message = f"No source cell is available for field {field_name!r}"
            raise KeyError(message) from exc
