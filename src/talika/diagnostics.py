"""Immutable diagnostics and non-raising validation results.

Diagnostic Model v1 is shared by runtime parsing, static checking, the CLI,
and integrations.  Exception classes in :mod:`talika.errors` are compatibility
adapters around these values rather than a second diagnostic representation.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Generic, TypeVar
from uuid import UUID

_UNSET = object()
T = TypeVar("T")


class DiagnosticSeverity(str, Enum):
    """Severity values supported by Diagnostic Model v1."""

    ERROR = "error"
    WARNING = "warning"


def _qualified_type(value: object) -> str:
    value_type = type(value)
    return f"{value_type.__module__}.{value_type.__qualname__}"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stable_json_value(value: Any) -> Any:
    """Convert an arbitrary project value into deterministic JSON data.

    The conversion intentionally never falls back to an object's ``repr`` or
    ``str`` implementation.  Those methods may include memory addresses or
    other process-specific data that would make checker output unstable.
    """
    return _stable_json_value(value, seen=set())


def _stable_json_value(value: Any, *, seen: set[int]) -> Any:
    if isinstance(value, Enum):
        return {
            "type": _qualified_type(value),
            "name": value.name,
            "value": _stable_json_value(value.value, seen=seen),
        }
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isfinite(value):
            return value
        label = (
            "nan" if math.isnan(value) else ("infinity" if value > 0 else "-infinity")
        )
        return {"type": "float", "value": label}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (UUID, Path, date, datetime, time)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    value_id = id(value)
    if value_id in seen:
        return {"type": _qualified_type(value)}

    if isinstance(value, Mapping):
        seen.add(value_id)
        try:
            if all(isinstance(key, str) for key in value):
                return {
                    key: _stable_json_value(value[key], seen=seen)
                    for key in sorted(value)
                }
            entries = [
                [
                    _stable_json_value(key, seen=seen),
                    _stable_json_value(item, seen=seen),
                ]
                for key, item in value.items()
            ]
            entries.sort(key=_canonical_json)
            return {"type": "mapping", "entries": entries}
        finally:
            seen.remove(value_id)

    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        seen.add(value_id)
        try:
            return [_stable_json_value(item, seen=seen) for item in value]
        finally:
            seen.remove(value_id)

    if isinstance(value, Set):
        seen.add(value_id)
        try:
            items = [_stable_json_value(item, seen=seen) for item in value]
            items.sort(key=_canonical_json)
            return items
        finally:
            seen.remove(value_id)

    return {"type": _qualified_type(value)}


def stable_text_value(value: Any) -> str:
    """Return a compact deterministic value representation for text errors."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return repr(value)
    encoded = stable_json_value(value)
    return json.dumps(encoded, sort_keys=True, separators=(",", ":"), allow_nan=False)


def stable_callable_name(value: object) -> str:
    """Return a callable identity without invoking project formatting hooks."""
    name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None)
    if isinstance(name, str) and name:
        module = getattr(value, "__module__", None)
        return f"{module}.{name}" if isinstance(module, str) and module else name
    return _qualified_type(value)


