---
icon: lucide/box
tags:
  - Records
  - Output models
  - Data boundary
  - Test objects
---

# From Records To Test Objects

After a table is parsed, the test needs something useful to work with. That
might be a Talika record, a dictionary for a factory, a dataclass, a Pydantic
model, or a project object.

The first parsed result is usually a record:

```python title="A parsed record"
--8<-- "docs_src/learn/records-and-outputs.py:record"
```

Records are intentionally small. They hold declared fields as attributes and
keep source information for diagnostics.

## Records are good at the boundary

Records are especially useful when the next step is a fixture or factory:

```python title="Passing parsed data to a factory"
--8<-- "docs_src/learn/records-and-outputs.py:factory"
```

The record owns table parsing concerns. The factory owns object creation. Those
two jobs should stay separate.

!!! tip "Keep the boundary boring"
    The parsed record should be predictable: fields in, validated values out.
    Let application factories, API clients, or ORM setup code do the rest.

## Sometimes you want project objects directly

A schema can configure a public output object after parsing and validation:

```python title="A dataclass output"
--8<-- "docs_src/learn/records-and-outputs.py:dataclass-output"
```

Parsing still returns Talika records. Conversion is an explicit second API:

```python title="parse() versus parse_as()"
--8<-- "docs_src/learn/records-and-outputs.py:parse-vs-records"
```

## The practical distinction

Use `parse()` for schema records: source metadata, `as_dict()`, and
table-focused validation support. Use `parse_as()` when the caller is ready
for a dataclass, Pydantic model, or another project object.

The output-model guide shows how to [add a dataclass output model](../guides/advanced/output-models.md#add-a-dataclass-output-model){ data-preview }
and how to [choose the right return shape](../guides/advanced/output-models.md#choose-the-right-return-shape){ data-preview }.

!!! note "The names are literal"
    `parse()` means "parse schema records." `parse_as()` means "parse, validate,
    then convert those records."

!!! note "Record values remain assignable"
    Schema declarations are frozen after compilation, but records returned by
    `parse()` are not frozen. A caller may assign a
    declared value after parsing. `table_source` cells and `table_extras`
    remain read-only so diagnostics cannot lose their original provenance.
