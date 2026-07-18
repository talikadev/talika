"""Reusable field parsers and parser-composition helpers.

Every parser follows the same callable contract used by ``field(parser=...)``:
it accepts the current value and a :class:`~talika.CellContext`. Parser
factories return plain callable objects, so projects can use them directly,
compose them, or mix them with custom functions.

!!! info
    Parser factories in this module do not know BDD business vocabulary. They
    provide small, predictable conversion primitives that project schemas can
    combine into their own table language.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime as DateTime
from decimal import Decimal
from typing import Any

from .context import CellContext
from .fields import Parser


def string(*, strip: bool = False, lower: bool = False, upper: bool = False) -> Parser:
    """Return a parser that normalizes text.

    Args:
        strip: Remove leading and trailing whitespace before case conversion.
        lower: Convert the resulting text to lowercase.
        upper: Convert the resulting text to uppercase.

    Returns:
        A parser that always returns ``str``.

    Raises:
        ValueError: If both ``lower`` and ``upper`` are enabled.

    !!! warning
        This parser deliberately performs no semantic validation. Use
        ``choice()`` or a custom parser when the table cell must be one of a
        known set of values.

    !!! example
        ```python
        class UserTable(RowTable):
            role = field("role", parser=string(strip=True, lower=True))
        ```

    """
    if lower and upper:
        raise ValueError("string parser cannot enable both lower and upper")

    def parse(value: Any, context: CellContext) -> str:
        """Normalize one value according to the factory options.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            The value converted to text and normalized in a deterministic
            order: string conversion, optional stripping, then case handling.

        !!! info
            The context is accepted for parser compatibility even though this
            built-in parser does not inspect it.

        """
        result = str(value)
        if strip:
            result = result.strip()
        if lower:
            result = result.lower()
        if upper:
            result = result.upper()
        return result

    return parse


def integer(*, base: int = 10) -> Parser:
    """Return a parser that converts values to ``int``.

    Args:
        base: Numeric base used when the incoming value is a string.

    Returns:
        A parser that returns an integer.

    !!! warning
        The base is passed to Python's ``int(value, base)`` only for strings.
        Non-string values use ``int(value)`` so already-typed project values
        still follow Python's normal conversion rules.

    !!! example
        ```python
        class Flags(RowTable):
            mask = field("mask", parser=integer(base=16))
        ```

    """

    def parse(value: Any, context: CellContext) -> int:
        """Convert one value to an integer.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            ``value`` converted with Python's integer conversion semantics.

        Raises:
            ValueError: If the value cannot be parsed as an integer.

        !!! info
            Schema parsing wraps this failure in ``TableError`` so callers
            receive the field and source-cell location.

        """
        return int(value, base) if isinstance(value, str) else int(value)

    return parse


def floating() -> Parser:
    """Return a parser that converts values to ``float``.

    Returns:
        A parser that returns a Python ``float``.

    !!! warning
        Use ``decimal()`` instead when tests need exact decimal arithmetic or
        should avoid binary floating-point representation.

    !!! example
        ```python
        class Product(RowTable):
            rating = field("rating", parser=floating())
        ```

    """

    def parse(value: Any, context: CellContext) -> float:
        """Convert one value to ``float``.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            ``value`` converted by Python's ``float`` constructor.

        !!! info
            The parser is intentionally thin so Python's own accepted float
            syntax remains the single source of truth.

        """
        return float(value)

    return parse


def decimal() -> Parser:
    """Return a parser that converts through text to ``Decimal``.

    Returns:
        A parser that returns ``decimal.Decimal``.

    !!! info
        Conversion goes through ``str(value)`` so existing numeric objects and
        raw table text follow the same exact decimal path.

    !!! example
        ```python
        class PriceTable(RowTable):
            total = field("total", parser=decimal())
        ```

    """

    def parse(value: Any, context: CellContext) -> Decimal:
        """Convert one value to ``Decimal``.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            A ``Decimal`` created from the text form of ``value``.

        Raises:
            decimal.InvalidOperation: If the text is not a valid decimal.

        !!! warning
            Empty strings are not treated as ``None`` here. Compose with
            ``optional(decimal())`` when blank or null-like tokens are valid.

        """
        return Decimal(str(value))

    return parse


def _validate_temporal_format(format: str, *, parser_name: str) -> None:
    """Validate a date or datetime parser format declaration."""
    if not isinstance(format, str):
        raise TypeError(f"{parser_name} format must be a string")
    if not format:
        raise ValueError(f"{parser_name} format cannot be empty")


@dataclass(frozen=True, slots=True)
class _DateParser:
    format: str

    @property
    def description(self) -> str:
        """Return the configured date parser contract."""
        return f"date(format={self.format!r})"

    def __call__(self, value: Any, context: CellContext) -> Date:
        """Parse one value into a calendar date."""
        return DateTime.strptime(str(value), self.format).date()


def date(*, format: str = "%Y-%m-%d") -> Parser:
    """Return a parser that converts text to ``datetime.date``.

    Args:
        format: One deterministic ``datetime.strptime`` format. The default
            accepts dates written as ``YYYY-MM-DD``.

    Returns:
        A parser that returns a Python ``date``.

    Raises:
        TypeError: If ``format`` is not a string.
        ValueError: If ``format`` is empty.

    !!! warning
        The parser does not strip whitespace or try several formats. Compose
        it with ``string(strip=True)`` or configure the exact format when the
        authored table uses a different syntax.

    !!! example
        ```python
        class Schedule(RowTable):
            due = field("due", parser=date())
            reviewed = field("reviewed", parser=date(format="%d/%m/%Y"))
        ```

    """
    _validate_temporal_format(format, parser_name="date")
    return _DateParser(format)


@dataclass(frozen=True, slots=True)
class _DateTimeParser:
    format: str

    @property
    def description(self) -> str:
        """Return the configured datetime parser contract."""
        return f"datetime(format={self.format!r})"

    def __call__(self, value: Any, context: CellContext) -> DateTime:
        """Parse one value into a date and time."""
        return DateTime.strptime(str(value), self.format)


def datetime(*, format: str = "%Y-%m-%dT%H:%M:%S") -> Parser:
    """Return a parser that converts text to ``datetime.datetime``.

    Args:
        format: One deterministic ``datetime.strptime`` format. The default
            accepts datetimes written as ``YYYY-MM-DDTHH:MM:SS``.

    Returns:
        A parser that returns a Python ``datetime``. The default format creates
        a naive value; formats containing ``%z`` create timezone-aware values.

    Raises:
        TypeError: If ``format`` is not a string.
        ValueError: If ``format`` is empty.

    !!! warning
        The parser does not strip whitespace, normalize timezones, or accept
        ISO variants that are absent from the configured format.

    !!! example
        ```python
        class Events(RowTable):
            created = field("created", parser=datetime())
            local = field("local", parser=datetime(format="%d/%m/%Y %H:%M"))
        ```

    """
    _validate_temporal_format(format, parser_name="datetime")
    return _DateTimeParser(format)


@dataclass(frozen=True, slots=True)
class _BooleanParser:
    accepted_true: frozenset[str]
    accepted_false: frozenset[str]
    case_sensitive: bool

    @property
    def description(self) -> str:
        true_contract = tuple(sorted(self.accepted_true))
        false_contract = tuple(sorted(self.accepted_false))
        return (
            f"boolean(true_values={true_contract!r}, "
            f"false_values={false_contract!r}, "
            f"case_sensitive={self.case_sensitive!r})"
        )

    def __call__(self, value: Any, context: CellContext) -> bool:
        normalize = (lambda token: token) if self.case_sensitive else str.lower
        normalized = normalize(str(value))
        if normalized in self.accepted_true:
            return True
        if normalized in self.accepted_false:
            return False
        accepted = sorted(self.accepted_true | self.accepted_false)
        raise ValueError(f"Expected one of {accepted!r}")


def _configured_parser_description(value: Any) -> str | None:
    if isinstance(value, (_BooleanParser, _DateParser, _DateTimeParser)):
        return value.description
    return None


def _boolean_tokens(
    values: Iterable[str],
    *,
    option: str,
    case_sensitive: bool,
) -> frozenset[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
        raise TypeError(f"{option} must be a non-string iterable of strings")
    tokens = tuple(values)
    if any(not isinstance(value, str) for value in tokens):
        raise TypeError(f"{option} must contain only strings")
    if case_sensitive:
        return frozenset(tokens)
    return frozenset(value.lower() for value in tokens)


def boolean(
    *,
    true_values: Iterable[str] = ("true",),
    false_values: Iterable[str] = ("false",),
    case_sensitive: bool = False,
) -> Parser:
    """Return a boolean parser with an explicit accepted vocabulary.

    Args:
        true_values: Strings accepted as ``True``.
        false_values: Strings accepted as ``False``.
        case_sensitive: Whether matching should preserve case.

    Returns:
        A parser that returns ``bool``.

    Raises:
        TypeError: If token collections or ``case_sensitive`` have invalid
            types.
        ValueError: If the true and false token sets overlap.

    !!! important "The default vocabulary is deliberately small"
        Without configuration, the parser accepts only ``"true"`` and
        ``"false"``. Matching is case-insensitive by default, so ``"TRUE"``
        and ``"False"`` also work. Words such as ``"yes"`` and ``"on"`` and
        numeric flags such as ``"1"`` must be declared by the schema.

    !!! warning
        Unknown values fail instead of falling back to Python truthiness. This
        prevents cells such as ``"False"`` or ``"nope"`` from accidentally
        becoming true.

    !!! warning "Whitespace is not removed"
        ``" true "`` is different from ``"true"``. Compose ``string(strip=True)``
        before this parser when the authored format permits padding.

    !!! example
        ```python
        active = field(
            "active",
            parser=boolean(true_values=("Y",), false_values=("N",)),
        )
        ```

    """
    if not isinstance(case_sensitive, bool):
        raise TypeError("case_sensitive must be a boolean")
    accepted_true = _boolean_tokens(
        true_values,
        option="true_values",
        case_sensitive=case_sensitive,
    )
    accepted_false = _boolean_tokens(
        false_values,
        option="false_values",
        case_sensitive=case_sensitive,
    )
    overlap = accepted_true & accepted_false
    if overlap:
        raise ValueError(f"Boolean true and false values overlap: {sorted(overlap)!r}")

    return _BooleanParser(
        accepted_true=accepted_true,
        accepted_false=accepted_false,
        case_sensitive=case_sensitive,
    )


def choice(*values: str, case_sensitive: bool = True) -> Parser:
    """Return a parser that validates one allowed string value.

    Args:
        *values: Accepted display values.
        case_sensitive: Whether input must match the case of an accepted value.

    Returns:
        A parser that returns the canonical value from ``values``.

    Raises:
        ValueError: If no values are supplied.

    !!! info
        With ``case_sensitive=False``, the returned value is still the
        canonical spelling passed to the factory.

    !!! example
        ```python
        role = field("role", parser=choice("admin", "editor", "viewer"))
        ```

    """
    if not values:
        raise ValueError("choice parser requires at least one allowed value")
    if case_sensitive:
        accepted = {value: value for value in values}
    else:
        accepted = {value.lower(): value for value in values}

    def parse(value: Any, context: CellContext) -> str:
        """Validate one cell against the accepted choices.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            The canonical accepted string.

        Raises:
            ValueError: If the value is not one of the configured choices.

        !!! warning
            This parser does not strip whitespace. Compose it after
            ``string(strip=True)`` when feature files may contain padding.

        """
        raw = str(value)
        key = raw if case_sensitive else raw.lower()
        if key not in accepted:
            raise ValueError(f"Expected one of {list(values)!r}")
        return accepted[key]

    return parse


def split(
    separator: str = ",",
    *,
    strip_items: bool = True,
    keep_empty: bool = False,
) -> Parser:
    """Return a parser that splits one cell into a list of strings.

    Args:
        separator: Text separator used between items.
        strip_items: Strip whitespace around each split item.
        keep_empty: Preserve empty segments instead of filtering them out.

    Returns:
        A parser that returns ``list[str]``.

    Raises:
        ValueError: If ``separator`` is empty.

    !!! info
        This parser is often paired with ``each(...)`` when a table cell holds
        a compact list of typed values.

    !!! example
        ```python
        tags = field("tags", parser=split(","))
        ```

    """
    if not separator:
        raise ValueError("split separator cannot be empty")

    def parse(value: Any, context: CellContext) -> list[str]:
        """Split one value into string items.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            The split items after optional stripping and empty-value filtering.

        !!! warning
            Splitting is purely textual. Escaped separators or quoted items
            require a project-specific parser.

        """
        items = str(value).split(separator)
        if strip_items:
            items = [item.strip() for item in items]
        if not keep_empty:
            items = [item for item in items if item != ""]
        return items

    return parse


def map_value(values: Mapping[str, Any], *, case_sensitive: bool = True) -> Parser:
    """Return a parser that maps cell strings to Python values.

    Args:
        values: Mapping from table text to the Python value to return.
        case_sensitive: Whether lookup should preserve case.

    Returns:
        A parser that returns the mapped value.

    !!! info
        This is useful for compact BDD vocabulary such as ``"TBD"`` becoming
        a sentinel object or ``"high"`` becoming a domain enum value.

    !!! example
        ```python
        priority = field("priority", parser=map_value({"low": 1, "high": 3}))
        ```

    """
    mapping = dict(values)
    if not case_sensitive:
        mapping = {str(key).lower(): value for key, value in mapping.items()}

    def parse(value: Any, context: CellContext) -> Any:
        """Look up one cell value in the configured mapping.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            The mapped Python value.

        Raises:
            ValueError: If the value has no mapping.

        !!! warning
            When matching is case-insensitive, duplicate lowercase keys are
            resolved by normal dictionary construction. Keep mappings
            unambiguous.

        """
        raw = str(value)
        key = raw if case_sensitive else raw.lower()
        if key not in mapping:
            raise ValueError(f"No mapped value for {raw!r}")
        return mapping[key]

    return parse


def compose(*parsers: Parser) -> Parser:
    """Run parsers left-to-right.

    Args:
        *parsers: Parser callables following the talika parser contract.

    Returns:
        A parser that feeds each result into the next parser.

    Raises:
        ValueError: If no parsers are supplied.

    !!! info
        Every parser receives the same ``CellContext`` so later stages still
        know the original field, item ID, and source value.

    !!! example
        ```python
        scores = field("scores", parser=compose(split(","), each(integer())))
        ```

    """
    if not parsers:
        raise ValueError("compose requires at least one parser")

    def parse(value: Any, context: CellContext) -> Any:
        """Apply the configured parser pipeline to one value.

        Args:
            value: Initial parser input.
            context: Source-aware parser context for the active field.

        Returns:
            The final value produced by the last parser.

        Raises:
            Exception: Any exception raised by a stage is allowed to propagate
                so schema parsing can wrap it with table diagnostics.

        !!! warning
            Parser order matters. A parser that expects a list should come
            after a parser such as ``split()`` that creates one.

        """
        result = value
        for parser in parsers:
            result = parser(result, context)
        return result

    return parse


def each(parser: Parser) -> Parser:
    """Apply one parser to every item in an iterable value.

    Args:
        parser: Parser applied to each non-string item.

    Returns:
        A parser that returns ``list[Any]``.

    !!! info
        ``each()`` is designed for composition after parsers that produce a
        sequence, such as ``split()``.

    !!! example
        ```python
        ids = field("ids", parser=compose(split(","), each(integer())))
        ```

    """

    def parse(values: Any, context: CellContext) -> list[Any]:
        """Parse every item in one iterable value.

        Args:
            values: Iterable parser input. Strings and bytes are rejected so a
                single cell is not accidentally iterated character by
                character.
            context: Source-aware parser context for the active field.

        Returns:
            A list containing one parsed value for each input item.

        Raises:
            ValueError: If ``values`` is a string, bytes, or non-iterable.

        !!! warning
            The same ``CellContext`` is reused for every item because the
            source location is still one original table cell.

        """
        if isinstance(values, (str, bytes)) or not isinstance(values, Iterable):
            raise ValueError("each parser expects a non-string iterable")
        return [parser(value, context) for value in values]

    return parse


@dataclass(frozen=True)
class _OptionalParser:
    """Parser wrapper that converts configured null-like tokens to ``None``.

    Attributes:
        parser: Parser used when the value is not null-like.
        none_values: Normalized tokens that should become ``None``.
        case_sensitive: Whether null-token matching preserves case.
    !!! info
        Field declarations decide whether explicit empty cells reach this
        parser through ``empty="parse"``.

    """

    parser: Parser
    none_values: frozenset[str]
    case_sensitive: bool

    def __call__(self, value: Any, context: CellContext) -> Any:
        """Return ``None`` for null-like input or delegate to the wrapped parser.

        Args:
            value: Current logical cell value.
            context: Source-aware parser context for the active field.

        Returns:
            ``None`` for empty or configured null tokens; otherwise the wrapped
            parser's result.

        !!! warning
            Empty strings are always treated as ``None`` by this wrapper. Use a
            custom parser when empty text is a meaningful domain value.

        """
        raw = str(value)
        normalized = raw if self.case_sensitive else raw.lower()
        if raw == "" or normalized in self.none_values:
            return None
        return self.parser(value, context)


def optional(
    parser: Parser,
    *,
    none_values: Iterable[str] = ("none", "null"),
    case_sensitive: bool = False,
) -> Parser:
    """Return a parser that maps empty or null-like tokens to ``None``.

    Args:
        parser: Parser used for non-null values.
        none_values: Text tokens that should parse as ``None``.
        case_sensitive: Whether matching ``none_values`` should preserve case.

    Returns:
        A parser object that converts empty or configured null-like values to
        ``None`` when the field invokes it.

    !!! info
        Use ``field(..., empty="parse")`` when an explicit blank cell should
        reach the returned parser. Without that field policy, blanks follow
        the field's normal empty-cell behavior.

    !!! example
        ```python
        due_date = field("due", parser=optional(string(strip=True)))
        ```

    """
    normalize = (lambda value: value) if case_sensitive else str.lower
    normalized = frozenset(normalize(str(value)) for value in none_values)
    return _OptionalParser(parser, normalized, case_sensitive)
