"""Compile schema declarations into immutable runtime plans."""

from __future__ import annotations

import sys
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, get_type_hints

from .annotations import (
    annotation_accepts_raw_text,
    annotation_accepts_value,
    parser_for_annotation,
)
from .errors import SchemaDefinitionError
from .fields import MISSING as _FIELD_MISSING
from .fields import Field
from .schema_plan import (
    CompiledField,
    EmptyPolicy,
    InapplicableFieldPolicy,
    Orientation,
    SchemaHooks,
    SchemaPlan,
    SchemaPolicies,
    UnknownFieldPolicy,
    immutable_mapping,
)

_INVALID = object()

RESERVED_FIELD_NAMES = frozenset(
    {
        "parse",
        "parse_as",
        "validate",
        "describe",
        "variant",
        "variant_for",
        "transform_table",
        "validate_record",
        "validate_records",
        "build_output",
        "table_source",
        "table_extras",
        "source_for",
        "as_dict",
        "table_transformer",
        "output_model",
        "unknown_fields",
        "inapplicable_fields",
        "__fields__",
        "__variants__",
        "__schema_plan__",
        "__schema_sealed__",
        "__schema_frozen__",
        "__variant_root__",
        "__variant_value__",
        "__table_orientation__",
    }
)


def collect_fields(
    schema_name: str,
    bases: tuple[type, ...],
    namespace: Mapping[str, Any],
) -> dict[str, Field]:
    """Resolve inherited and local fields before class construction."""
    local_fields = {
        name: value for name, value in namespace.items() if isinstance(value, Field)
    }
    for name, declared in local_fields.items():
        if name in RESERVED_FIELD_NAMES:
            raise SchemaDefinitionError(
                f"Field attribute {name!r} is reserved by Talika",
                schema=schema_name,
            )
        if declared._owner is not None:
            raise SchemaDefinitionError(
                f"Field {declared.label!r} is already bound to "
                f"{declared._owner.__name__}.{declared.name}; create a new "
                "field declaration or use clone()",
                schema=schema_name,
            )

    inherited: dict[str, Field] = {}
    for base in bases:
        for name, declared in getattr(base, "__fields__", {}).items():
            if name not in inherited:
                inherited[name] = declared.clone()
                continue
            existing = inherited[name]
            if existing._origin == declared._origin:
                continue
            if name not in local_fields:
                raise SchemaDefinitionError(
                    f"Conflicting inherited field {name!r} is declared by "
                    f"{_origin_name(existing)} and {_origin_name(declared)}; "
                    "redeclare it on the child schema to resolve the conflict",
                    schema=schema_name,
                )

    for name in inherited:
        if name in namespace and name not in local_fields:
            raise SchemaDefinitionError(
                f"A non-field attribute cannot override inherited field {name!r}",
                schema=schema_name,
            )

    fields = dict(inherited)
    fields.update(local_fields)
    return fields


def _origin_name(declared: Field) -> str:
    """Return a readable field declaration origin."""
    if declared._origin is None:
        return "an unknown schema"
    return declared._origin[0]


def resolve_annotations(cls: type, fields: Mapping[str, Field]) -> None:
    """Infer parsers and validate framework-controlled annotation paths.

    Args:
        cls: Schema class whose annotations should be resolved.
        fields: Bound field declarations collected for the schema.

    Raises:
        SchemaDefinitionError: If Talika can prove that a missing, empty,
            defaulted, or raw-text path contradicts the resolved annotation.


    !!! info
        Explicit parsers and default factories remain trusted extension
        points. This validation covers only values Talika creates directly.

    """
    for field_name, declared in fields.items():
        annotation = _resolve_field_annotation(cls, field_name)
        if annotation is _INVALID:
            if declared.empty == "parse" and declared.parser is None:
                raise SchemaDefinitionError(
                    f"Field {field_name!r} uses empty='parse' but has no explicit "
                    "parser and its annotation cannot provide one; add parser=... "
                    "or choose another empty policy",
                    schema=cls.__name__,
                )
            continue
        explicit_parser = declared.parser is not None
        if not explicit_parser:
            inferred = parser_for_annotation(annotation)
            if inferred is not None:
                declared.parser = inferred
        _validate_annotation_paths(cls, declared, annotation)


