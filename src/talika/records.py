"""Lightweight typed records produced from table schemas.

Schema records are created after table shape validation, field parsing, and
source metadata collection. They behave like small dataclass-style objects
without requiring schema classes to define ``__init__`` methods.

!!! info
    Output-model conversion happens after records are finalized. Use
    ``parse_records()`` when tests need these intermediate record objects.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, ClassVar

from .fields import Field
from .sources import RecordSource


class TableRecord:
    """Base record object created before optional model conversion.

    Attributes:
        table_source: Immutable source metadata for the record.
        table_extras: Preserved inapplicable variant values when schema policy
            allows them.

    !!! warning
        Users normally subclass ``RowTable`` or ``ColumnTable`` rather than
        ``TableRecord`` directly.

    """

    __fields__: ClassVar[Mapping[str, Field]] = MappingProxyType({})
    _table_source: RecordSource
    _table_extras: Mapping[str, Any]

    @classmethod
    def _from_values(
        cls,
        values: dict[str, Any],
        *,
        source: RecordSource | None = None,
        extras: Mapping[str, Any] | None = None,
    ) -> TableRecord:
        """Construct a schema record without invoking user initialization.

        Args:
            values: Parsed values keyed by schema attribute name.
            source: Optional source metadata for the record.
            extras: Optional preserved extra values.

        Returns:
            A populated record instance of ``cls``.

        !!! info
            Schema classes declare fields as descriptors, so direct assignment
            through ``setattr`` attaches values consistently with normal
            attribute access.

        """
        record = cls.__new__(cls)
        for name in cls.__fields__:
            setattr(record, name, values[name])
        record._table_source = source or RecordSource.create()
        record._table_extras = MappingProxyType(dict(extras or {}))
        return record

    @property
    def table_source(self) -> RecordSource:
        """Return immutable source metadata for this parsed record.

        Returns:
            ``RecordSource`` containing record and field cell locations.

        !!! info
            Source metadata remains available even when validation later raises
            an error, making custom diagnostics easier to build.

        """
        return self._table_source

    def source_for(self, field_name: str) -> Any:
        """Return the original ``TableCell`` for one schema attribute.

        Args:
            field_name: Python schema attribute name.

        Returns:
            Source-aware cell for the requested field.

        Raises:
            KeyError: If no source cell exists for ``field_name``.

        !!! example
            ```python
            cell = record.source_for("email")
            raise TableError.from_cell("Invalid email", cell)
            ```

        """
        return self.table_source.source_for(field_name)

    @property
    def table_extras(self) -> Mapping[str, Any]:
        """Return values preserved by schema policy.

        Returns:
            Read-only mapping of preserved inapplicable variant labels to values.

        !!! warning
            Extras exist only when the variant inapplicable-field policy is
            ``"preserve"``. Code should not depend on them for required domain
            fields.

        """
        return self._table_extras

    def as_dict(self) -> dict[str, Any]:
        """Return declared schema fields as a new dictionary.

        Returns:
            Mapping from schema attribute names to parsed values.

        !!! info
            Source metadata and extras are intentionally excluded so the result
            is suitable for output-model keyword arguments.

        """
        return {name: getattr(self, name) for name in self.__fields__}

    def __repr__(self) -> str:
        """Return a constructor-like representation of declared fields.

        Returns:
            String containing the record type and parsed field values.

        !!! info
            The representation is meant for tests and debugging, not for
            round-tripping records.

        """
        values = ", ".join(
            f"{name}={getattr(self, name)!r}" for name in self.__fields__
        )
        return f"{type(self).__name__}({values})"

    def __eq__(self, other: object) -> bool:
        """Compare records by concrete type and declared field values.

        Args:
            other: Object being compared to this record.

        Returns:
            ``True`` when both records have the same concrete schema type and
            parsed field dictionary.

        !!! warning
            Source metadata and preserved extras do not participate in
            equality. They describe provenance rather than record identity.

        """
        return type(self) is type(other) and self.as_dict() == other.as_dict()
