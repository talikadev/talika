"""Schema field declarations.

Field declarations are descriptors collected by the schema metaclass. They
describe how Gherkin data table labels map to Python attributes, which values are
required, and how raw cell text should be converted.

!!! info
    Labels are literal project vocabulary. ``talika`` does not infer
    meaning from characters such as ``*`` unless the schema explicitly sets
    options such as ``required=True``.
"""

from __future__ import annotations

from collections.abc import (
    Callable,
    Mapping,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Sequence,
)
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from types import MappingProxyType
from typing import Any

from .context import CellContext, DefaultContext

MISSING = object()
Parser = Callable[[Any, CellContext], Any]
DefaultFactory = Callable[[DefaultContext], Any]


@dataclass(frozen=True)
class ReferenceSpec:
    """Configure local ID resolution within the same parsed table.

    Attributes:
        target: Attribute name on the referenced record used as the lookup key.
        many: Whether the source cell contains several references.
        separator: Text separator used when ``many`` is true.

    !!! info
        Reference resolution happens after records are constructed and before
        record/table validation hooks run.

    """

    target: str
    many: bool
    separator: str


@dataclass
class Field:
    """Store one declared schema field and its conversion behavior.

    Attributes:
        label: Canonical Gherkin data table label. ``None`` is accepted only
            while an ordinary ``field()`` waits for its Python attribute name.
        aliases: Alternate accepted labels for evolving feature vocabulary.
        required: Whether the field must be present and non-empty.
        default: Static value used when an optional field is absent.
        default_factory: Context-aware factory used when an optional field is
            absent.
        parser: Optional callable used to convert non-empty cell values.
        empty: Effective policy for explicit empty cells.
        is_id: Whether this field identifies column-oriented records.
        is_discriminator: Whether this field selects record variants.
        variants: Declarative discriminator component mapping.
        reference: Optional local-record reference configuration.
        name: Python attribute name assigned by the schema class body.

    !!! warning
        ``Field`` instances are mutable during class creation because
        ``__set_name__`` records their Python attribute name. Schema
        inheritance uses ``clone()`` to avoid sharing that mutable state. The
        declaration is frozen after its schema plan is compiled.

    """

    label: str | None
    aliases: tuple[str, ...] = ()
    required: bool = False
    default: Any = MISSING
    default_factory: DefaultFactory | object = MISSING
    parser: Parser | None = None
    empty: str = "raw"
    is_id: bool = False
    is_discriminator: bool = False
    variants: Mapping[Any, type] | None = None
    reference: ReferenceSpec | None = None
    name: str = ""
    _owner: type | None = dataclass_field(
        default=None, init=False, repr=False, compare=False
    )
    _origin: tuple[str, str] | None = dataclass_field(
        default=None, init=False, repr=False, compare=False
    )
    _frozen: bool = dataclass_field(
        default=False, init=False, repr=False, compare=False
    )

    def __setattr__(self, name: str, value: Any) -> None:
        """Set declaration metadata while the field is being compiled.

        Compiled declarations are immutable. Parsed record assignment still
        uses :meth:`__set__` and is deliberately unaffected by this guard.
        """
        if getattr(self, "_frozen", False):
            raise AttributeError(
                f"Field metadata is frozen; cannot assign {name!r}. "
                "Declare a new field on a schema subclass instead."
            )
        object.__setattr__(self, name, value)

    def clone(self) -> Field:
        """Return an independent declaration for schema inheritance.

        Returns:
            A new ``Field`` with the same declaration options.

        !!! info
            Schema subclasses receive cloned fields so changing an inferred
            parser or descriptor name on one schema does not mutate its base
            schema's declaration.

        """
        cloned = Field(
            label=self.label,
            aliases=self.aliases,
            required=self.required,
            default=self.default,
            default_factory=self.default_factory,
            parser=self.parser,
            empty=self.empty,
            is_id=self.is_id,
            is_discriminator=self.is_discriminator,
            variants=self.variants,
            reference=self.reference,
            name=self.name,
        )
        object.__setattr__(cloned, "_origin", self._origin)
        return cloned

    def __set_name__(self, owner: type, name: str) -> None:
        """Record the Python attribute name assigned by a schema class.

        Args:
            owner: Schema class receiving the descriptor.
            name: Attribute name used in the class body.

        !!! info
            The table label and the Python attribute name are intentionally
            separate so feature files can use human-facing language while code
            keeps normal Python identifiers.

        """
        if self._owner is not None and self._owner is not owner:
            raise AttributeError(
                f"Field {self.label!r} is already bound to "
                f"{self._owner.__name__}.{self.name}"
            )
        self.name = name
        if self.label is None:
            self.label = name
        self._owner = owner
        if self._origin is None:
            self._origin = (f"{owner.__module__}.{owner.__qualname__}", name)

    def _freeze(self) -> None:
        """Freeze declaration metadata after schema compilation."""
        object.__setattr__(self, "_frozen", True)

    def __get__(self, instance: object | None, owner: type | None = None) -> Any:
        """Return the declaration on classes or parsed value on records.

        Args:
            instance: Parsed record instance, or ``None`` during class access.
            owner: Owning schema class.

        Returns:
            The ``Field`` declaration when accessed on a class, otherwise the
            parsed attribute value stored on the record.

        !!! warning
            Parsed records are created through the schema lifecycle. Accessing
            a descriptor-backed attribute before construction populates the
            instance dictionary will raise ``KeyError``.

        """
        if instance is None:
            return self
        return instance.__dict__[self.name]

    def __set__(self, instance: object, value: Any) -> None:
        """Store a parsed value on a record instance.

        Args:
            instance: Parsed record object being populated.
            value: Parsed field value.

        !!! info
            Assignment is intentionally direct. Validation and conversion have
            already happened before values are attached to records.

        """
        instance.__dict__[self.name] = value

    @property
    def labels(self) -> tuple[str, ...]:
        """Return the canonical label followed by accepted aliases.

        Returns:
            Tuple used during label matching and duplicate-label validation.

        !!! info
            Canonical label order is preserved so introspection can present the
            preferred table vocabulary first.

        """
        if self.label is None:
            raise RuntimeError("Field label is unavailable before class binding")
        return (self.label, *self.aliases)