def _validate_annotation_paths(cls: type, declared: Field, annotation: Any) -> None:
    """Reject field outcomes that contradict one resolved annotation.

    Args:
        cls: Schema class receiving the field.
        declared: Bound field declaration after parser inference.
        annotation: Resolved Python annotation for the field.

    Raises:
        SchemaDefinitionError: If a framework-owned value path is incompatible
            with ``annotation``.

    """
    name = declared.name
    if (
        not declared.required
        and declared.default is _FIELD_MISSING
        and declared.default_factory is _FIELD_MISSING
        and not annotation_accepts_value(annotation, None)
    ):
        raise SchemaDefinitionError(
            f"Field {name!r} may be missing and become None, but its annotation "
            "does not allow None; use required=True, add a default, or include None "
            "in the annotation",
            schema=cls.__name__,
        )
    if declared.default is not _FIELD_MISSING and not annotation_accepts_value(
        annotation, declared.default
    ):
        raise SchemaDefinitionError(
            f"Field {name!r} default does not match its annotation; use a matching "
            "default value or change the annotation",
            schema=cls.__name__,
        )
    if (
        not declared.required
        and declared.empty == "raw"
        and not annotation_accepts_value(annotation, "")
    ):
        raise SchemaDefinitionError(
            f"Field {name!r} uses empty='raw' and may become a string, but its "
            "annotation does not allow str; choose empty='none', empty='parse', "
            "or empty='error'",
            schema=cls.__name__,
        )
    if (
        not declared.required
        and declared.empty == "none"
        and not annotation_accepts_value(annotation, None)
    ):
        raise SchemaDefinitionError(
            f"Field {name!r} uses empty='none', but its annotation does not allow "
            "None; include None in the annotation or choose another empty policy",
            schema=cls.__name__,
        )
    if declared.empty == "parse" and declared.parser is None:
        raise SchemaDefinitionError(
            f"Field {name!r} uses empty='parse' but has no inferred or explicit "
            "parser; add parser=... or choose another empty policy",
            schema=cls.__name__,
        )
    if declared.parser is None and not annotation_accepts_raw_text(annotation):
        raise SchemaDefinitionError(
            f"Field {name!r} has no parser and would remain text, but its annotation "
            "does not accept raw str values; add an explicit parser or use a "
            "supported annotation",
            schema=cls.__name__,
        )


def _resolve_field_annotation(cls: type, field_name: str) -> Any:
    """Resolve the nearest declaring annotation for one field."""
    declaring_class = next(
        (
            candidate
            for candidate in cls.__mro__
            if field_name in candidate.__dict__.get("__annotations__", {})
        ),
        None,
    )
    if declaring_class is None:
        return _INVALID
    annotation = declaring_class.__dict__["__annotations__"][field_name]
    if not isinstance(annotation, str):
        return annotation

    module = sys.modules.get(declaring_class.__module__)
    globalns = vars(module) if module is not None else {}
    localns = dict(vars(declaring_class))
    localns[declaring_class.__name__] = declaring_class
    holder = type(
        "_TalikaFieldAnnotation",
        (),
        {
            "__annotations__": {"value": annotation},
            "__module__": declaring_class.__module__,
        },
    )
    try:
        return get_type_hints(holder, globalns=globalns, localns=localns)["value"]
    except (NameError, TypeError, SyntaxError):
        return _INVALID


