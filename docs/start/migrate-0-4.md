---
icon: lucide/replace
tags:
  - Migration
  - Talika 0.4
  - Parsing
  - Fields
---

# Migrating From 0.3

Talika 0.4 makes two boundaries explicit: a typed field must describe every
value Talika can create, and output conversion happens through `parse_as()`.
Most schemas need only small, local edits.

## Make Typed Fields Consistent

Before, a typed field could be optional even when its annotation rejected
`None` or raw blank text:

```python title="Before"
--8<-- "docs_src/start/migrate-0-4.py:typed-before"
```

If the field is required, say so:

```python title="After: required"
--8<-- "docs_src/start/migrate-0-4.py:typed-after-required"
```

If it is optional, allow `None` and choose the blank policy:

```python title="After: optional"
--8<-- "docs_src/start/migrate-0-4.py:typed-after-optional"
```

Unsupported annotations such as `list[str]` now require an explicit parser.
Static defaults must match resolvable annotations. Explicit custom parsers and
default factories remain trusted.

## Split Parsing From Output Conversion

In 0.3, `parse()` could return either records or configured output models, and
`parse_records()` forced the record form:

```python title="Before"
--8<-- "docs_src/start/migrate-0-4.py:output-before"
```

In 0.4, `parse()` always returns schema records. `parse_as()` performs output
conversion:

```python title="After"
--8<-- "docs_src/start/migrate-0-4.py:output-after"
```

`parse_records()`, `parse_table_records()`, and the pytest fixture's
`parse_records()` method were removed. Their direct replacement is `parse()`.

You may also pass a dataclass, Pydantic model, or other callable for one call:

```python title="Explicit output target"
--8<-- "docs_src/start/migrate-0-4.py:explicit-output"
```

An explicit target overrides configured schema and variant output hooks.

## Required Fields Own Blank Input

In 0.3, an empty-aware parser could make a required blank succeed:

```python title="Before"
--8<-- "docs_src/start/migrate-0-4.py:blank-before"
```

In 0.4, required blanks always raise `empty_required`. Optional fields send a
blank to their parser only with `empty="parse"`:

```python title="After"
--8<-- "docs_src/start/migrate-0-4.py:blank-after"
```

## Check The Result

Run the test suite after updating schema definitions. Schema-definition errors
name the conflicting field path and suggest a concrete correction. Then update
type-checking samples so `parse()` is `list[SchemaType]` and explicit
`parse_as(..., OutputType)` is `list[OutputType]`.
