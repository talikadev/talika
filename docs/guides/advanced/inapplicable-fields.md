---
icon: lucide/ban
tags:
  - Variants
  - Fields
  - Validation
  - Table schemas
---

# Inapplicable Fields

Variant tables often contain the union of every possible field in the table
family. That shape is useful for authors because they can compare records in
one place, but it also creates a question: what should happen when a record
contains a value for a field that belongs to another variant?

```gherkin title="A poll with a value in an article-only field"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:feature-content"
```

In this table, `Body` belongs to `Article`. The selected record is a `Poll`.
The `Options` value is correct, but `Body` contains `copied note`. Talika calls
that an inapplicable field: the label is known to the table family, but it does
not apply to the selected variant.

!!! tip "Known label, wrong selected shape"
    An unknown field is a label the schema family does not know. An
    inapplicable field is a known label with a non-empty value on a record
    whose selected variant does not declare that field.

## Start With a Variant Table

The examples below use a small CMS table with two variants.

```python title="Shared variant fields"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:base-fields"
```

`ArticleFields` owns `Body`. `PollFields` owns `Options`. The base table owns
the shared fields.

```python title="Strict content table"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:strict-schema"
```

The default policy is `inapplicable_fields = "forbid"`. You normally do not
write that line because it is already the schema default.

!!! note "This policy only matters for variants"
    A non-variant table does not have selected and non-selected shapes. The
    inapplicable-field policy is only used when a discriminator has selected a
    concrete variant for a record.

## The Default Is Forbid

The strict default protects the table author from quiet mistakes.

```python title="A poll with a non-empty Body cell"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:bad-table"
```

```python title="Parsing with the default policy"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:forbid-call"
```

```text title="Inapplicable-field diagnostic"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:forbid-output"
```

This failure is intentional. `Body` is a valid label somewhere in the table
family, so Talika does not treat it as unknown. But after `Type` selects
`Poll`, a non-empty `Body` cell looks like misplaced data.

The diagnostic points to the exact cell that should be cleared, moved, or
explained by changing policy.

!!! warning "Forbid is the safest default"
    In most test data, a non-empty value in the wrong variant field is a bug.
    Leaving it in the table can make the scenario look like it is testing one
    thing while the parser silently ignores another.

## Empty Cells Are Allowed

A variant table can still include rows or columns for other variants. Empty
cells are ignored.

```python title="A clean poll row"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:empty-table"
```

```bash { .talika-terminal title="Empty inapplicable cells are ignored" .speed-3}
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:empty-output"
```

This is the normal union-table pattern. The table can show both `Body` and
`Options` labels, while each record only fills the fields that match its
variant.

!!! tip "Use blank cells to keep the table rectangular"
    Authors can leave fields blank where they do not apply. The strict policy
    only rejects non-empty inapplicable values.

## Preserve Inapplicable Values

Use `inapplicable_fields = "preserve"` when old or imported tables may contain
values that do not apply to the selected variant, but you still want to inspect
them.

```python title="Preserving inapplicable values"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:preserve-schema"
```

With this policy, Talika does not attach the value to the selected variant as a
normal field. The record still remains a `Poll` record. The inapplicable value
is stored separately in `table_extras`.

```python title="Parsing with preserve"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:preserve-call"
```

```bash { .talika-terminal title="Preserved table extras" .speed-3}
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:preserve-output"
```

This gives migration or linting code a way to see the value without pretending
that `Body` is part of the poll schema.

!!! note "Preserve does not make the field applicable"
    The selected record still only has fields declared by its variant and base
    schema. Preserved values are extra source data, not parsed domain fields.

## Extras Stay Out of `as_dict`

`table_extras` is intentionally separate from parsed schema fields.

```bash { .talika-terminal title="Extras are not schema fields" .speed-3}
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:as-dict"
```

That matters for output models. The default output-model conversion uses
`record.as_dict()`, so preserved inapplicable values do not get passed into a
dataclass, Pydantic model, or ordinary constructor by accident.

If output conversion needs extras, use a custom `build_output()` that
deliberately reads `record.table_extras`.

!!! warning "Do not depend on extras as required data"
    Extras are preserved because the value did not fit the selected variant.
    Treat them as migration, diagnostics, or audit data, not as part of the
    normal record contract.

## Extras Are Read-Only

`table_extras` is a read-only mapping on the parsed record.

```python title="Trying to mutate extras"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:readonly-extras"
```

```text title="Read-only extras error"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:readonly-extras-output"
```

The record represents the parsed result of one authored table. If migration
code needs to rewrite old values, rewrite the source table or build a new
output object rather than mutating the parsed record in place.

!!! tip "Keep parsed records stable"
    Treat schema records as immutable parse results for practical purposes.
    They expose source data and extras for inspection, not as a place to repair
    the table after parsing. Declared record attributes are technically
    assignable in Talika 0.3; source metadata and extras are enforced as
    read-only.

## Empty Inapplicable Cells Are Not Extras

Preserve mode only records non-empty values. Empty cells for other variants are
ignored, just as they are in strict mode.

```bash { .talika-terminal title="Blank wrong-variant cells" .speed-3}
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:empty-extras-output"
```

This keeps `table_extras` focused. It reports authored values that may need
attention, not every blank cell required to keep a union-shaped table
rectangular.

!!! note "Extras mean something was written"
    If a label appears in the table but the selected variant leaves the cell
    blank, Talika treats that as intentional table shape. It is not preserved
    as an extra.

## Extras Use Authored Labels

Preserved extras are keyed by the actual label used in the table, not by the
Python field name.

```python title="A variant field with an alias"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:alias-schema"
```

```bash { .talika-terminal title="Authored label in extras" .speed-3}
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:alias-output"
```

The schema field name is `body`, and the canonical label is `Body`, but the
table author used the alias `Article body`. That exact label appears in
`table_extras`.

This is useful for migration tooling because it preserves the vocabulary that
actually appeared in the authored table.

!!! tip "Use extras for reporting"
    When showing preserved values back to an author, the authored label is
    usually more helpful than the Python attribute name.

## Unsupported Policies Fail Early

Only two policies are supported:

- `"forbid"`
- `"preserve"`

`"ignore"` is not supported. A schema that asks for it fails during class
creation.

```python title="Unsupported inapplicable-field policy"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:invalid-policy"
```

```text title="Schema definition error"
--8<-- "docs_src/guides/advanced/inapplicable-fields.py:invalid-policy-output"
```

Silent ignore is deliberately absent. If a value is written into a field that
does not apply to the selected variant, the parser should either reject it or
preserve it for explicit inspection.

!!! warning "Avoid silent data loss"
    `"preserve"` is a conscious migration choice. `"forbid"` is the safer
    default for tests. A silent ignore policy would make authored values
    disappear without either behavior.

## Choose the Policy

Use the default `"forbid"` when feature tables are expected to be clean and the
team wants mistakes to fail immediately.

Use `"preserve"` when the table is transitional:

- old feature files still contain values from an earlier schema
- imported data needs to be audited before cleanup
- a tooling pass should report extra values without blocking parsing
- migration code needs to compare selected fields and preserved source values

In most test suites, keep strict mode for normal scenario setup. Reach for
preserve mode when the documentation, migration, or tooling story explicitly
needs to keep those extra authored values visible.

!!! tip "Preserve temporarily, then remove"
    If preserve mode is only helping a schema migration, treat it as temporary.
    Once old tables are cleaned up, returning to strict mode gives better
    protection against misplaced data.
