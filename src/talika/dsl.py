"""Composable, project-owned cell parsing rules.

``CellDSL`` intentionally implements dispatch rather than domain syntax. A
project chooses its exact tokens, regular expressions, predicates, field
scopes, generated values, and fallback behavior.

!!! info
    The DSL is a parser factory for one field value at a time. It never
    changes table shape, performs business actions, or interprets symbols such
    as ``*`` unless a project registers that meaning.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from .context import CellContext

TokenHandler = Callable[[CellContext], Any]
PatternHandler = Callable[[re.Match[str], CellContext], Any]
Predicate = Callable[[str, CellContext], bool]
PredicateHandler = Callable[[str, CellContext], Any]
FallbackHandler = Callable[[str, CellContext], Any]


def _normalize_fields(fields: Iterable[str] | None) -> frozenset[str] | None:
    """Return an immutable field-name scope for one rule declaration.

    Args:
        fields: ``None`` for a global rule, one field name, or an iterable of
            field names.

    Returns:
        ``None`` for a global rule or a non-empty immutable field-name set.

    Raises:
        ValueError: If a scoped rule contains no usable field names.

    !!! warning
        Scopes use schema attribute names, not human-facing table labels.

    """
    if fields is None:
        return None
    if isinstance(fields, str):
        fields = (fields,)
    normalized = frozenset(fields)
    if not normalized or any(not field for field in normalized):
        raise ValueError("Cell DSL field scopes must contain field names")
    return normalized


def _applies(fields: frozenset[str] | None, context: CellContext) -> bool:
    """Return whether a rule is global or includes the current schema field.

    Args:
        fields: Normalized field scope or ``None`` for a global rule.
        context: Parser context for the cell being dispatched.

    Returns:
        ``True`` when the rule should be considered for the active field.

    !!! info
        Field scoping happens before pattern matching and predicate execution,
        so expensive project predicates can be limited to relevant fields.

    """
    return fields is None or context.field_name in fields


@dataclass(frozen=True)
class _TokenRule:
    """Registered exact-token rule used by ``CellDSL`` dispatch.

    Attributes:
        value: Exact cell text that triggers this rule.
        fields: Optional schema-field scope.
        handler: Callable that produces the parsed value.

    !!! info
        Token rules are internal immutable records so registration order and
        duplicate detection remain separate concerns.

    """

    value: str
    fields: frozenset[str] | None
    handler: TokenHandler


@dataclass(frozen=True)
class _PatternRule:
    """Registered full-match regular-expression rule.

    Attributes:
        source: Original pattern text used for duplicate detection.
        pattern: Compiled regular expression.
        fields: Optional schema-field scope.
        handler: Callable receiving the match and cell context.

    !!! warning
        Patterns use ``fullmatch`` during dispatch. Add ``.*`` explicitly when
        a project really wants substring behavior.

    """

    source: str
    pattern: re.Pattern[str]
    fields: frozenset[str] | None
    handler: PatternHandler


@dataclass(frozen=True)
class _PredicateRule:
    """Registered project predicate and matching handler.

    Attributes:
        predicate: Callable deciding whether a value should be handled.
        fields: Optional schema-field scope.
        handler: Callable receiving the original value and context.

    !!! warning
        Predicate functions should be side-effect free. They may be evaluated
        for cells that ultimately match only because the predicate returns
        true.

    """

    predicate: Predicate
    fields: frozenset[str] | None
    handler: PredicateHandler


class CellDSL:
    """Dispatch cell values to project-defined parsing handlers.

    Dispatch order is exact tokens, regular-expression patterns, predicates,
    and finally the optional fallback. For an exact token, field-scoped rules
    take precedence over a global rule with the same value. Pattern and
    predicate rules otherwise retain registration order.

    !!! example
        ```python
        content_cells = CellDSL()

        @content_cells.token("random", fields=("headline",))
        def random_headline(context):
            return context.user_data["faker"].headline()
        ```
    """

    def __init__(self) -> None:
        """Initialize an empty rule registry.

        !!! info
            Registration mutates only this DSL instance. Once the instance is
            attached to a schema field, parsing uses the rules accumulated on
            that object.
        """
        self._tokens: list[_TokenRule] = []
        self._token_keys: set[tuple[str, frozenset[str] | None]] = set()
        self._patterns: list[_PatternRule] = []
        self._pattern_keys: set[tuple[str, frozenset[str] | None]] = set()
        self._predicates: list[_PredicateRule] = []
        self._fallback: FallbackHandler | None = None

    def token(
        self,
        value: str,
        *,
        fields: Iterable[str] | None = None,
    ) -> Callable[[TokenHandler], TokenHandler]:
        """Register an exact token.

        Args:
            value: Exact cell text that should trigger the decorated handler.
            fields: Optional schema attribute name or names that limit where
                the token applies.

        Returns:
            A decorator that stores and returns the project handler unchanged.

        Raises:
            ValueError: If ``value`` is empty or the same token/scope pair is
                registered twice.

        !!! warning
            Field-scoped tokens use schema attribute names. A field declared as
            ``headline = field("Headline*")`` is scoped as ``"headline"``, not
            ``"Headline*"``.

        """
        if not value:
            raise ValueError("Cell DSL token cannot be empty")
        scope = _normalize_fields(fields)

        def register(handler: TokenHandler) -> TokenHandler:
            """Store the decorated token handler and return it unchanged.

            Args:
                handler: Project callable that receives ``CellContext``.

            Returns:
                The same handler so decorator syntax does not hide it.

            Raises:
                ValueError: If the exact token and scope are already
                    registered.

            !!! info
                Returning the original handler keeps tests free to call the
                project function directly when that is useful.

            """
            key = (value, scope)
            if key in self._token_keys:
                raise ValueError(
                    f"Cell DSL token {value!r} is already registered for this scope"
                )
            self._tokens.append(_TokenRule(value, scope, handler))
            self._token_keys.add(key)
            return handler

        return register

    def pattern(
        self,
        expression: str,
        *,
        fields: Iterable[str] | None = None,
    ) -> Callable[[PatternHandler], PatternHandler]:
        """Register a full-match regular expression.

        Args:
            expression: Regular-expression text compiled immediately.
            fields: Optional schema attribute name or names that limit where
                the pattern applies.

        Returns:
            A decorator that stores and returns the project handler unchanged.

        Raises:
            ValueError: If the same expression/scope pair is registered twice.
            re.error: If ``expression`` is not a valid regular expression.

        !!! info
            Pattern handlers receive the ``re.Match`` object so capture groups
            can become typed values without reparsing the cell text.

        """
        compiled = re.compile(expression)
        scope = _normalize_fields(fields)

        def register(handler: PatternHandler) -> PatternHandler:
            """Store the decorated pattern handler and return it unchanged.

            Args:
                handler: Project callable receiving ``re.Match`` and
                    ``CellContext``.

            Returns:
                The same handler supplied by the caller.

            Raises:
                ValueError: If this expression and scope were already
                    registered.

            !!! warning
                Registration order matters for patterns. Put more specific
                expressions before broader ones.

            """
            key = (expression, scope)
            if key in self._pattern_keys:
                raise ValueError(
                    f"Cell DSL pattern {expression!r} is already registered "
                    "for this scope"
                )
            self._patterns.append(_PatternRule(expression, compiled, scope, handler))
            self._pattern_keys.add(key)
            return handler

        return register

    def when(
        self,
        predicate: Predicate,
        *,
        fields: Iterable[str] | None = None,
    ) -> Callable[[PredicateHandler], PredicateHandler]:
        """Register a project predicate for syntax awkward to express as regex.

        Predicates run after exact tokens and regular expressions. They should
        return a boolean and avoid side effects because only the handler's
        return value becomes the parsed cell value.

        Args:
            predicate: Callable that decides whether a value should match.
            fields: Optional schema attribute name or names that limit where
                the predicate applies.

        Returns:
            A decorator that stores and returns the predicate handler.

        !!! warning
            Predicates are tried in registration order after token and pattern
            rules. Keep them cheap and deterministic.

        """
        scope = _normalize_fields(fields)

        def register(handler: PredicateHandler) -> PredicateHandler:
            """Store the decorated predicate handler and return it unchanged.

            Args:
                handler: Project callable receiving the value and context.

            Returns:
                The same handler supplied by the caller.

            !!! info
                Predicate registration intentionally permits multiple
                overlapping predicates. First match wins at dispatch time.

            """
            self._predicates.append(_PredicateRule(predicate, scope, handler))
            return handler

        return register

    def fallback(self, handler: FallbackHandler) -> FallbackHandler:
        """Register behavior for values that match no explicit rule.

        Args:
            handler: Project callable receiving the raw value and context.

        Returns:
            The same handler supplied by the caller.

        Raises:
            ValueError: If a fallback is already registered.

        !!! warning
            A fallback makes the DSL match every value, which also affects
            ``CellDSLChain`` composition. Use it only when the DSL should own
            unmatched values.

        """
        if self._fallback is not None:
            raise ValueError("Cell DSL fallback is already registered")
        self._fallback = handler
        return handler

    def compose(self, *others: CellDSL) -> CellDSLChain:
        """Return a first-match chain beginning with this DSL.

        Args:
            *others: Additional DSLs consulted after this one.

        Returns:
            A ``CellDSLChain`` parser.

        !!! example
            ```python
            parser = shared_cells.compose(project_cells)
            value = parser("random", context)
            ```

        """
        return CellDSLChain((self, *others))

    def _dispatch(self, value: str, context: CellContext) -> tuple[bool, Any]:
        """Return ``(matched, result)`` for composition-aware dispatch.

        Args:
            value: Current logical cell value.
            context: Parser context for the active schema field.

        Returns:
            ``(True, parsed_value)`` when a rule or fallback handles the value,
            otherwise ``(False, value)``.

        !!! info
            ``CellDSLChain`` uses the matched flag to distinguish "a DSL
            intentionally returned the original text" from "this DSL did not
            match".

        """
        token_rules = [rule for rule in self._tokens if rule.value == value]
        token_rules.sort(key=lambda rule: rule.fields is None)
        for token_rule in token_rules:
            if _applies(token_rule.fields, context):
                return True, token_rule.handler(context)

        for pattern_rule in self._patterns:
            if not _applies(pattern_rule.fields, context):
                continue
            match = pattern_rule.pattern.fullmatch(value)
            if match is not None:
                return True, pattern_rule.handler(match, context)

        for predicate_rule in self._predicates:
            if _applies(predicate_rule.fields, context) and predicate_rule.predicate(
                value, context
            ):
                return True, predicate_rule.handler(value, context)

        if self._fallback is not None:
            return True, self._fallback(value, context)
        return False, value

    def __call__(self, value: str, context: CellContext) -> Any:
        """Parse one value or pass it through when no rule matches.

        Args:
            value: Current logical cell value.
            context: Parser context for the active schema field.

        Returns:
            The parsed value from the first matching rule, fallback result, or
            original text when no rule applies.

        !!! info
            This method satisfies the same callable contract as ordinary field
            parsers, so a ``CellDSL`` instance can be passed directly to
            ``field(parser=...)``.

        """
        _, result = self._dispatch(value, context)
        return result


class CellDSLChain:
    """Ask several ``CellDSL`` objects in first-match order.

    Attributes:
        dsls: Immutable ordered DSL sequence consulted during parsing.

    !!! info
        Chains are useful when a project has shared tokens plus feature-area
        specific rules. The first DSL that reports a match owns the result.

    """

    def __init__(self, dsls: Sequence[CellDSL]) -> None:
        """Validate and store composed DSLs.

        Args:
            dsls: Ordered sequence of ``CellDSL`` instances.

        Raises:
            ValueError: If no DSLs are supplied.
            TypeError: If any item is not a ``CellDSL``.

        !!! warning
            A DSL with a fallback always matches, so later DSLs in the chain
            will never see values that reach it.

        """
        if not dsls:
            raise ValueError("CellDSLChain requires at least one DSL")
        if not all(isinstance(dsl, CellDSL) for dsl in dsls):
            raise TypeError("CellDSLChain accepts only CellDSL instances")
        self.dsls = tuple(dsls)

    def __call__(self, value: str, context: CellContext) -> Any:
        """Return the first result from the composed DSLs.

        Args:
            value: Current logical cell value.
            context: Parser context for the active schema field.

        Returns:
            Parsed value from the first matching DSL, or the original text when
            none match.

        !!! info
            The original value can still be a deliberate parsed result when a
            DSL matches and returns it; the chain preserves that distinction.

        """
        for dsl in self.dsls:
            matched, result = dsl._dispatch(value, context)
            if matched:
                return result
        return value


def compose_cell_dsls(*dsls: CellDSL) -> CellDSLChain:
    """Compose reusable and project-specific cell grammars.

    Args:
        *dsls: Ordered DSLs, with earlier DSLs taking priority.

    Returns:
        A ``CellDSLChain`` parser.

    !!! example
        ```python
        parser = compose_cell_dsls(shared_cells, article_cells)
        headline = field("Headline*", parser=parser)
        ```

    """
    return CellDSLChain(dsls)
