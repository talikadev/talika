---
icon: lucide/regex
---

# CellDSL Patterns

Exact tokens are good for fixed words such as `random` or `today`. Patterns
are for project vocabulary that has a small amount of structure inside the
cell.

Examples include:

- `3 words`
- `CMS:market-brief`
- `user:alice`
- `between 1 and 5`
- `tag:news,markets`

The cell is still authored as plain text. The pattern gives that text a
controlled meaning for one schema field.

```gherkin title="A table with a patterned cell"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:feature-patterns"
```

!!! tip "Use patterns for parameterized vocabulary"
    If the value has a number, name, slug, or other parameter inside it, use a
    pattern or predicate instead of registering many exact tokens.

## Register a Regex Pattern

Create a `CellDSL` and register a regular expression with `pattern(...)`.

```python title="A pattern with a named capture"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-dsl"
```

The handler receives two arguments:

- `match`, the regular-expression match object
- `context`, the same cell context passed to other field parsers

Named groups keep the handler readable. Here, `match["count"]` becomes the
number of words to generate.

```python title="A content schema using the pattern"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-schema"
```

```python title="A compact generated headline"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-table"
```

```bash { .talika-terminal title="Pattern result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-output"
```

The authored cell `3 words` is not returned as text. The pattern handler turns
it into the parsed headline value for that field.

!!! note "Pattern handlers return parsed values"
    A pattern handler can return a string, list, number, enum, dataclass, or
    any other value the field should hold. It follows the same field-parser
    contract as ordinary parser functions.

## Patterns Use Full Match

Pattern rules use regular-expression `fullmatch`, not substring search.

```python title="Values that do and do not full-match"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:fullmatch-table"
```

```bash { .talika-terminal title="Full-match behavior" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:fullmatch-output"
```

Only `3 words` matches the full pattern. `prefix 3 words` and
`3 words please` do not match, so they pass through unchanged.

This is deliberate. A pattern should describe the whole authored cell. If a
project really wants substring behavior, make that explicit in the expression
with `.*`.

!!! warning "Do not rely on accidental substring matches"
    Full-match behavior keeps table vocabulary predictable. A broad substring
    match can accidentally reinterpret ordinary prose as project syntax.

## Pattern Order Matters

Pattern rules are tried in registration order after exact tokens.

```python title="Specific pattern before catch-all"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-order"
```

```bash { .talika-terminal title="First matching pattern wins" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-order-output"
```

The first value matches `\d+ words`, so the specific handler runs. The second
value does not match that pattern, so the catch-all pattern handles it.

Keep specific patterns before broad patterns. A pattern such as `.*` should be
near the end because it can match almost anything.

!!! note "Dispatch order inside one DSL"
    CellDSL dispatch is exact tokens first, then patterns, then predicates,
    then fallback. This page focuses on the last three rule types; exact tokens
    keep their higher priority.

## Use Predicates for Awkward Syntax

Some project syntax is easier to express as Python code than as a regular
expression. Use `when(...)` for that.

```python title="A predicate rule for CMS-prefixed values"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:predicate-dsl"
```

Predicates receive the current value and context, and return `True` when the
handler should run. The handler also receives the original value and context.

```python title="A schema using a predicate DSL"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:predicate-schema"
```

```bash { .talika-terminal title="Predicate result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:predicate-output"
```

The predicate is scoped to `headline`, so `CMS:market-brief` becomes
`Market Brief`, while `CMS:draft` in `status` stays literal.

!!! warning "Keep predicates cheap"
    Predicates may be evaluated for many cells. They should be deterministic,
    quick, and free of side effects. Put the expensive work in the handler
    after the predicate has matched.

## Use Fallback for Owned Fields

By default, unmatched values pass through unchanged. A fallback changes that:
it handles any value that did not match a token, pattern, or predicate.

```python title="A status DSL with fallback normalization"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:fallback-dsl"
```

```python title="A status schema"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:fallback-schema"
```

```bash { .talika-terminal title="Fallback result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:fallback-output"
```

The exact token `published` still wins before fallback. The other status values
do not match explicit rules, so fallback normalizes them.

Use fallback when the DSL should own every value for that field, such as a
status normalizer or a small controlled vocabulary parser.

!!! warning "Fallback matches everything"
    A fallback makes the DSL handle every unmatched value. That is useful for
    owned fields, but too broad for fields that should accept literal text
    unchanged.

## Registration Is Checked

The same pattern expression and same field scope cannot be registered twice.

```python title="Duplicate pattern registration"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:duplicate-pattern"
```

```text title="Duplicate pattern error"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:duplicate-pattern-output"
```

A DSL can also have only one fallback.

```python title="Duplicate fallback registration"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:duplicate-fallback"
```

```text title="Duplicate fallback error"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:duplicate-fallback-output"
```

Registration errors happen when the DSL is defined. Invalid regular expression
syntax is also rejected immediately by Python's regex compiler.

!!! tip "Fail ambiguous vocabulary early"
    A DSL is project language. Duplicate rules make that language harder to
    explain, so Talika rejects duplicate pattern and fallback declarations
    before any table is parsed.

## Handler Errors Keep Cell Location

If a pattern handler raises, Talika reports a field parser failure at the cell
that matched the pattern.

```python title="A pattern handler that fails"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-error"
```

```python title="Parsing the failing pattern"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-error-call"
```

```text title="Pattern diagnostic"
--8<-- "docs_src/guides/advanced/cell-dsl-patterns.py:pattern-error-output"
```

The diagnostic includes the schema, field, source row and column, item ID, and
authored value. The handler can stay focused on project conversion while
Talika preserves the table context around the failure.

!!! note "Pattern failures are parser failures"
    A matched pattern is part of field parsing. If the handler cannot build a
    value, the failure is reported through the same source-aware parser
    diagnostic path as other field parser errors.

## Choose the Rule Type

Use exact tokens when the whole cell is a fixed word or phrase.

Use patterns when the cell has a predictable text shape with captures.

Use predicates when the rule is easier to express as Python logic than as a
regular expression.

Use fallback when the DSL should own every unmatched value for that field.

The goal is not to make feature tables clever. The goal is to make repeated
project setup vocabulary explicit, tested, and source-aware.

!!! tip "Keep authored syntax small"
    A CellDSL works best when it explains a few project-owned phrases. If a
    cell starts to look like a programming language, move complexity back into
    Python helpers or table transformations.