def compile_schema(cls: type, fields: Mapping[str, Field]) -> SchemaPlan:
    """Validate one schema class and return its immutable plan."""
    labels: dict[str, str] = {}
    for field_name, declared in fields.items():
        if len(set(declared.labels)) != len(declared.labels):
            raise SchemaDefinitionError(
                f"Field {field_name!r} aliases must differ from its resolved label",
                schema=cls.__name__,
            )
        for label in declared.labels:
            if label in labels and labels[label] != field_name:
                raise SchemaDefinitionError(
                    f"Field label or alias {label!r} is already used by "
                    f"{labels[label]!r}",
                    schema=cls.__name__,
                )
            labels[label] = field_name

    orientation_value = getattr(cls, "__table_orientation__", None)
    try:
        orientation = (
            None if orientation_value is None else Orientation(orientation_value)
        )
    except ValueError as exc:
        raise SchemaDefinitionError(
            "Table orientation must be 'row' or 'column'",
            schema=cls.__name__,
        ) from exc

    try:
        unknown_fields = UnknownFieldPolicy(
            getattr(cls, "unknown_fields", UnknownFieldPolicy.FORBID.value)
        )
    except ValueError as exc:
        raise SchemaDefinitionError(
            "unknown_fields must be 'forbid'", schema=cls.__name__
        ) from exc
    try:
        inapplicable_fields = InapplicableFieldPolicy(
            getattr(
                cls,
                "inapplicable_fields",
                InapplicableFieldPolicy.FORBID.value,
            )
        )
    except ValueError as exc:
        raise SchemaDefinitionError(
            "inapplicable_fields must be 'forbid' or 'preserve'",
            schema=cls.__name__,
        ) from exc

    compiled = tuple(_compile_field(declared) for declared in fields.values())
    by_name = {item.name: item for item in compiled}
    by_label = {label: item for item in compiled for label in item.labels}
    ids = [item for item in compiled if item.is_id]
    discriminators = [item for item in compiled if item.is_discriminator]

    if not cls.__dict__.get("__talika_framework_base__", False):
        if orientation is Orientation.ROW and len(ids) > 1:
            raise SchemaDefinitionError(
                "RowTable schemas allow at most one id_field", schema=cls.__name__
            )
        if orientation is Orientation.COLUMN and len(ids) != 1:
            raise SchemaDefinitionError(
                "ColumnTable schemas require exactly one id_field",
                schema=cls.__name__,
            )

    if orientation is not None and not discriminators:
        for item in compiled:
            if item.reference is not None and item.reference.target not in by_name:
                raise SchemaDefinitionError(
                    f"Reference target field {item.reference.target!r} is not declared",
                    schema=cls.__name__,
                )

    transformer = getattr(cls, "table_transformer", None)
    if transformer is not None and not callable(
        getattr(transformer, "transform", None)
    ):
        raise SchemaDefinitionError(
            "table_transformer must provide a callable transform() method",
            schema=cls.__name__,
        )
    output_model = getattr(cls, "output_model", None)
    if output_model is not None and not callable(output_model):
        raise SchemaDefinitionError(
            "output_model must be callable", schema=cls.__name__
        )

    hook_names = (
        "transform_table",
        "validate_record",
        "validate_records",
        "build_output",
    )
    hooks: dict[str, Any] = {}
    for hook_name in hook_names:
        hook = getattr(cls, hook_name, None)
        if hook is not None and not callable(hook):
            raise SchemaDefinitionError(
                f"{hook_name} must be callable", schema=cls.__name__
            )
        hooks[hook_name] = hook

    build_output_owner = next(
        (owner for owner in cls.__mro__ if "build_output" in owner.__dict__),
        None,
    )
    if build_output_owner is not None and build_output_owner.__dict__.get(
        "__talika_framework_base__", False
    ):
        hooks["build_output"] = None

    reference_targets = {
        item.reference.target: by_name[item.reference.target]
        for item in compiled
        if item.reference is not None and item.reference.target in by_name
    }
    plan = SchemaPlan(
        schema_type=cls,
        display_name=cls.__dict__.get("__schema_display_name__", cls.__name__),
        orientation=orientation,
        fields=compiled,
        fields_by_name=immutable_mapping(by_name),
        fields_by_label=immutable_mapping(by_label),
        accepted_labels=frozenset(by_label),
        id_field=ids[0] if len(ids) == 1 else None,
        discriminator=discriminators[0] if len(discriminators) == 1 else None,
        variants=immutable_mapping({}),
        reference_targets=immutable_mapping(reference_targets),
        policies=SchemaPolicies(unknown_fields, inapplicable_fields),
        hooks=SchemaHooks(
            table_transformer=transformer,
            output_model=output_model,
            transform_table=hooks["transform_table"],
            validate_record=hooks["validate_record"],
            validate_records=hooks["validate_records"],
            build_output=hooks["build_output"],
        ),
    )
    for declared in fields.values():
        declared._freeze()
    return plan


