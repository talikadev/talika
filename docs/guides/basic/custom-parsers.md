---
icon: lucide/wrench
tags:
  - Custom parsing
  - Parser API
  - Cell context
  - Error handling
---

# Custom Parsers

Use a custom parser when the built-in parser factories cannot fully describe
your table language.

The parser contract is simple: a parser is a callable that receives the current
cell value and a `CellContext`, then returns the Python value for that field.

```python title="The custom parser shape"
--8<-- "docs_src/guides/basic/custom-parsers.py:parser-signature"
```

The value is usually a string from the table, but it may already have been
changed by a table transformer. The context tells the parser which schema,
field, source cell, item ID, and parse-time project data are involved.

```gherkin title="A table that needs parser context"
--8<-- "docs_src/guides/basic/custom-parsers.py:feature-basic"
```

!!! tip "Write custom parsers for project vocabulary"
    A custom parser is best when the table uses language that belongs to your
    project: imported IDs, role aliases, external status codes, compact domain
    syntax, or validation that depends on parse-time configuration.

## Write the Parser Signature

A custom parser must accept two arguments:

- `value`: the current cell value being parsed.
- `context`: a `CellContext` for the active field.

```python title="A parser that uses context"
--8<-- "docs_src/guides/basic/custom-parsers.py:basic-contract"
```

This parser uses three pieces of information:

- `value` supplies the authored username cell.
- `context.item_id` supplies the parsed row ID from `id_field(...)`.
- `context.user_data["prefix"]` supplies project data passed to `parse(...)`.

```python title="Parsing with project context"
--8<-- "docs_src/guides/basic/custom-parsers.py:basic-parse"
```

```bash { .talika-terminal title="Custom parser result" .speed-3}
--8<-- "docs_src/guides/basic/custom-parsers.py:basic-output"
```

The parser returns the value stored on the record. Talika does not apply a
second conversion after the custom parser returns.

!!! warning "The signature must accept context"
    A parser that only accepts `value` will fail because Talika always calls
    parsers with both `value` and `context`.

## Read CellContext

`CellContext` is the parser's view of the parsing operation. It gives the
parser source-aware information without forcing the parser to know how row and
column tables are implemented.

| Attribute | Meaning |
| --- | --- |
| `schema` | The schema class currently parsing the field. |
| `field_name` | The Python attribute that will receive the parsed value. |
| `field_label` | The canonical table label declared by `field(...)`. |
| `row` | One-based source row, when available. |
| `column` | One-based source column, when available. |
| `item_id` | Parsed item ID, when the table has one. |
| `source_value` | The original authored cell text. |
| `user_data` | Read-only project data supplied to `parse(..., context=...)`. |

Use `field_name` when your parser cares about the Python schema attribute. Use
`field_label` when the error or normalization belongs to the authored table
label. Use `item_id` when parsing depends on the current record identity.

!!! note "Value and source_value are not always the same"
    `value` is the current value being parsed. `context.source_value` is the
    original authored cell text. They are usually the same in basic tables, but
    table transformation can change `value` while preserving the original
    source for diagnostics.

## Pass Project Data into Parsers

Do not hide project state in global variables when the value can change per
test run. Pass it to `parse(..., context={...})` and read it from
`context.user_data`.

```python title="A parser driven by project data"
--8<-- "docs_src/guides/basic/custom-parsers.py:role-contract"
```

This parser normalizes authored role names, applies aliases from the parse
context, and checks the result against a configured set of allowed roles.

```python title="Parsing role aliases"
--8<-- "docs_src/guides/basic/custom-parsers.py:role-parse"
```

```bash { .talika-terminal title="Role parser result" .speed-3}
--8<-- "docs_src/guides/basic/custom-parsers.py:role-output"
```

The table author can write `Administrator`, while the test receives the project
role value `admin`.

If the value is not accepted, raise a normal exception with a clear message:

```python title="Rejected project value"
--8<-- "docs_src/guides/basic/custom-parsers.py:role-error"
```

```text title="Custom parser failure"
--8<-- "docs_src/guides/basic/custom-parsers.py:role-error-output"
```

Talika wraps the exception with schema, field, row, column, and authored value.
That means the parser message can focus on the domain problem.

