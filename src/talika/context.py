"""Context objects passed through table and cell parsing.

Contexts keep project-owned dependencies separate from schema declarations.
They are immutable containers passed through transformers, parsers, default
factories, and validation hooks during one parse operation.

!!! info
    ``talika`` copies user mappings into read-only views so parser code can
    read dependencies without accidentally mutating caller-owned state.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, cast


@dataclass(frozen=True)
class ParseContext:
    """Project-owned dependencies and settings for one parse operation.

    The library copies the supplied mapping and exposes it as read-only
    ``user_data``. Cell parsers, table transformers, and record validators all
    receive data originating from this same context object.

    Attributes:
        user_data: Read-only mapping of project-owned dependencies and
            settings.

    !!! example
        ```python
        UserTable.parse(datatable, context={"faker": faker})
        ```

    """

    user_data: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_value(cls, value: Mapping[str, Any] | ParseContext | None) -> ParseContext:
        """Normalize raw context input.

        Args:
            value: ``None``, an existing ``ParseContext``, or a project mapping.

        Returns:
            A ``ParseContext`` instance with read-only ``user_data``.

        Raises:
            TypeError: If ``value`` cannot be copied as a mapping.

        !!! info
            Existing ``ParseContext`` objects pass through unchanged, which lets
            advanced callers construct and reuse immutable context values.

        """
        if value is None:
            return cls()
        if isinstance(value, cls):
            return value
        return cls(user_data=MappingProxyType(dict(cast(Mapping[str, Any], value))))


@dataclass(frozen=True)
class CellContext:
    """Source location and project data supplied to a field parser.

    ``value`` is passed separately to a field parser and represents the
    current, possibly transformed value. ``source_value`` records what was
    written in the original Gherkin data table before table transformation.

    Attributes:
        schema: Concrete schema class parsing the cell.
        field_name: Python attribute name receiving the parsed value.
        field_label: Canonical Gherkin data table label for the field.
        row: One-based source row when available.
        column: One-based source column when available.
        item_id: Parsed record ID when available.
        source_value: Original feature-file text before transformation.
        user_data: Read-only project data from ``ParseContext``.

    !!! warning
        Parser functions receive the current value as a separate argument. Use
        ``source_value`` only when diagnostics or project syntax need the
        original feature text.

    """

    schema: type
    field_name: str
    field_label: str
    row: int | None
    column: int | None
    item_id: Any | None
    source_value: str
    user_data: Mapping[str, Any]


@dataclass(frozen=True)
class DefaultContext:
    """Context supplied when a missing optional field uses a factory.

    Default factories do not have a source cell because the field was omitted
    from the Gherkin data table. They still receive the selected schema, field identity,
    item ID when available, and the same read-only project data supplied to the
    parse operation.

    Attributes:
        schema: Concrete schema class building the default.
        field_name: Python attribute name receiving the default.
        field_label: Canonical Gherkin data table label for the field.
        item_id: Parsed record ID when available.
        user_data: Read-only project data from ``ParseContext``.

    !!! info
        Default factories run only for missing optional fields, not for
        explicit empty cells.

    """

    schema: type
    field_name: str
    field_label: str
    item_id: Any | None
    user_data: Mapping[str, Any]
