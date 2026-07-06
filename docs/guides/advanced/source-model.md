---
icon: lucide/map-pin
---

# Source Model

Talika keeps two versions of a table value in mind:

- the current value being parsed
- the original source cell the author wrote

That distinction is the reason diagnostics can point back to a precise table
cell even after parsing, defaults, references, validators, output conversion,
or table transformations have run.

```gherkin title="A table whose parsed record keeps source metadata"
--8<-- "docs_src/guides/advanced/source-model.py:feature-source"
```

The source model is not something most users need for basic parsing. It becomes
important when you write custom validators, table transformers, static checks,
editor integrations, or diagnostics that should point to authored table cells.

!!! tip "Separate value from provenance"
    A parsed value answers "what should the test use?" Source metadata answers
    "where did this value come from in the authored table?"

## Raw Rows Become TableData

Pytest-bdd style datatables usually arrive as ordinary nested strings. Talika
upgrades those rows into `TableData` before parsing.

```python title="Wrapping raw rows"
--8<-- "docs_src/guides/advanced/source-model.py:tabledata-basic"
```

`TableData` contains `TableCell` objects. Each cell has:

- `value`, the current logical value
- `source_row`, the original one-based row number
- `source_column`, the original one-based column number
- `source_value`, the original authored value

```bash { .talika-terminal title="Source-aware table cells" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:tabledata-output"
```

Coordinates are one-based because they are meant for people reading feature
tables and diagnostics. `table.cell(2, 2)` means row 2, column 2 in the
authored table.

!!! warning "Use one-based coordinates with cell()"
    `TableData.cell(...)` is deliberately one-based. Use `table.rows` directly
    when writing normal zero-based Python iteration.

## Change Values Without Losing Source

When transformation code changes a logical value, use `cell.with_value(...)`.

```python title="Changing a current value"
--8<-- "docs_src/guides/advanced/source-model.py:with-value"
```

```bash { .talika-terminal title="Current value vs source value" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:with-value-output"
```

The new cell has `value='ADMIN'`, but `source_value='admin'`. That means later
parsing sees the changed value, while later diagnostics can still quote the
authored table cell.

`TableData.from_cells(...)` is used when code already has source-aware cells
and wants to arrange them into a new logical table.

!!! note "to_rows only returns current values"
    `to_rows()` is useful for display and debugging, but it drops source
    metadata. Do not use it inside transformers that need to preserve
    diagnostics.

## Row Records Keep Row Source

Parsed schema records expose source metadata through `table_source` and
`source_for(...)`.

```python title="A row table schema"
--8<-- "docs_src/guides/advanced/source-model.py:row-schema"
```

Use `parse_records(...)` when you specifically need schema records and source
metadata.

```python title="Reading row record source"
--8<-- "docs_src/guides/advanced/source-model.py:row-source"
```

```bash { .talika-terminal title="Row record source metadata" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:row-source-output"
```

For a row-oriented record, `table_source.row` points to the data row. There is
no record column, so `table_source.column` is `None`. Field cells still know
their own row and column.

!!! tip "Use source_for for field-level diagnostics"
    `table_source` tells you where the record lives. `source_for("field_name")`
    tells you which authored cell supplied one field.

## Column Records Keep Item Source

Column-shaped records use the item column as the record location.

```python title="A column table schema"
--8<-- "docs_src/guides/advanced/source-model.py:column-schema"
```

```python title="Reading column record source"
--8<-- "docs_src/guides/advanced/source-model.py:column-source"
```

```bash { .talika-terminal title="Column record source metadata" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:column-source-output"
```

For a column-oriented record, `table_source.item_id` is the parsed ID and
`table_source.column` points to the item column. Field sources still point to
the row and column where that field value was authored.

This is useful in CMS-style tables because a diagnostic can say both which
item failed and which field cell caused the failure.

!!! note "Record location depends on table shape"
    Row tables usually identify records by row. Column tables usually identify
    records by item ID and item column.

## Defaults May Not Have Source Cells

A value can exist on a record without coming from an authored cell. Defaults
are the common case.