def _compile_field(declared: Field) -> CompiledField:
    """Copy one declaration into immutable normalized metadata."""
    if declared._origin is None:
        raise RuntimeError("Cannot compile an unbound field")
    if declared.label is None:
        raise RuntimeError("Cannot compile a field before its label is resolved")
    return CompiledField(
        name=declared.name,
        origin=declared._origin,
        label=declared.label,
        aliases=declared.aliases,
        required=declared.required,
        default=declared.default,
        default_factory=declared.default_factory,
        parser=declared.parser,
        empty=EmptyPolicy(declared.empty),
        is_id=declared.is_id,
        is_discriminator=declared.is_discriminator,
        variants=declared.variants,
        reference=declared.reference,
        declaration=declared,
    )


def update_variant_plan(cls: Any) -> None:
    """Attach a new immutable family snapshot after variant registration."""
    current: SchemaPlan = cls.__schema_plan__
    variant_plans = {
        value: variant.__schema_plan__ for value, variant in cls.__variants__.items()
    }
    references = _reference_targets(current, variant_plans.values(), complete=False)
    type.__setattr__(
        cls,
        "__schema_plan__",
        current.with_variants(variant_plans, reference_targets=references),
    )


def validate_schema_family(cls: Any) -> None:
    """Validate the current variant family before parsing or describing it."""
    plan: SchemaPlan = cls.__schema_plan__
    if not plan.variants:
        _reference_targets(plan, (), complete=True)
        return
    if plan.discriminator is None:
        raise SchemaDefinitionError(
            "Schemas with registered variants require exactly one discriminator_field",
            schema=plan.display_name,
        )
    if sum(item.is_discriminator for item in plan.fields) != 1:
        raise SchemaDefinitionError(
            "Schemas with registered variants require exactly one discriminator_field",
            schema=plan.display_name,
        )
    for variant in plan.variants.values():
        discriminators = [item for item in variant.fields if item.is_discriminator]
        if len(discriminators) != 1:
            raise SchemaDefinitionError(
                "Each variant must inherit the base discriminator_field",
                schema=variant.display_name,
            )
        declared = discriminators[0]
        if (
            declared.name != plan.discriminator.name
            or declared.label != plan.discriminator.label
        ):
            raise SchemaDefinitionError(
                "Variants cannot replace the base discriminator_field",
                schema=variant.display_name,
            )
    _reference_targets(plan, plan.variants.values(), complete=True)


def seal_schema_family(cls: Any) -> None:
    """Validate and seal a schema family before table input is processed."""
    if cls.__dict__.get("__schema_sealed__", False):
        return
    validate_schema_family(cls)
    type.__setattr__(cls, "__schema_sealed__", True)


def _reference_targets(
    plan: SchemaPlan,
    variants: Any,
    *,
    complete: bool,
) -> dict[str, CompiledField]:
    """Resolve compatible target declarations across one schema family."""
    family = [plan, *variants]
    target_names: list[str] = []
    for member in family:
        for item in member.fields:
            if item.reference is not None and item.reference.target not in target_names:
                target_names.append(item.reference.target)

    targets: dict[str, CompiledField] = {}
    for target_name in target_names:
        candidates = [
            member.fields_by_name[target_name]
            for member in family
            if target_name in member.fields_by_name
        ]
        if not candidates:
            if complete:
                raise SchemaDefinitionError(
                    f"Reference target field {target_name!r} is not declared",
                    schema=plan.display_name,
                )
            continue
        parsers: list[object] = []
        for candidate in candidates:
            if not any(candidate.parser is parser for parser in parsers):
                parsers.append(candidate.parser)
        if len(parsers) > 1 and complete:
            raise SchemaDefinitionError(
                f"Reference target field {target_name!r} has ambiguous parsers; "
                "declare it on a common base or TableFields component",
                schema=plan.display_name,
            )
        if len(parsers) == 1:
            targets[target_name] = candidates[0]
    return targets


def read_only_fields(fields: Mapping[str, Field]) -> Mapping[str, Field]:
    """Return the compatibility field view backed by a private copy."""
    return MappingProxyType(dict(fields))
