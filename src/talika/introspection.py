"""Immutable, machine-readable descriptions of table schema contracts.

The objects in this module are returned by ``Table.describe()`` and power the
``talika describe`` command. They intentionally contain only serializable
or easily renderable metadata.

!!! info
    Contracts describe schema shape and configured hooks. They do not parse a
    table or execute project validators.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .fields import MISSING, Field


def _callable_name(value: Any) -> str | None:
    """Return a best-effort display name for a callable or object.

    Args:
        value: Callable, object, ``None``, or ``MISSING`` sentinel.

    Returns:
        ``None`` for absent values, otherwise a qualified/name/type fallback.

    !!! info
        The result is for diagnostics and schema descriptions, not for
        re-importing the callable.

    """
    if value is None or value is MISSING:
        return None
    return getattr(
        value, "__qualname__", getattr(value, "__name__", type(value).__name__)
    )


@dataclass(frozen=True)
class FieldContract:
    """Public description of one declared schema field.

    Attributes:
        name: Python schema attribute name.
        label: Canonical BDD table label.
        aliases: Alternate accepted labels.
        required: Whether the field is required.
        is_id: Whether the field identifies column-oriented records.
        is_discriminator: Whether the field selects variants.
        has_default: Whether a static or factory default is configured.
        default_repr: ``repr`` of a static default when present.
        default_factory: Display name of the default factory when present.
        parser: Display name of the parser when present.
        reference_target: Referenced field name when this is a reference.
        reference_many: Whether the reference contains multiple keys.
        empty: Explicit empty-cell policy for optional values.

    !!! info
        The contract is frozen so tools can cache it safely.

    """

    name: str
    label: str
    aliases: tuple[str, ...]
    required: bool
    is_id: bool
    is_discriminator: bool
    has_default: bool
    default_repr: str | None
    default_factory: str | None
    parser: str | None
    reference_target: str | None
    reference_many: bool
    empty: str

    @classmethod
    def from_field(cls, name: str, declared: Field) -> FieldContract:
        """Build an immutable contract from one field declaration.

        Args:
            name: Python schema attribute name.
            declared: Internal ``Field`` declaration.

        Returns:
            A ``FieldContract`` suitable for JSON conversion.

        !!! warning
            Defaults are represented with ``repr`` rather than copied as live
            objects, because contracts are descriptive metadata.

        """
        reference = declared.reference
        return cls(
            name=name,
            label=declared.label,
            aliases=declared.aliases,
            required=declared.required,
            is_id=declared.is_id,
            is_discriminator=declared.is_discriminator,
            has_default=(
                declared.default is not MISSING
                or declared.default_factory is not MISSING
            ),
            default_repr=(
                repr(declared.default) if declared.default is not MISSING else None
            ),
            default_factory=_callable_name(declared.default_factory),
            parser=_callable_name(declared.parser),
            reference_target=reference.target if reference else None,
            reference_many=reference.many if reference else False,
            empty=declared.empty,
        )


@dataclass(frozen=True)
class VariantContract:
    """Description of one discriminator value and selected schema.

    Attributes:
        value: Parsed discriminator value that selects the variant.
        schema_name: Display name of the concrete variant schema.
        fields: Field contracts active for that variant.
        output_model: Display name of the variant output model, if any.
        output_builder: Display name of the output builder hook.

    !!! info
        Generated variant class names may change, so tooling should present
        ``schema_name`` and use ``variant_for()`` for runtime lookup.

    """

    value: Any
    schema_name: str
    fields: tuple[FieldContract, ...]
    output_model: str | None
    output_builder: str


@dataclass(frozen=True)
class TableContract:
    """Complete public description returned by ``Table.describe()``.

    Attributes:
        schema_name: Display name of the described schema.
        orientation: ``"row"`` or ``"column"``.
        fields: Base schema field contracts.
        variants: Discriminator variant contracts.
        unknown_fields: Policy for undeclared table labels.
        inapplicable_fields: Policy for values belonging to other variants.
        transformer: Display name of configured table transformer.
        output_model: Display name of configured output model.
        output_builder: Display name of the output builder hook.

    !!! example
        ```python
        contract = UserTable.describe()
        assert contract.orientation == "row"
        ```

    """

    schema_name: str
    orientation: str
    fields: tuple[FieldContract, ...]
    variants: tuple[VariantContract, ...]
    unknown_fields: str
    inapplicable_fields: str
    transformer: str | None
    output_model: str | None
    output_builder: str

    def as_dict(self) -> dict[str, Any]:
        """Return a recursively structured dictionary.

        Returns:
            Dictionary containing only standard container values.

        !!! info
            CLI JSON output delegates to this method so editor integrations and
            CI scripts receive the same shape as Python callers.

        """
        return asdict(self)


def describe_schema(schema: Any) -> TableContract:
    """Inspect one table schema without parsing a feature table.

    Args:
        schema: ``RowTable`` or ``ColumnTable`` subclass to describe.

    Returns:
        A frozen ``TableContract`` containing fields, variants, policies, and
        configured hook names.

    !!! warning
        This function trusts that ``schema`` has already been created by the
        talika metaclass. Use ``Table.describe()`` for the public API.

    """
    orientation = (
        "column"
        if any(base.__name__ == "ColumnTable" for base in schema.mro())
        else "row"
    )
    fields = tuple(
        FieldContract.from_field(name, declared)
        for name, declared in schema.__fields__.items()
    )
    variants = tuple(
        VariantContract(
            value=value,
            schema_name=variant.__dict__.get(
                "__schema_display_name__", variant.__name__
            ),
            fields=tuple(
                FieldContract.from_field(name, declared)
                for name, declared in variant.__fields__.items()
            ),
            output_model=_callable_name(variant.output_model),
            output_builder=_callable_name(variant.build_output) or "build_output",
        )
        for value, variant in schema.__variants__.items()
    )
    return TableContract(
        schema_name=schema.__dict__.get("__schema_display_name__", schema.__name__),
        orientation=orientation,
        fields=fields,
        variants=variants,
        unknown_fields=schema.unknown_fields,
        inapplicable_fields=schema.inapplicable_fields,
        transformer=_callable_name(schema.table_transformer),
        output_model=_callable_name(schema.output_model),
        output_builder=_callable_name(schema.build_output) or "build_output",
    )
