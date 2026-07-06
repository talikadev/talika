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


def parser_for_annotation(annotation: Any) -> Parser | None:
    """Return a parser for one supported annotation.

    Args:
        annotation: The runtime annotation object gathered from a schema
            attribute, usually through ``typing.get_type_hints``.

    Returns:
        A parser compatible with ``field(parser=...)`` when the annotation is
        supported, or ``None`` when the value should be left as the raw string.

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
            age: int = field("age")
            reviewer: int | None = field("reviewer")
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
