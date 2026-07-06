---
icon: lucide/columns-3
---

# Column Tables

Use `ColumnTable` when the first column contains labels and each later column
describes one record.

This shape is useful when each item has several fields, when a record reads
more naturally as a vertical card, or when row tables become too wide to scan.
CMS content examples often fit this shape: an article, poll, or page section
may have many properties, and each item is easier to read from top to bottom.

```gherkin title="A column-oriented feature table"
--8<-- "docs_src/guides/basic/column-tables.py:feature-basic"
```

In this table, `A-1` and `P-1` are the records. `Type`, `Headline`, and
`Status` are fields on each record.

!!! tip "When to choose a column table"
    Choose a column table when each item has enough fields that a row table
    would become wide or full of blanks. The first column becomes the list of
    labels, and each item gets its own vertical column.

## Define the Column Contract

A column table must declare exactly one `id_field(...)`. That field identifies
each item column and must be the first row in the table.

```python title="content_table.py"
--8<-- "docs_src/guides/basic/column-tables.py:contract-basic"
```

The contract says:

- `id` maps the ID row `IDs` to the Python attribute `id`. Every item column must have a unique ID in that row.
- `content_type` maps the required table row `Type` to the attribute `content_type`.
- `headline` maps the required table row `Headline` to the attribute `headline`.
- `status` maps the optional table row `Status` to the attribute `status`, which returns `None` when the whole row is absent.

!!! note "ColumnTable requires an ID row"
    A row table may choose whether to declare an ID field. A column table must
    declare one, because the parser needs a stable identity for each item
    column.

## Parse Item Columns

The datatable shape mirrors the feature table. The first cell of each row is a
label. Each later cell belongs to the item column above it.

```python title="The datatable shape"
--8<-- "docs_src/guides/basic/column-tables.py:datatable-basic"
```

Call `parse()` with the datatable:

```python title="Parse the content records"
--8<-- "docs_src/guides/basic/column-tables.py:parse-basic"
```

The parsed result is ordered by item column. The first output record belongs to
`A-1`, and the second belongs to `P-1`.

```bash { .talika-terminal title="Parsed column record" .speed-3}
--8<-- "docs_src/guides/basic/column-tables.py:record-output"
```

The item ID is both a normal parsed field (`item.id`) and source metadata
(`item.table_source.item_id`). The normal field is useful in test setup. The
source metadata is useful when validation or diagnostics need to identify the
authored item.

## Item Lookup and Column Metadata

Column tables still return a sequence of parsed records, so index-based access
works. The difference is what the index means. In a row table, record position
usually points to a source row. In a column table, record position points to an
item column.

Most tests become clearer if they do not rely on positional access for long.
Parse the table, then build a small lookup by item ID for assertions and setup
code.

- `table_source.column` stores the one-based source column for the parsed item.
- `table_source.row` is not populated for the record itself because the item
  runs vertically through several rows.
- `source_for("field_name")` still points to the exact row and column for one
  field value.

```python title="Item ID lookup and column coordinates"
--8<-- "docs_src/guides/basic/column-tables.py:column-metadata"
```

!!! tip "Use IDs after parsing"
    Column tables are often authored by ID. Building `by_id = {item.id: item}`
    makes later assertions read like the feature file instead of like a column
    index calculation.

## Missing Optional Rows

When an optional field row is absent, Talika gives that field `None` unless the
field declares a default.

```python title="The Status row is absent"
--8<-- "docs_src/guides/basic/column-tables.py:missing-optional"
```

This is different from an explicit empty cell. In the next table, the `Status`
row exists, and `A-1` intentionally has a blank status cell:

```python title="The Status cell is empty"
--8<-- "docs_src/guides/basic/column-tables.py:empty-optional"
```

!!! warning "Absent row and empty cell are different"
    An absent optional row means the field was not provided for any item. An
    empty cell means the field was provided, but one item has a blank value.
    Those two cases are often handled differently in real feature files.

## Missing and Empty Required Values

A required field row must be present, and every item column must have a
non-empty value for that field.

If the table omits a required row, the error includes the item ID because the
missing value affects a specific item column:

```python title="Missing required row"
--8<-- "docs_src/guides/basic/column-tables.py:missing-required"
```

```text title="Missing required row error"
--8<-- "docs_src/guides/basic/column-tables.py:missing-required-output"
```

If the row exists but an item leaves the required cell empty, the error points
to the exact row and column:

```python title="Empty required cell"
--8<-- "docs_src/guides/basic/column-tables.py:empty-required"
```

```text title="Empty required cell error"
--8<-- "docs_src/guides/basic/column-tables.py:empty-required-output"
```

This is one of the main benefits of preserving table source information. The
author can go directly to the blank cell instead of searching through parsing
code.

## The First Row Must Be the ID Row

For column tables, the first row controls item identity. The first cell of that
row must match the declared `id_field(...)` label or one of its aliases.

```python title="Wrong first row"
--8<-- "docs_src/guides/basic/column-tables.py:wrong-first-row"
```

```text title="Wrong first row error"
--8<-- "docs_src/guides/basic/column-tables.py:wrong-first-row-output"
```

Talika rejects this table before parsing records because it cannot safely know
which values are item IDs.

!!! note "The ID row is structural"
    The ID row is not just another optional field. It defines the item columns.
    Move it carefully when editing column-oriented feature files.

## Duplicate Item IDs

Every item column needs a unique ID. Duplicate IDs make references, defaults,
diagnostics, and later validation ambiguous.

```python title="Duplicate item ID"
--8<-- "docs_src/guides/basic/column-tables.py:duplicate-id"
```

```text title="Duplicate item ID error"
--8<-- "docs_src/guides/basic/column-tables.py:duplicate-id-output"
```

The diagnostic points to the second occurrence. That is the cell the author
needs to change.

## Rectangular Tables

Every row in a column table must have the same number of cells as the ID row.
If the ID row defines two item columns, every other row must also provide two
item cells.

```python title="A ragged column table"
--8<-- "docs_src/guides/basic/column-tables.py:ragged-row"
```

```text title="Ragged row error"
--8<-- "docs_src/guides/basic/column-tables.py:ragged-row-output"
```

Talika reports this as a table-shape error. Until the row is rectangular, the
parser cannot reliably know which item a missing cell belongs to.

!!! tip "Keep column tables readable"
    Column tables are best when each item is worth reading vertically. If the
    table only has two or three simple fields, a row table may be shorter and
    easier to compare.
