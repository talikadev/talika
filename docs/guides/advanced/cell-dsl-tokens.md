---
icon: lucide/braces
tags:
  - CellDSL
  - Tokens
  - Custom parsing
  - Cell context
---

# CellDSL Tokens

`CellDSL` lets a project give special meaning to authored cell text.

Talika does not ship built-in meanings for words like `random`, `today`,
`current user`, or `default`. Those words are project vocabulary. A `CellDSL`
lets you define that vocabulary once and attach it to the fields where it is
allowed.

```gherkin title="A table with a project token"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:feature-content"
```

In this table, `random` should generate a headline, but it should not generate
a status. The same visible cell text can mean something in one field and stay
literal in another field.

!!! tip "A token is exact project vocabulary"
    Use token rules for short, exact cell values such as `random`, `today`,
    `none`, `current user`, or `published`. If the value has parameters, a
    pattern rule is usually a better fit.

## Create a Token DSL

Start by creating one `CellDSL` instance and registering exact tokens on it.

```python title="A field-scoped random token"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:token-dsl"
```

The decorated function receives a `CellContext`. It can read parse-time project
data from `context.user_data`, source identity from `context.row` and
`context.column`, and record identity from `context.item_id` when the table has
an ID.

The token value is exact. This rule matches the cell text `random`. It does not
match `Random`, ` random `, `random headline`, or any other spelling.

!!! warning "Tokens do not normalize text"
    If your project wants case-insensitive or more flexible syntax, normalize
    the table before parsing or use a pattern/predicate rule in the later DSL
    topics. Exact tokens stay exact.

## Attach the DSL to Fields

A `CellDSL` is a field parser. Attach it with `field(..., parser=...)`.

```python title="A content table using token parsing"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:content-schema"
```

The same parser is attached to `headline` and `status`, but the token itself is
scoped to `headline`.

```python title="A table using the same word twice"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:content-table"
```

```python title="Parsing with project context"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:token-parse"
```

```bash { .talika-terminal title="Token parsing result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:token-output"
```

The headline token matched, so the handler generated a value. The status cell
also contains `random`, but the token is not scoped to `status`, so the value
passes through unchanged.

!!! note "A DSL may be shared by several fields"
    The DSL can be attached to multiple fields. Field scopes decide which rules
    apply to which schema attribute.

## Use Cell Context

Token handlers receive `CellContext`, not only the raw value. For exact tokens,
the value is already known because it is the token being handled.

```python title="Inspecting parser context"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:context-dsl"
```

```python title="A schema for context inspection"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:context-schema"
```

```bash { .talika-terminal title="Cell context seen by a token" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:context-output"
```

The context gives token handlers enough information to generate values that
belong to the current record and field. This is why a CMS headline token can
use the current item ID, or a date token can read a clock supplied through
parse context.

!!! tip "Pass dependencies through parse context"
    Put generators, clocks, fixtures, configuration, and policy values in
    `parse(..., context={...})`. Do not close over test-local mutable state
    when the context can make the dependency explicit.

## Scope Tokens by Python Field Name

The `fields=` argument uses schema attribute names, not table labels.

```python title="Field name used for token scope"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:scope-example"
```

The field scope is `"headline"`, not `"Headline"`.

This distinction matters because table labels are user-facing vocabulary. They
may contain spaces, punctuation, aliases, or old names. Field scopes belong to
Python schema code and use the stable attribute name.

!!! warning "Use field names, not labels"
    A field declared as `headline = field("Headline*")` is scoped as
    `"headline"`. Passing `"Headline*"` to `fields=` will not match that field.

## Scoped Tokens Beat Global Tokens

You can register a global token and a field-scoped token with the same exact
value.

```python title="Global and field-scoped tokens"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:global-and-scoped"
```

```python title="Fields using the same DSL"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:scoped-schema"
```

```bash { .talika-terminal title="Scoped token precedence" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:scoped-output"
```

For `headline`, the scoped token wins. For `category`, no scoped token applies,
so the global token handles the value.

This is useful when a broad project token has a sensible default meaning, but
one field needs a more specific meaning.

!!! note "Token precedence is narrow"
    This precedence rule is for exact tokens with the same value. Pattern,
    predicate, fallback, and composed DSL precedence are covered separately.

## Unmatched Values Pass Through

If no token matches, a `CellDSL` returns the original cell value.

```python title="A DSL with no matching tokens"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:passthrough"
```

```bash { .talika-terminal title="Literal value passthrough" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:passthrough-output"
```

This lets one parser accept both special project tokens and ordinary literal
values. A headline field can support `random` while still accepting a normal
authored headline.

!!! tip "Keep literals valid"
    A token DSL does not force every value to be a token. Use it when a field
    should accept a small set of special values plus ordinary table text.

## Registration Is Validated

An exact token cannot be empty.

```python title="Empty token registration"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:empty-token"
```

```text title="Empty token error"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:empty-token-output"
```

The same token and same scope cannot be registered twice.

```python title="Duplicate token registration"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:duplicate-token"
```

```text title="Duplicate token error"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:duplicate-token-output"
```

Duplicate detection is per scope. A global `random` token and a
`fields=("headline",)` `random` token can coexist because they do not describe
the same rule.

!!! note "Registration errors happen early"
    These errors happen when the DSL is defined, not when a feature table is
    parsed. That helps catch ambiguous project vocabulary during import.

## Token Handler Errors Keep Source Context

If a token handler raises an exception, Talika wraps it as a field parser
failure and keeps the source location of the cell that triggered the token.

```python title="A token handler that fails"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:handler-error"
```

```python title="Parsing the failing token"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:handler-error-call"
```

```text title="Source-aware token diagnostic"
--8<-- "docs_src/guides/advanced/cell-dsl-tokens.py:handler-error-output"
```

The failure points to `Headline` row 2, column 2, the authored cell containing
`broken`. That is the right place for the table author or test maintainer to
start looking.

!!! warning "Keep token handlers deterministic"
    A token handler is still a parser. It should return a value for the current
    cell or raise a clear exception. Avoid hidden side effects that make the
    same table parse differently across runs.

## Choose Tokens for Stable Vocabulary

Use exact tokens for values that should read like named project vocabulary:

- `random`
- `today`
- `current user`
- `none`
- `published`
- `default`

Avoid exact tokens for values that contain parameters, counts, IDs, or ranges.
Those belong in pattern, predicate, or transformation rules where the variable
part can be parsed deliberately.

The best token names are short, predictable, and documented by the schema that
uses them. A reader should be able to see `random` in a field and know that the
project has assigned that word a specific meaning for that field.

!!! tip "Prefer clear token names"
    A good token is small, predictable table language. It removes repeated
    setup code and keeps authored examples readable.