def _validate_field_options(
    label: str | None,
    aliases: Sequence[str],
    *,
    allow_implicit_label: bool = False,
    required: bool,
    default: Any,
    default_factory: DefaultFactory | object,
    parser: Parser | None = None,
    empty: str | None = None,
) -> tuple[tuple[str, ...], str]:
    """Validate declaration options shared by field constructors.

    Args:
        label: Canonical table label, or ``None`` for an implicit ordinary
            field label.
        aliases: Alternate accepted labels.
        allow_implicit_label: Whether ``None`` may be resolved from the Python
            attribute name during class creation.
        required: Whether a value is required.
        default: Static default value or ``MISSING``.
        default_factory: Context-aware default factory or ``MISSING``.
        parser: Optional value parser.
        empty: Explicit empty-cell policy, or ``None`` to choose ``"error"``
            for required fields and ``"raw"`` for optional fields.

    Returns:
        Aliases normalized to a tuple and the effective empty-cell policy.

    Raises:
        ValueError: If labels/defaults are internally contradictory.
        TypeError: If ``default_factory`` is present but not callable.

    !!! warning
        Required fields cannot declare defaults because that would make missing
        table data appear valid.

    """
    if label is None:
        if not allow_implicit_label:
            raise TypeError("field label must be a string")
    elif not isinstance(label, str):
        raise TypeError("field label must be a string")
    elif not label:
        raise ValueError("field label cannot be empty")
    if isinstance(aliases, (str, bytes, bytearray)) or not isinstance(
        aliases, Sequence
    ):
        raise TypeError("field aliases must be a non-string sequence of strings")
    normalized = tuple(aliases)
    if any(not isinstance(alias, str) for alias in normalized):
        raise TypeError("field aliases must be strings")
    if any(not alias for alias in normalized):
        raise ValueError("field aliases cannot be empty")
    if (label is not None and label in normalized) or len(set(normalized)) != len(
        normalized
    ):
        raise ValueError("field aliases must be unique and differ from the label")
    if default is not MISSING and default_factory is not MISSING:
        raise ValueError("field cannot declare both default and default_factory")
    if required and (default is not MISSING or default_factory is not MISSING):
        raise ValueError("required fields cannot declare defaults")
    if default_factory is not MISSING and not callable(default_factory):
        raise TypeError("default_factory must be callable")
    if parser is not None and not callable(parser):
        raise TypeError("parser must be callable")
    if empty is not None and empty not in {"raw", "parse", "none", "error"}:
        raise ValueError("empty must be 'raw', 'parse', 'none', 'error', or None")
    if required and empty not in {None, "error"}:
        raise ValueError("required fields only support empty='error'")
    effective_empty = ("error" if required else "raw") if empty is None else empty
    if default is not MISSING:
        if isinstance(
            default, (MutableMapping, MutableSequence, MutableSet, bytearray)
        ):
            raise TypeError(
                "mutable static defaults are not allowed; use default_factory"
            )
        try:
            hash(default)
        except TypeError as exc:
            raise TypeError(
                "unhashable static defaults are not allowed; use default_factory"
            ) from exc
    return normalized, effective_empty


