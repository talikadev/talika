"""Immutable internal schema metadata consumed by the parsing engine."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from types import MappingProxyType
from typing import Any, TypeVar

from .fields import Field, ReferenceSpec

K = TypeVar("K")
V = TypeVar("V")


def immutable_mapping(values: Mapping[K, V]) -> Mapping[K, V]:
    """Return a read-only mapping backed by a private dictionary copy."""
    return MappingProxyType(dict(values))


class Orientation(str, Enum):
    """Supported physical table orientations."""

    ROW = "row"
    COLUMN = "column"


class ErrorMode(str, Enum):
    """Supported parser diagnostic modes."""

    FIRST = "first"
    COLLECT = "collect"


class EmptyPolicy(str, Enum):
    """Supported explicit-empty-cell policies."""

    RAW = "raw"
    PARSE = "parse"
    NONE = "none"
    ERROR = "error"


class UnknownFieldPolicy(str, Enum):
    """Supported undeclared-label policies."""

    FORBID = "forbid"


class InapplicableFieldPolicy(str, Enum):
    """Supported wrong-variant-field policies."""

    FORBID = "forbid"
    PRESERVE = "preserve"


@dataclass(frozen=True, slots=True)
class CompiledField:
    """Normalized immutable metadata for one schema field."""

    name: str
    origin: tuple[str, str]
    label: str
    aliases: tuple[str, ...]
    required: bool
    default: Any
    default_factory: Any
    parser: Callable[..., Any] | None
    parse_empty: bool
    empty: EmptyPolicy
    is_id: bool
    is_discriminator: bool
    variants: Mapping[Any, type] | None
    reference: ReferenceSpec | None
    declaration: Field

    @property
    def labels(self) -> tuple[str, ...]:
        """Return the canonical label followed by aliases."""
        return (self.label, *self.aliases)


@dataclass(frozen=True, slots=True)
class SchemaPolicies:
    """Normalized schema policy values."""

    unknown_fields: UnknownFieldPolicy
    inapplicable_fields: InapplicableFieldPolicy


@dataclass(frozen=True, slots=True)
class SchemaHooks:
    """Resolved lifecycle hooks and configured output/transform objects."""

    table_transformer: Any
    output_model: Callable[..., Any] | None
    transform_table: Callable[..., Any] | None
    validate_record: Callable[..., Any] | None
    validate_records: Callable[..., Any] | None
    build_output: Callable[..., Any] | None


@dataclass(frozen=True, slots=True)
class SchemaPlan:
    """One immutable compiled representation of a Talika schema."""

    schema_type: type
    display_name: str
    orientation: Orientation | None
    fields: tuple[CompiledField, ...]
    fields_by_name: Mapping[str, CompiledField]
    fields_by_label: Mapping[str, CompiledField]
    accepted_labels: frozenset[str]
    id_field: CompiledField | None
    discriminator: CompiledField | None
    variants: Mapping[Any, SchemaPlan]
    reference_targets: Mapping[str, CompiledField]
    policies: SchemaPolicies
    hooks: SchemaHooks

    def with_variants(
        self,
        variants: Mapping[Any, SchemaPlan],
        *,
        reference_targets: Mapping[str, CompiledField] | None = None,
    ) -> SchemaPlan:
        """Return a new family snapshot without mutating this plan."""
        return replace(
            self,
            variants=immutable_mapping(variants),
            reference_targets=(
                self.reference_targets
                if reference_targets is None
                else immutable_mapping(reference_targets)
            ),
        )
