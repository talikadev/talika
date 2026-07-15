"""Infer field parsers from supported Python type annotations.

This module keeps annotation handling intentionally conservative. It only
infers parsers for types with obvious, local conversion semantics and returns
``None`` for annotations that should remain raw text.

!!! info
    Explicit ``field(parser=...)`` values always win. Annotation inference is
    a convenience for common schema declarations, not a second parser registry.
"""

from __future__ import annotations

import types
from decimal import Decimal
from enum import Enum
from typing import Any, Literal, Union, get_args, get_origin

from .fields import Parser
from .parsers import boolean, decimal, floating, integer, optional


def annotation_accepts_raw_text(annotation: Any) -> bool:
    """Return whether arbitrary unparsed cell text fits an annotation.

    Args:
        annotation: Resolved annotation attached to a schema field.

    Returns:
        ``True`` for ``Any``, ``object``, ``str``, or a union containing one
        of those types. Literal annotations return ``False`` because an
        arbitrary cell is not guaranteed to match their finite vocabulary.


    !!! info
        This helper validates only Talika's raw-text path. It does not inspect
        or constrain values returned by explicit project parsers.

    """
    if annotation in (Any, object, str):
        return True
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType):
        return any(annotation_accepts_raw_text(item) for item in get_args(annotation))
    return False


def annotation_accepts_value(annotation: Any, value: Any) -> bool:
    """Return whether one framework-created value fits an annotation.

    Args:
        annotation: Resolved field annotation.
        value: Missing, empty-policy, or static-default value created directly
            by Talika.

    Returns:
        Whether the value matches common runtime-checkable annotations.
        Unsupported typing constructs are treated conservatively as not
        matching unless they expose a runtime origin that accepts the value.


    !!! warning
        This is deliberately not a general-purpose Python type checker. It is
        used only for declaration paths controlled by the framework.

    """
    if annotation in (Any, object):
        return True
    if annotation is None or annotation is type(None):
        return value is None

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (Union, types.UnionType):
        return any(annotation_accepts_value(item, value) for item in arguments)
    if origin is Literal:
        return any(
            type(value) is type(allowed) and value == allowed for allowed in arguments
        )
    if origin is tuple:
        if not isinstance(value, tuple):
            return False
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            return all(annotation_accepts_value(arguments[0], item) for item in value)
        return len(value) == len(arguments) and all(
            annotation_accepts_value(item_annotation, item)
            for item_annotation, item in zip(arguments, value, strict=True)
        )
    if origin in (list, set, frozenset):
        if not isinstance(value, origin):
            return False
        return not arguments or all(
            annotation_accepts_value(arguments[0], item) for item in value
        )
    if origin is dict:
        if not isinstance(value, dict):
            return False
        if len(arguments) != 2:
            return True
        key_type, value_type = arguments
        return all(
            annotation_accepts_value(key_type, key)
            and annotation_accepts_value(value_type, item)
            for key, item in value.items()
        )
    if origin is not None:
        try:
            return isinstance(value, origin)
        except TypeError:
            return False
    if annotation in (str, int, float, bool, bytes):
        return type(value) is annotation
    try:
        return isinstance(value, annotation)
    except TypeError:
        return False


def parser_for_annotation(annotation: Any) -> Parser | None:
    """Return a parser for one supported annotation.

    Args:
        annotation: The runtime annotation object gathered from a schema
            attribute, usually through ``typing.get_type_hints``.

    Returns:
        A parser compatible with ``field(parser=...)`` when the annotation is
        supported, or ``None`` when Talika cannot infer a conversion. Schema
        compilation then verifies whether an unparsed string is compatible
        with the annotation.

    !!! info
        Supported annotations are ``str``, ``int``, ``float``, ``bool``,
        ``Decimal``, enums, string ``Literal`` values, and optional unions
        containing exactly one non-``None`` type.

    !!! warning
        Unsupported unions deliberately return ``None``. This prevents
        ambiguous coercion when more than one non-null type could accept the
        same cell text.

    !!! example
        ```python
        class UserTable(RowTable):
            age: int = field("age", required=True)
            reviewer: int | None = field("reviewer", empty="parse")
        ```

    """
    if annotation in (Any, str):
        return None
    if annotation is int:
        return integer()
    if annotation is float:
        return floating()
    if annotation is bool:
        return boolean()
    if annotation is Decimal:
        return decimal()
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return _enum_parser(annotation)

    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (Union, types.UnionType):
        non_none = [argument for argument in arguments if argument is not type(None)]
        if len(non_none) == 1 and len(non_none) != len(arguments):
            parser = parser_for_annotation(non_none[0]) or _identity
            return optional(parser)
        return None
    if (
        origin is Literal
        and arguments
        and all(isinstance(argument, str) for argument in arguments)
    ):
        allowed = tuple(arguments)

        def parse_literal(value: Any, context: Any) -> str:
            """Validate that a cell exactly matches one literal string.

            Args:
                value: Current logical cell value after table transformation.
                context: Parser context supplied by the schema lifecycle.

            Returns:
                The original string value when it is one of the allowed
                literals.

            Raises:
                ValueError: If the cell value is not registered in the
                    annotation's literal set.

            !!! warning
                Literal parsing is intentionally exact and does not normalize
                whitespace or case. Add an explicit parser when a project wants
                looser matching.

            """
            if value not in allowed:
                raise ValueError(f"Expected one of {list(allowed)!r}")
            return value

        return parse_literal
    return None


def _identity(value: Any, context: Any) -> Any:
    """Return ``value`` unchanged for composed inferred parsers.

    Args:
        value: Current parser input.
        context: Parser context supplied by the schema lifecycle.

    Returns:
        The same object received as ``value``.

    !!! info
        This helper is used inside inferred ``Optional`` parsers when the inner
        annotation means "keep this value as-is".

    """
    return value


def _enum_parser(enum_type: type[Enum]) -> Parser:
    """Return a parser that matches enum values before member names.

    Args:
        enum_type: Enum subclass used by a schema field annotation.

    Returns:
        A parser that converts cell text into a member of ``enum_type``.

    !!! info
        Matching enum values first lets feature files use domain-facing values
        while still accepting member names for tests that prefer Python
        identifiers.

    """

    def parse(value: Any, context: Any) -> Enum:
        """Convert one cell value into an enum member.

        Args:
            value: Current logical cell value after table transformation.
            context: Parser context supplied by the schema lifecycle.

        Returns:
            The enum member whose value or name matches the cell text.

        Raises:
            ValueError: If no enum member matches the cell text.

        !!! warning
            Matching is string-based. Use an explicit parser when enum values
            need locale-aware, case-insensitive, or numeric normalization.

        """
        raw = str(value)
        for member in enum_type:
            if str(member.value) == raw or member.name == raw:
                return member
        choices = [str(member.value) for member in enum_type]
        raise ValueError(f"Expected one of {choices!r}")

    return parse