def field(
    label: str | None = None,
    *,
    required: bool = False,
    default: Any = MISSING,
    default_factory: DefaultFactory | object = MISSING,
    parser: Parser | None = None,
    aliases: Sequence[str] = (),
    empty: str | None = None,
) -> Any:
    """Declare a row or column in a table schema.

    The Python attribute name becomes the table label when ``label`` is
    omitted. Empty cells are controlled only by ``empty``; parser objects do
    not opt into blank handling implicitly.

    Args:
        label: Canonical Gherkin data table label. When omitted, use the
            Python attribute name.
        required: Whether the field must be present and non-empty.
        default: Static value used when the entire field is absent.
        default_factory: Factory called for an absent optional field.
        parser: Optional parser for non-empty values.
        aliases: Alternate accepted table labels.
        empty: Policy for explicit empty cells. When omitted, required fields
            use ``"error"`` and optional fields use ``"raw"``. ``"parse"``
            sends an empty string through the parser, ``"none"`` returns
            ``None``, and ``"error"`` rejects it.

    Returns:
        A descriptor collected by ``RowTable`` or ``ColumnTable`` subclasses.

    Raises:
        TypeError: If labels, aliases, parsers, factories, or defaults have an
            invalid runtime shape.
        ValueError: If required/default/empty options contradict each other or
            an empty policy is unknown.

    !!! example
        ```python
        class UserTable(RowTable):
            name = field(required=True)
            role = field("role", default="viewer", aliases=("type",))
        ```

    """
    normalized_aliases, effective_empty = _validate_field_options(
        label,
        aliases,
        allow_implicit_label=True,
        required=required,
        default=default,
        default_factory=default_factory,
        parser=parser,
        empty=empty,
    )
    return Field(
        label=label,
        aliases=normalized_aliases,
        required=required,
        default=default,
        default_factory=default_factory,
        parser=parser,
        empty=effective_empty,
    )


def id_field(
    label: str,
    *,
    parser: Parser | None = None,
    aliases: Sequence[str] = (),
) -> Any:
    """Declare the item identifier field for parsed records.

    Args:
        label: Canonical ID row label.
        parser: Optional parser for ID values.
        aliases: Alternate accepted ID row labels.

    Returns:
        A required identifier ``Field`` descriptor.

    !!! warning
        A column-oriented table must declare exactly one ID field. A
        row-oriented table may declare one when parser contexts, defaults, and
        diagnostics need a stable ``item_id``.

    """
    normalized_aliases, effective_empty = _validate_field_options(
        label,
        aliases,
        required=True,
        default=MISSING,
        default_factory=MISSING,
        parser=parser,
    )
    return Field(
        label=label,
        aliases=normalized_aliases,
        required=True,
        parser=parser,
        empty=effective_empty,
        is_id=True,
    )


