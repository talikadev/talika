---
icon: lucide/wand-sparkles
---

# Transform Tables

Some teams write feature tables exactly in the shape their Python code wants.
Other teams write tables in a shape that is easier for people to read, review,
or maintain.

Table transformations are for the second case. They let a schema normalize the
authored table before labels are matched, fields are parsed, and records are
validated.

```gherkin title="An authored table with friendly values"
--8<-- "docs_src/guides/advanced/transform-tables.py:feature"
```

In this table, the author has not done anything wrong. The ID is lowercase
because that is easy to type. The headline is sentence-like text. The status is
written as a human phrase. Your test code may still want `A-1`, `Market Brief`,
and `ready-for-review`.

!!! tip "Transform authored shape into logical shape"
    A table transformation should answer: "What table should the schema see?"
    It should not try to replace field parsers, record validators, or table
    validators.

## Use `transform_table` for Schema-Specific Changes

Override `transform_table(...)` when the transformation belongs to one schema.
The hook receives a `TableData` object and the current parse context.

```python title="Normalizing values before the schema parses them"
--8<-- "docs_src/guides/advanced/transform-tables.py:direct-hook"
```

The transformed values are what the fields parse:

```bash { .talika-terminal title="Parsed normalized content" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:direct-output"
```

The important detail is the return value. `transform_table(...)` must return
`TableData`, not plain rows. When you already have source-aware cells, build the
new table with `TableData.from_cells(...)`.

!!! warning "Do not rebuild transformed tables from plain strings"
    `table.to_rows()` is useful for debugging, but it drops source metadata.
    Inside a transformer, arrange existing cells and use `cell.with_value(...)`
    when the logical value changes.

## Preserve the Authored Cell

`with_value(...)` changes the current value while keeping the original row,
column, and source text.

```bash { .talika-terminal title="Transformed value with original source" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:source-preserved-output"
```

That distinction matters later. A parser receives `ready-for-review`, but an
error can still point to row 3, column 2, where the author wrote
`Ready For Review`.

!!! note "Current value and source value can differ"
    The current value is the value Talika should parse. The source value is the
    value the feature author wrote. Transformations often need both.

## Compose Reusable Transformers

Use reusable transformer objects when the same normalization should be shared
by several schemas. A transformer object only needs a `transform(...)` method:

```python title="Reusable transformers in a left-to-right pipeline"
--8<-- "docs_src/guides/advanced/transform-tables.py:pipeline"
```

This shape is the public `TableTransformer` protocol. You do not need to inherit
from a base class. Any object with a compatible `transform(table, context, *,
schema=None)` method can be used as a schema's `table_transformer`.

`compose_transformers(...)` runs each transformer from left to right. Each stage
receives the table returned by the previous stage.

```bash { .talika-terminal title="Pipeline result" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:pipeline-output"
```

The example also uses `context.user_data`. This is helpful when a test run wants
to pass a small amount of environment-specific information into parsing, such
as a prefix, locale, tenant, or mode.

`compose_transformers(...)` returns a `TransformerPipeline`. You normally do
not need to instantiate `TransformerPipeline` directly unless a project wants
to build the sequence dynamically.

!!! tip "Keep stages small"
    A readable transformer usually does one kind of work: normalize labels,
    expand compact authoring syntax, prefix IDs, or clean a family of values.
    Pipelines are easier to review when each stage has a clear job.

## Return `TableData`

Talika checks transformer results before continuing. If a hook returns plain
rows, parsing stops with a table error:

```python title="Returning plain rows by mistake"
--8<-- "docs_src/guides/advanced/transform-tables.py:invalid-return"
```

```bash { .talika-terminal title="Invalid transformer return" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:invalid-return-output"
```

Pipeline stages are checked in the same way. If a reusable stage returns the
wrong kind of value, the error identifies the stage number and class name:

```bash { .talika-terminal title="Invalid pipeline stage" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:pipeline-invalid-output"
```

## Raise Intentional Table Errors

If a transformer detects invalid authoring syntax, raise a `TableError` from
the specific cell. Talika preserves intentional table errors instead of wrapping
them as unexpected failures.

```python title="Pointing a transformer error at the authored cell"
--8<-- "docs_src/guides/advanced/transform-tables.py:intentional-error"
```

```bash { .talika-terminal title="Source-aware transformer error" .speed-3}
--8<-- "docs_src/guides/advanced/transform-tables.py:intentional-error-output"
```

The error belongs to row 2, column 1, because that is where the problematic
authoring text came from.

!!! warning "Do not hide authoring mistakes during transformation"
    If a compact table syntax is invalid, fail early and point to the exact
    cell. Silent cleanup makes feature files harder to trust because authors do
    not learn which table text was ambiguous or unsupported.

## Choose Transformations Deliberately

Use a table transformation when the authored table should become a different
logical table before parsing. Good examples include:

- normalizing labels or IDs before field lookup
- expanding compact table syntax into ordinary rows or columns
- rewriting project-owned vocabulary into parser-friendly values
- applying test-run context before field parsing begins

Avoid transformations for ordinary type conversion. A field parser is usually
better for turning `"34"` into an integer, `"yes"` into a boolean, or a status
label into a domain enum. Avoid transformations for business rules too. Record
validators and table validators give clearer intent for rules such as duplicate
emails, invalid ranges, or missing references.

!!! example "A useful boundary"
    If the question is "What table should my schema see?", use a table
    transformation. If the question is "What does this cell mean?", use a
    parser. If the question is "Is this record or table valid?", use validation.