```python title="Trying to locate a defaulted field"
--8<-- "docs_src/guides/advanced/source-model.py:missing-source"
```

```text title="Missing source-cell error"
--8<-- "docs_src/guides/advanced/source-model.py:missing-source-output"
```

The `status` field exists on the parsed record because the schema supplied a
default. There is no `Status` cell in the table, so `source_for("status")`
raises `KeyError`.

!!! warning "Only locate authored values"
    Call `source_for(...)` when a value came from the table. For missing fields
    filled by defaults, raise record-level diagnostics or point to another
    authored cell that caused the problem.

## Source Metadata Is Read-Only

Record source metadata is copied and exposed through read-only mappings.

```python title="Trying to mutate record source cells"
--8<-- "docs_src/guides/advanced/source-model.py:readonly-source"
```

```text title="Read-only source mapping"
--8<-- "docs_src/guides/advanced/source-model.py:readonly-source-output"
```

This protects diagnostics from accidental mutation after parsing. A validator,
factory, or helper can read provenance, but should not rewrite where a record
came from.

!!! note "Build new values instead of mutating source"
    If a transformer needs to change the logical table, it should build a new
    `TableData` from source-aware cells. Parsed record source metadata is for
    inspection.

## Transformations Preserve Original Cells

Source metadata is especially important when a transformer rewrites values
before field parsing.

```python title="A transformation that uppercases one value"
--8<-- "docs_src/guides/advanced/source-model.py:transform-schema"
```

```bash { .talika-terminal title="Transformed record source" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:transform-output"
```

The parsed value is `ADMIN`, but the source value is still `admin`. The
transformer changed what later parsing saw, not where the value came from.

This matters when a later parser or validator fails. The diagnostic should
point to the table text the author can edit, not to an internal value created
by the transformer.

!!! tip "Use with_value inside transformations"
    If a transformed value derives from an existing table cell, use
    `source_cell.with_value(...)`. That preserves row, column, and authored
    value.

## Build Errors from Source Cells

Custom validators and transformers can build precise diagnostics from a
`TableCell`.

```python title="Creating a source-aware error"
--8<-- "docs_src/guides/advanced/source-model.py:error-from-cell"
```

```bash { .talika-terminal title="Error created from a source cell" .speed-3}
--8<-- "docs_src/guides/advanced/source-model.py:error-from-cell-output"
```

`TableError.from_cell(...)` copies the source row, source column, and source
value into the diagnostic. Use it when a custom rule can identify the exact
authored cell that caused the failure.

!!! warning "Point to the cell the author can fix"
    If the problem belongs to one table cell, build the error from that cell.
    If the problem belongs to a whole record or whole table, use a record-level
    or table-level diagnostic instead.

## Parser Errors Use Source Values

When a parser fails after transformation, Talika reports the original source
cell.

```python title="A parser failure after transformation"
--8<-- "docs_src/guides/advanced/source-model.py:parser-error-after-transform"
```

```python title="Parsing the transformed table"
--8<-- "docs_src/guides/advanced/source-model.py:parser-error-after-transform-call"
```

```text title="Diagnostic points to the authored value"
--8<-- "docs_src/guides/advanced/source-model.py:parser-error-after-transform-output"
```

The parser saw the transformed value internally, but the diagnostic reports
`value='admin'` because that is the authored cell text. This keeps the error
actionable for the person editing the table.

!!! note "Current value and source value serve different readers"
    Parsers need the current logical value. Diagnostics need the authored
    source value. The source model keeps both available.

## When to Use the Source Model

Most ordinary tests can ignore these objects and simply use `parse(...)`.

Reach for the source model when you are writing:

- custom validators with cell-specific errors
- table transformations
- static checkers or editor diagnostics
- source-aware assertions
- output builders that need record provenance
- tooling that reports row and column locations

Use `parse_records(...)` when you need source metadata after parsing. Use
`TableData` and `TableCell` directly when you are transforming or checking the
table before normal schema parsing.

!!! tip "Keep source handling close to diagnostics"
    Source metadata is most valuable at the point where you need to explain a
    problem. Keep ordinary domain logic focused on parsed values, and use
    source objects when you need to report where those values came from.
