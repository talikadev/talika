---
icon: lucide/rows-3
tags:
  - Row tables
  - Data tables
  - Schemas
  - Records
  - Parsing
---

# Row Tables

Use `RowTable` when the first row of the datatable contains labels and each
later row describes one record.

This is the most common shape for user lists, permissions, account states,
small product records, and other examples where the reader naturally scans one
record from left to right.

```gherkin title="A row-oriented feature table"
--8<-- "docs_src/guides/basic/row-tables.py:feature-basic"
```

In this table, the first row names the fields. Every later row is one user. The
schema you write should describe the labels, the required values, and the cell
parsers for that shape.

!!! tip "When to choose a row table"
    Choose a row table when each item has a small number of fields and the
    table is easiest to read horizontally. If each item has many fields or many
    optional values, a column-oriented table may be easier for authors to scan.

## Define the Row Contract

A row table contract is a normal Python class that inherits from `RowTable`.
Each `field(...)` declaration maps a table label to a Python attribute.

```python title="users_table.py"
--8<-- "docs_src/guides/basic/row-tables.py:contract-basic"
```

The class says:

- `username` must appear in the header row and each cell must be non-empty.
- `email` must also appear and be non-empty.
- `active` must appear, be non-empty, and parse through `boolean()`.

Talika does not infer Boolean meaning merely because a word looks familiar to
humans. The default `boolean()` parser gives `true` and `false` meaning. Other
vocabularies, such as `yes/no`, must be configured explicitly on that parser.

!!! note "Labels and attributes"
    The value passed to `field("...")` is the label in the authored table. The
    attribute name on the class is the name your Python code reads after
    parsing. Keeping those two names separate lets feature files use readable
    wording while test code keeps normal Python attributes.

## Parse Records from the Datatable

`pytest-bdd` passes the table to the step as nested strings. You can also write
that shape directly while learning or testing a schema:

```python title="The datatable shape"
--8<-- "docs_src/guides/basic/row-tables.py:datatable-basic"
```

Call `parse()` at the point where your test setup receives the table:

```python title="Parse the users"
--8<-- "docs_src/guides/basic/row-tables.py:parse-basic"
```

The parsed result is a list. Each item is a record with the declared fields as
attributes.

```bash { .talika-terminal title="Parsed row record" .speed-3}
--8<-- "docs_src/guides/basic/row-tables.py:record-output"
```

That record is intentionally small. It holds parsed values, supports
`as_dict()`, and carries source metadata for diagnostics and custom validation.

## The Parsed Record Collection and Object

When you call `parse()`, Talika returns a standard Python `list` containing parsed schema records. You can use standard Python collection methods on the result:

- Check the count: `len(users)`
- Retrieve by index: `users[0]`
- Iterate: `[u.username for u in users]`
- Slice: `users[1:]`

Each record object provides attributes matching your declared schema fields, plus helper methods and metadata properties:

- **`as_dict()`**: Returns a clean Python `dict` containing only your declared schema attributes and their parsed values. It intentionally excludes metadata and extras, making it perfect for unpacking (e.g. `User(**record.as_dict())`) into domain models.
- **`table_source`**: An immutable `RecordSource` object storing the record's source location (like the 1-based `row` index in the feature table).
- **`source_for(field_name)`**: Returns a `TableCell` object representing the source cell for a specific field. You can read its properties:
    - `value`: The current parsed/transformed string value.
    - `source_row`: The 1-based row number in the feature file.
    - `source_column`: The 1-based column number in the feature file.
    - `source_value`: The raw string value before any transformation.

```python title="Accessing record and cell metadata"
--8<-- "docs_src/guides/basic/row-tables.py:record-metadata"
```

```bash { .talika-terminal title="Source metadata lookup" .speed-3}
--8<-- "docs_src/guides/basic/row-tables.py:record-metadata-output"
```

## Required Fields

A required field has two rules:

1. The label must be present in the header row.
2. The cell for each record must not be empty.

If the table omits a required label, parsing fails before any row can be used:

```python title="Missing required label"
--8<-- "docs_src/guides/basic/row-tables.py:required-missing"
```

