---
icon: lucide/git-branch
tags:
  - Variants
  - Schemas
  - Conditional fields
  - Data tables
---

# Variants

Use variants when one table contains records from the same family, but not
every record has the same fields.

CMS content is a common example. Every item may have an ID, type, and headline.
An article needs a body. A poll needs options. A video needs a URL. These
records belong together in one authored setup table, but each content type has
its own required fields and parsed shape.

```gherkin title="A table with article and poll records"
--8<-- "docs_src/guides/advanced/variants.py:feature-content"
```

Without variants, the schema has an awkward choice: make every possible field
optional, or split one readable table into several separate tables. Variants
let the table stay together while each record is parsed by the schema that
matches its discriminator value.

!!! tip "Think one table family"
    A variant table has shared fields on the base schema and specific fields on
    each selected variant. The discriminator cell chooses which specific schema
    applies to each record.

## Use `TableFields` for Concise Variants

The concise style uses `TableFields` components and a `discriminator(...)`
field with a variant mapping.

```python title="Declarative content variants"
--8<-- "docs_src/guides/advanced/variants.py:declarative-schema"
```

The base table declares fields that every content item has:

- `id`
- `content_type`
- `headline`

The variant components declare fields that only apply to one selected content
type:

- `ArticleFields` declares `body`
- `PollFields` declares `options`

```python title="A mixed content table"
--8<-- "docs_src/guides/advanced/variants.py:content-table"
```

When Talika parses a record, it reads the `Type` cell, selects the matching
variant schema, and then parses only the fields that apply to that schema.

```python title="Parsing declarative variants"
--8<-- "docs_src/guides/advanced/variants.py:declarative-parse"
```

```bash { .talika-terminal title="Selected variant values" .speed-3}
--8<-- "docs_src/guides/advanced/variants.py:declarative-output"
```

Generated variant records are instances of the base table and the selected
component. That is why `article` is both a `ContentTable` record and an
`ArticleFields` record.

!!! note "TableFields components do not parse alone"
    `TableFields` is a reusable group of declarations. It becomes parseable
    only when Talika composes it with a concrete `RowTable` or `ColumnTable`
    through a discriminator mapping.

## Ask for a Variant Schema

Declarative variants generate concrete schema classes. Use `variant_for(...)`
when code needs the generated class for assertions, introspection, or type
checks.

```python title="Getting generated variant classes"
--8<-- "docs_src/guides/advanced/variants.py:variant-for"
```

The generated class name is an implementation detail. The stable lookup is the
registered discriminator value, such as `"Article"` or `"Poll"`.

!!! tip "Use variant_for instead of class-name guessing"
    Generated classes have readable names, but user code should not depend on
    those names. Use `ContentTable.variant_for("Article")` when you need the
    schema selected for that value.

## Use Explicit Variant Classes When Names Matter

The explicit style uses `discriminator_field(...)` on the base schema and
registers concrete subclasses with `@Table.variant(value)`.

```python title="Explicit content variant classes"
--8<-- "docs_src/guides/advanced/variants.py:explicit-schema"
```

This style is useful when variants need their own class names, methods,
validators, custom output builders, or direct imports from project code.

```python title="Parsing explicit variants"
--8<-- "docs_src/guides/advanced/variants.py:explicit-parse"
```

```bash { .talika-terminal title="Explicit variant records" .speed-3}
--8<-- "docs_src/guides/advanced/variants.py:explicit-output"
```

Both styles use the same parser lifecycle. The difference is how the variant
schemas are declared.

Use `discriminator(..., variants={...})` when a compact table family is enough.
Use explicit subclasses when the variant class itself is part of your test or
domain code.

!!! warning "Register parsed discriminator values"
    If the discriminator has a parser, variant keys must match the parsed
    values, not the raw table text.

!!! warning "Register variants before parsing"
    Explicit `@Table.variant(...)` decorators should run while the schema
    module is imported. The first successful schema-family finalization by
    `parse()`, `parse_as()`, or `validate()` seals the registry. Registering another
    variant after that raises `SchemaDefinitionError`. `describe()` and
    `variant_for()` inspect the current registry without sealing it.

    `__variants__` is a read-only compatibility view. Always use the decorator
    rather than mutating that mapping directly.

## Unknown Variants Point to the Discriminator

When the discriminator value is not registered, Talika points at the cell that
selected the unknown variant.

