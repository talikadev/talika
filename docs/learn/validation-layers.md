---
icon: lucide/layers
---

# Validation Layers

Not every table problem belongs to the same layer. Understanding the layers
makes errors easier to explain and schemas easier to design.

Consider this table:

```gherkin title="Several different problems"
--8<-- "docs_src/learn/validation-layers.py:gherkin"
```

It has more than one kind of issue. Each issue should be reported at the layer
that understands it best.

## Field parsing

Field parsing handles one cell becoming one Python value.

```text title="A field parsing problem"
--8<-- "docs_src/learn/validation-layers.py:field-error"
```

This is the right layer for numbers, booleans, choices, dates, lists, and other
cell-level syntax.

## Required fields

Required-field validation answers a simpler question: did the author provide
the value the table needs?

```text title="A required value problem"
--8<-- "docs_src/learn/validation-layers.py:required-error"
```

This is not a parsing problem. There is no value to parse.

## Whole-table rules

Some rules require more than one record. Duplicate emails are a table-level
concern because no single row can know whether another row used the same email.

```text title="A table-level problem"
--8<-- "docs_src/learn/validation-layers.py:table-error"
```

## References

References are another layer. A cell can parse correctly and still point to an
item that does not exist.

```text title="A reference problem"
--8<-- "docs_src/learn/validation-layers.py:reference-error"
```

!!! note "Layered errors are easier to fix"
    If the age is invalid, point to the age cell. If emails are duplicated,
    explain the table rule. If a reference is missing, point to the reference
    cell. The reader should not have to guess which kind of mistake they made.