```text title="Missing required label error"
--8<-- "docs_src/guides/basic/row-tables.py:required-missing-output"
```

If the label is present but a row leaves the cell blank, the error points to
the specific authored cell:

```python title="Empty required cell"
--8<-- "docs_src/guides/basic/row-tables.py:required-empty"
```

```text title="Empty required cell error"
--8<-- "docs_src/guides/basic/row-tables.py:required-empty-output"
```

!!! warning "Missing and empty are different"
    A missing label is a table-shape problem. An empty cell is a value problem
    in one record. Talika reports them differently because the author fixes
    them in different places.

## Optional Fields and Defaults

Not every field needs to be written in every feature table. Optional fields can
use a static `default` or a `default_factory`.

```python title="Defaults for optional row fields"
--8<-- "docs_src/guides/basic/row-tables.py:defaults-contract"
```

When the entire field is absent from the header row, Talika supplies the
default:

```python title="Parsing a shorter table"
--8<-- "docs_src/guides/basic/row-tables.py:defaults-parse"
```

`default_factory` receives a context object. Use it when the missing value
depends on project data passed to `parse(..., context={...})`, or on an item ID
declared for the row.

An explicit empty cell is not the same as an absent field:

```python title="An empty cell is still present"
--8<-- "docs_src/guides/basic/row-tables.py:empty-is-present"
```

The field exists in the table, so the static default is not used. This is
important when feature authors intentionally write an empty value, or when a
blank cell should fail under a stricter empty-cell policy.

!!! note "Default factories are for missing fields"
    A default factory is a way to fill omitted optional data. It is not a
    general fallback for bad or blank cells. If an empty cell has meaning, make
    that policy explicit on the field.

## Row IDs

A row-oriented schema may declare an `id_field(...)`. This is optional, but it
is useful when parsers, default factories, diagnostics, or later validation
need a stable item identifier.

Row schemas allow zero or one `id_field`. Multiple ID declarations fail while
the schema class is created. Parsed IDs must be hashable and unique across the
table; typed duplicates such as `1` and `01` are duplicates when the ID parser
converts both to integer `1`.

Use `TableFields` for an incomplete reusable group of declarations. Do not
create an incomplete row or column schema solely to add an ID in a later
subclass.

```python title="A row table with item IDs"
--8<-- "docs_src/guides/basic/row-tables.py:id-contract"
```

The ID field is parsed before the other row fields, so its value is available
through parser and default-factory context.

```python title="Using the row ID in context"
--8<-- "docs_src/guides/basic/row-tables.py:id-parse"
```

In this example, `parse_display_name()` sees `context.item_id`, and
`default_audit_name()` uses the same ID to create a missing audit value.

Use `parse_records()` when you specifically want the Talika record object and
its `table_source` metadata. If the schema later configures an output model,
`parse()` may return that model instead.

## Row IDs in Diagnostics

When a row has an ID field, errors can include `item_id`. That makes failures
easier to locate in larger tables, especially when rows are sorted or filtered
by a test helper.

```python title="A parser failure on an identified row"
--8<-- "docs_src/guides/basic/row-tables.py:id-error"
```

```text title="Diagnostic with item_id"
--8<-- "docs_src/guides/basic/row-tables.py:id-error-output"
```

The row and column still point to the authored cell. The item ID adds a stable
record identity that can appear in logs, CI output, or editor diagnostics.

## Rectangular Tables

Every data row must have the same number of cells as the header row. This is
easy to miss when editing feature files by hand.

```python title="A ragged row"
--8<-- "docs_src/guides/basic/row-tables.py:ragged-row"
```

```text title="Ragged row error"
--8<-- "docs_src/guides/basic/row-tables.py:ragged-row-output"
```

Talika reports ragged rows as table-shape errors because the parser cannot know
which missing cell belongs to which label.

!!! tip "Keep row tables small"
    Row tables work best when each record has a compact set of fields. If the
    table becomes wide, hard to scan, or full of blank cells, the problem may
    be table shape rather than parsing.