!!! tip "Keep parser messages domain-specific"
    A good parser error says what was wrong with the table value, not where the
    value came from. Talika adds the source location around it.

## Parse Compact Domain Syntax

Custom parsers are also useful when a table cell has compact syntax that is
specific to your test domain.

```python title="A percent parser"
--8<-- "docs_src/guides/basic/custom-parsers.py:percent-contract"
```

This parser accepts values such as `95%`, rejects values without the percent
sign, rejects percentages outside the range `0..100`, and returns a decimal
ratio that test code can compare directly.

```python title="Parsing a percent value"
--8<-- "docs_src/guides/basic/custom-parsers.py:percent-parse"
```

```bash { .talika-terminal title="Percent parser result" .speed-3}
--8<-- "docs_src/guides/basic/custom-parsers.py:percent-output"
```

When the value is outside the project rule, the parser raises `ValueError`:

```python title="A percent outside the allowed range"
--8<-- "docs_src/guides/basic/custom-parsers.py:percent-error"
```

```text title="Percent parser failure"
--8<-- "docs_src/guides/basic/custom-parsers.py:percent-error-output"
```

This style keeps the parser small and readable. It does not try to validate the
whole record. It only answers one field-level question: how should this cell be
converted?

!!! note "Keep record rules out of field parsers"
    A field parser should parse one cell. If a rule needs multiple fields from
    the same record, it belongs in record validation rather than in a field
    parser.

## Empty Cells and Custom Parsers

By default, an explicit empty optional cell is not sent to the parser. Talika
returns `""` for that field.

If your parser needs to handle empty text itself, set `empty="parse"` on the
field.

```python title="A parser that handles blank text"
--8<-- "docs_src/guides/basic/custom-parsers.py:empty-contract"
```

```python title="Parsing empty cells"
--8<-- "docs_src/guides/basic/custom-parsers.py:empty-parse"
```

```bash { .talika-terminal title="Empty-cell parser result" .speed-3}
--8<-- "docs_src/guides/basic/custom-parsers.py:empty-output"
```

The `normal` field keeps the empty string because the parser is skipped for
blank optional cells. The `parsed_empty` field sends the blank string to the
parser because the field explicitly opts into `empty="parse"`.

!!! warning "Do not assume your parser sees blanks"
    If an optional field has an empty cell and the field does not use
    `empty="parse"`, your custom parser will not run for that cell.

## Use Source Value Carefully

Most custom parsers should use `value`. That is the current value in the table
lifecycle. In ordinary tables, it is the text written in the feature file.

Use `context.source_value` when the original authored text matters for a
diagnostic or for project syntax that should survive transformation.

```python title="A parser that mentions the original cell"
--8<-- "docs_src/guides/basic/custom-parsers.py:source-value"
```

The parser above checks the transformed value, but its error message can still
mention the original cell text. This matters when a transformer expands or
normalizes compact authored syntax before field parsing.

!!! note "Prefer value for conversion"
    Treat `value` as the thing you are converting. Treat `source_value` as
    source context that helps explain where the value came from.

## Understand Parser Failures and Exception Wrapping

When a custom parser raises an ordinary exception during parsing, Talika wraps
it as `TableError(code="parser_failed")` and retains the original exception as
the diagnostic cause.

Because of this auto-wrapping behavior:

- **Raise Plain Exceptions** when Talika should classify the failure as
  `parser_failed` and populate its normal schema, field, location, and values.
- **Raise `TableError` deliberately** when the project owns a more specific
  code, hint, or location. Talika passes that exact exception through unchanged.
- **Raise `TableErrors` or `SchemaDefinitionError` deliberately** when the
  extension owns an aggregate or schema-level failure; these also pass through.

The same pass-through rule applies to default factories, transformers,
reference-key parsers, validators, and output builders.

```python title="A parser with the wrong signature"
--8<-- "docs_src/guides/basic/custom-parsers.py:bad-signature"
```

```text title="Bad parser signature diagnostic"
--8<-- "docs_src/guides/basic/custom-parsers.py:bad-signature-output"
```

!!! tip "Test custom parsers through a schema"
    A parser function can be unit-tested directly for small conversions, but
    also test it through `RowTable.parse(...)` or `ColumnTable.parse(...)`.
    That verifies the error message, source location, context data, and
    empty-cell behavior together.