def discriminator_field(
    label: str,
    *,
    parser: Parser | None = None,
    aliases: Sequence[str] = (),
) -> Any:
    """Declare the field used to select registered record variants.

    A discriminator is always required because the parser cannot choose a
    variant without it. The optional parser runs before variant lookup, so a
    project may register enum members or other typed values as variant keys.

    Declaring this field does not enable variants by itself. Register variant
    schema subclasses with ``@BaseSchema.variant(value)``.

    Args:
        label: Canonical discriminator label.
        parser: Optional parser that runs before variant lookup.
        aliases: Alternate accepted labels.

    Returns:
        A required discriminator ``Field`` descriptor.

    !!! example
        ```python
        class ContentTable(ColumnTable):
            content_type = discriminator_field("Type*")
        ```

    """
    normalized_aliases, effective_empty = _validate_field_options(
        label,
        aliases,
        required=True,
        default=MISSING,
        default_factory=MISSING,
        parser=parser,
    )
    return Field(
        label=label,
        aliases=normalized_aliases,
        required=True,
        parser=parser,
        empty=effective_empty,
        is_discriminator=True,
    )


def discriminator(
    label: str,
    *,
    variants: Mapping[Any, type],
    parser: Parser | None = None,
    aliases: Sequence[str] = (),
) -> Any:
    """Declare a discriminator and variant field components together.

    ``variants`` maps parsed discriminator values to ``TableFields``
    subclasses. When the containing table schema is created, talika
    composes each component with that schema and registers the resulting
    record variant automatically.

    This is the concise alternative to ``discriminator_field()`` plus
    ``@Table.variant(value)`` classes. The explicit decorator form remains
    useful when a project prefers named variant schema classes.

    Args:
        label: Canonical discriminator label.
        variants: Mapping from parsed discriminator values to ``TableFields``
            component classes.
        parser: Optional parser that runs before variant lookup.
        aliases: Alternate accepted labels.

    Returns:
        A required discriminator ``Field`` descriptor with variant metadata.

    Raises:
        TypeError: If ``variants`` is not a mapping.
        ValueError: If ``variants`` is empty.

    !!! example
        ```python
        content_type = discriminator(
            "Type*",
            variants={"Article": ArticleFields, "Poll": PollFields},
        )
        ```

    """
    if not isinstance(variants, Mapping):
        raise TypeError("discriminator variants must be a mapping")
    if not variants:
        raise ValueError("discriminator variants cannot be empty")
    normalized_aliases, effective_empty = _validate_field_options(
        label,
        aliases,
        required=True,
        default=MISSING,
        default_factory=MISSING,
        parser=parser,
    )
    return Field(
        label=label,
        aliases=normalized_aliases,
        required=True,
        parser=parser,
        empty=effective_empty,
        is_discriminator=True,
        variants=MappingProxyType(dict(variants)),
    )


def reference(
    label: str,
    *,
    target: str = "id",
    many: bool = False,
    separator: str = ",",
    required: bool = False,
    default: Any = MISSING,
    aliases: Sequence[str] = (),
) -> Any:
    """Declare a local reference to another parsed record in the same table.

    The raw cell contains one target value, or a separator-delimited list when
    ``many=True``. Resolution occurs after all records are constructed and
    before validation hooks run.

    Args:
        label: Canonical table label containing reference keys.
        target: Attribute on records used as the lookup key.
        many: Whether the cell contains several keys.
        separator: Separator used when ``many`` is true.
        required: Whether the reference cell must be present and non-empty.
        default: Static value used when an optional reference field is absent.
        aliases: Alternate accepted table labels.

    Returns:
        A ``Field`` descriptor whose parsed value is resolved to record
        objects.

    Raises:
        ValueError: If ``many=True`` and ``separator`` is empty.

    !!! warning
        Reference keys are parsed with the target field's parser before lookup.
        Keep separators distinct from valid key text when using ``many=True``.

    """
    if not isinstance(target, str):
        raise TypeError("reference target must be a string")
    if not target:
        raise ValueError("reference target cannot be empty")
    if not isinstance(separator, str):
        raise TypeError("reference separator must be a string")
    if many and not separator:
        raise ValueError("reference separator cannot be empty")
    normalized_aliases, effective_empty = _validate_field_options(
        label,
        aliases,
        required=required,
        default=default,
        default_factory=MISSING,
    )
    return Field(
        label=label,
        aliases=normalized_aliases,
        required=required,
        default=default,
        empty=effective_empty,
        reference=ReferenceSpec(target=target, many=many, separator=separator),
    )