```python title="A content type with no registered variant"
--8<-- "docs_src/guides/advanced/variants.py:unknown-variant"
```

```text title="Unknown variant diagnostic"
--8<-- "docs_src/guides/advanced/variants.py:unknown-variant-output"
```

The diagnostic includes the allowed values because the fix is usually to
change the authored discriminator cell or register another variant schema.

!!! note "The discriminator is required"
    A variant table must have one discriminator field. Talika cannot choose a
    record schema without it.

## Required Fields Belong to the Selected Variant

Variant fields are checked only when their variant is selected.

An article needs `Body`. A poll does not. A poll needs `Options`. An article
does not. Empty cells for other variants are allowed so one table can show the
union of all possible fields.

```python title="An article missing its required body"
--8<-- "docs_src/guides/advanced/variants.py:missing-variant-field"
```

```text title="Selected variant required-field diagnostic"
--8<-- "docs_src/guides/advanced/variants.py:missing-variant-field-output"
```

The schema name is `ContentTable[Article]`, not just `ContentTable`, because
the missing field belongs to the selected article variant.

!!! tip "Keep shared fields on the base schema"
    If every variant needs a field, declare it on the base table. If only one
    variant needs it, declare it on that variant.

## Non-Empty Wrong-Variant Fields Are Rejected

Variant tables often include rows or columns for every possible variant field.
That is fine when the cells are empty for records where the field does not
apply.

A non-empty value for the wrong variant usually means the table author put data
in the wrong place.

```python title="A poll with an article body"
--8<-- "docs_src/guides/advanced/variants.py:inapplicable-field"
```

```text title="Inapplicable field diagnostic"
--8<-- "docs_src/guides/advanced/variants.py:inapplicable-field-output"
```

This strict behavior prevents quiet mistakes. If the selected record is a
`Poll`, a non-empty `Body` cell is suspicious because `Body` belongs to
`Article`.

!!! warning "Empty wrong-variant cells are different"
    Empty cells for other variants are ignored. Non-empty cells for other
    variants are rejected by default because they look like misplaced data.

## Parse the Discriminator When Needed

The discriminator can have a parser. Talika runs that parser before looking up
the variant.

```python title="A normalized discriminator"
--8<-- "docs_src/guides/advanced/variants.py:parsed-selector"
```

```bash { .talika-terminal title="Parsed discriminator value" .speed-3}
--8<-- "docs_src/guides/advanced/variants.py:parsed-selector-output"
```

The table text contains `"ARTICLE"`, but the discriminator parser changes it
to `"article"`. The registered variant key must therefore be `"article"`.

Use this for case normalization, enum conversion, or project vocabulary where
the authored table text should be accepted in more than one spelling.

!!! note "Variant keys are Python values"
    Registered variant keys are not limited to strings. If the discriminator
    parser returns an enum member or another hashable value, register that
    parsed value.

## Give Each Variant Its Own Output Model

Variants can define their own `output_model` or `build_output()` behavior.
That is useful when `parse_as()` should return different project object types
from one table.

```python title="Per-variant output models"
--8<-- "docs_src/guides/advanced/variants.py:variant-output-models"
```

```bash { .talika-terminal title="Variant output objects" .speed-3}
--8<-- "docs_src/guides/advanced/variants.py:variant-output-models-output"
```

The article row becomes an `Article` object. The poll row becomes a `Poll`
object. The base table still owns the shared parsing contract, and each
variant owns the output shape for its selected records.

!!! tip "Keep conversion on the variant that owns the shape"
    If variants have different output types, define output conversion on the
    variant classes or components. The base table should only handle output
    that is common to every record.

## Variants Work In Row Tables Too

Column tables are a natural fit for CMS content cards, but variants are not
limited to column-shaped data. Row tables can use the same discriminator model.

```python title="A row table with payment variants"
--8<-- "docs_src/guides/advanced/variants.py:row-variants"
```

```bash { .talika-terminal title="Row-table variant records" .speed-3}
--8<-- "docs_src/guides/advanced/variants.py:row-variants-output"
```

This shape reads well when each row is naturally one event or object. The
`card` row needs `last_four`; the `bank` row needs `account`. The empty cells
for the other payment type are ignored because they do not contain data.

!!! note "Choose shape before variant style"
    First decide whether rows or columns make the authored table readable.
    Then decide whether concise `TableFields` components or explicit variant
    classes make the schema easier to maintain.