@dataclass(frozen=True, slots=True, init=False)
class Diagnostic:
    """One immutable, source-aware Diagnostic Model v1 value."""

    diagnostic_version: ClassVar[int] = 1

    code: str
    message: str
    severity: DiagnosticSeverity
    hint: str | None
    schema_name: str | None
    field_name: str | None
    field_label: str | None
    source_uri: str | None
    row: int | None
    column: int | None
    _item_id: Any
    _source_value: Any
    _logical_value: Any
    cause: BaseException | None = field(compare=False, repr=False)

    def __init__(
        self,
        *,
        code: str,
        message: str,
        severity: DiagnosticSeverity | str = DiagnosticSeverity.ERROR,
        hint: str | None = None,
        schema_name: str | None = None,
        field_name: str | None = None,
        field_label: str | None = None,
        source_uri: str | None = None,
        row: int | None = None,
        column: int | None = None,
        item_id: Any = _UNSET,
        source_value: Any = _UNSET,
        logical_value: Any = _UNSET,
        cause: BaseException | None = None,
    ) -> None:
        if not isinstance(code, str) or not code:
            raise ValueError("Diagnostic code must be a non-empty string")
        if not isinstance(message, str) or not message:
            raise ValueError("Diagnostic message must be a non-empty string")
        normalized_severity = DiagnosticSeverity(severity)
        for name, coordinate in (("row", row), ("column", column)):
            if coordinate is not None and (
                isinstance(coordinate, bool) or not isinstance(coordinate, int)
            ):
                raise TypeError(f"Diagnostic {name} must be an integer or None")
            if coordinate is not None and coordinate < 1:
                raise ValueError(f"Diagnostic {name} must be positive")
        if source_uri is not None and (
            not isinstance(source_uri, str) or not source_uri
        ):
            raise ValueError("Diagnostic source_uri must be a non-empty string")

        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "severity", normalized_severity)
        object.__setattr__(self, "hint", hint)
        object.__setattr__(self, "schema_name", schema_name)
        object.__setattr__(self, "field_name", field_name)
        object.__setattr__(self, "field_label", field_label)
        object.__setattr__(self, "source_uri", source_uri)
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "column", column)
        object.__setattr__(self, "_item_id", item_id)
        object.__setattr__(self, "_source_value", source_value)
        object.__setattr__(self, "_logical_value", logical_value)
        object.__setattr__(self, "cause", cause)

    @property
    def item_id(self) -> Any | None:
        """Return the item ID, or ``None`` when it was omitted."""
        return None if self._item_id is _UNSET else self._item_id

    @property
    def has_item_id(self) -> bool:
        """Return whether the diagnostic explicitly carries an item ID."""
        return self._item_id is not _UNSET

    @property
    def source_value(self) -> Any | None:
        """Return the original source value, or ``None`` when omitted."""
        return None if self._source_value is _UNSET else self._source_value

    @property
    def has_source_value(self) -> bool:
        """Return whether an original source value is present."""
        return self._source_value is not _UNSET

    @property
    def logical_value(self) -> Any | None:
        """Return the logical/transformed value, or ``None`` when omitted."""
        return None if self._logical_value is _UNSET else self._logical_value

    @property
    def has_logical_value(self) -> bool:
        """Return whether a logical/transformed value is present."""
        return self._logical_value is not _UNSET

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-compatible Diagnostic Model v1 mapping."""
        return {
            "diagnostic_version": self.diagnostic_version,
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "hint": self.hint,
            "schema_name": self.schema_name,
            "field_name": self.field_name,
            "field_label": self.field_label,
            "source_uri": self.source_uri,
            "row": self.row,
            "column": self.column,
            "has_item_id": self.has_item_id,
            "item_id": (stable_json_value(self.item_id) if self.has_item_id else None),
            "has_source_value": self.has_source_value,
            "source_value": (
                stable_json_value(self.source_value) if self.has_source_value else None
            ),
            "has_logical_value": self.has_logical_value,
            "logical_value": (
                stable_json_value(self.logical_value)
                if self.has_logical_value
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class ValidationResult(Generic[T]):
    """Non-raising result returned by ``Schema.validate()``."""

    records: tuple[T, ...] = ()
    diagnostics: tuple[Diagnostic, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "records", tuple(self.records))
        object.__setattr__(self, "diagnostics", tuple(self.diagnostics))
        if any(not isinstance(item, Diagnostic) for item in self.diagnostics):
            raise TypeError("ValidationResult diagnostics must be Diagnostic values")

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        """Return error-severity diagnostics in discovery order."""
        return tuple(
            item
            for item in self.diagnostics
            if item.severity is DiagnosticSeverity.ERROR
        )

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        """Return warning-severity diagnostics in discovery order."""
        return tuple(
            item
            for item in self.diagnostics
            if item.severity is DiagnosticSeverity.WARNING
        )

    @property
    def valid(self) -> bool:
        """Return whether validation found no error-severity diagnostics."""
        return not self.errors
