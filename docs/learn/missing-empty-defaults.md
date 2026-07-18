---
icon: lucide/list-minus
tags:
  - Missing values
  - Empty cells
  - Defaults
  - Data modeling
---

# Missing, Empty, And Defaults

One of the easiest table mistakes is treating missing and empty as the same
thing. They are different authoring choices, and they usually deserve different
behavior.

## Missing means the field was not written

In this table, there is no `active` field at all:

```gherkin title="The active column is missing"
--8<-- "docs_src/learn/missing-empty-defaults.py:missing-column"
```

A schema can safely say, "when authors do not mention this field, use the
project default."

Because the label is absent, the same rule applies to every record in that
table. There is no authored `active` cell to parse or point to in a diagnostic.

```python title="A default for the absent field"
--8<-- "docs_src/learn/missing-empty-defaults.py:contract"
```

Here, missing `active` can mean `True` because the field was omitted.

## Empty means the author wrote a blank cell

This table is different:

```gherkin title="The active cell is empty"
--8<-- "docs_src/learn/missing-empty-defaults.py:empty-cell"
```

The author included `active`, then left the value blank. That could mean
"unknown", "not applicable", "intentionally empty", or simply "I forgot to fill
it in." The table layer should not pretend those are all the same.

!!! note "A useful distinction"
    Missing is about table shape. Empty is about a specific cell. Defaults are
    usually safe for missing fields, but explicit empty cells deserve a clear
    policy.

## Sometimes empty is meaningful

Some fields really do allow an empty or null-like value. Make that explicit:

```python title="An optional text value"
--8<-- "docs_src/learn/missing-empty-defaults.py:explicit-none"
```

The important habit is to decide. Once missing, empty, and default values are
separate ideas, feature files become easier to review and parser behavior
becomes easier to explain.

Defaults are schema-owned final Python values; they are not passed through a
cell parser. Use a hashable, non-mutable static default for shared constants,
and use `default_factory` for fresh mutable values such as lists or mappings.

Compare the concrete behavior for [missing optional fields](../guides/basic/missing-empty-defaults.md#missing-optional-fields){ data-preview }
and [present but empty cells](../guides/basic/missing-empty-defaults.md#empty-cells-are-present-values){ data-preview }.

!!! warning "Avoid accidental defaults"
    A default should not hide an incomplete table. Use defaults when omission is
    normal. Use validation when a blank cell probably means the author missed
    something.
