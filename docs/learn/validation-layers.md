---
icon: lucide/layers
tags:
  - Validation
  - Error handling
  - References
  - Diagnostics
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

Work from the smallest useful scope outward. First decide whether one cell can
be parsed, then whether one record is complete and coherent, and only then ask
questions that depend on the rest of the table.

## Field parsing

Field parsing handles one cell becoming one Python value.

```text title="A field parsing problem"
--8<-- "docs_src/learn/validation-layers.py:field-error"
```

This is the right layer for numbers, booleans, choices, dates, lists, and other
cell-level syntax.

A field parser should not need sibling fields or other records. Once a rule
needs that wider context, moving it to validation keeps the parser focused on
one authored value.

## Required fields

Required-field validation answers a simpler question: did the author provide
the value the table needs?

```text title="A required value problem"
--8<-- "docs_src/learn/validation-layers.py:required-error"
```

This is not a parsing problem. There is no value to parse.

Required-field checks also distinguish a label that is missing from the table
from a required cell that is present but blank. Those cases need different
fixes, so they receive different diagnostics.

## Record rules

Once every field in one record has parsed, record validation can compare those
values together. A minimum-age rule, for example, needs the parsed `age` but
does not need to inspect any other record in the table.

```text title="A record-level problem"
--8<-- "docs_src/learn/validation-layers.py:record-error"
```

This layer is a good fit for rules such as conditional requirements, valid
date ranges, or combinations of fields that are individually valid but do not
make sense together.

## Whole-table rules

Some rules require more than one record. Duplicate emails are a table-level
concern because no single row can know whether another row used the same email.

Whole-table validation runs only after Talika has complete parsed records. It
is therefore the right place for uniqueness, aggregate limits, ordering, and
relationships that must be checked across the collection.

```text title="A table-level problem"
--8<-- "docs_src/learn/validation-layers.py:table-error"
```

## References

References are another layer. A cell can parse correctly and still point to an
item that does not exist.

```text title="A reference problem"
--8<-- "docs_src/learn/validation-layers.py:reference-error"
```

The guides show these layers in practice: [record validation](../guides/basic/record-validation.md#add-a-record-validator){ data-preview },
[whole-table validation](../guides/basic/table-validation.md#add-a-table-validator){ data-preview },
and [reference resolution](../guides/advanced/references.md#resolve-one-reference){ data-preview }.

!!! note "Layered errors are easier to fix"
    If the age text is invalid, point to the age cell. If one parsed record
    breaks a business rule, explain that record rule. If emails are duplicated,
    explain the whole-table rule. If a reference is missing, point to the
    reference cell. The reader should not have to guess which kind of mistake
    they made.
