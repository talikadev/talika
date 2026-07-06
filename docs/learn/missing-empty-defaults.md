---
icon: lucide/list-minus
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

!!! warning "Avoid accidental defaults"
    A default should not hide an incomplete table. Use defaults when omission is
    normal. Use validation when a blank cell probably means the author missed
    something.
