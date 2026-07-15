---
icon: lucide/text-cursor-input
tags:
  - Cell parsing
  - Type conversion
  - Data tables
  - Schemas
---

# Cells Are Text First

Feature tables are written for people. That means every value begins as text,
even when it looks like something more specific.

```gherkin title="Text that looks typed"
--8<-- "docs_src/learn/cells-are-text.py:gherkin"
```

Python receives those cells as strings:

```python title="Same values in Python"
--8<-- "docs_src/learn/cells-are-text.py:python-values"
```

The table looks typed because humans recognize the words. Python does not.

## Looking typed is not the same as being typed

Some conversions are obvious. Others are traps.

```python title="Unsafe guesses"
--8<-- "docs_src/learn/cells-are-text.py:bad-guesses"
```

`"34"` can become an integer. `"Admin, Editor"` can become a list. `"draft"`
can become an allowed state. But none of that should happen by accident.

!!! warning "Truthiness is not table meaning"
    Python treats every non-empty string as true. That is useful in ordinary
    Python code, but it is not a safe way to read authored table values such as
    `no`, `off`, or `disabled`.

## Parsing is a table decision

A table contract makes conversion explicit:

```python title="Explicit cell meaning"
--8<-- "docs_src/learn/cells-are-text.py:contract"
```

This says:

- `age` should become an integer
- `active` should use the explicitly declared `yes/no` Boolean vocabulary
- `roles` should split one cell into several items
- `state` should be one of the allowed words

The important part is not the specific parser. The important part is that the
meaning lives in one visible place.

The parser guide covers the concrete building blocks, from
[scalar parsers](../guides/basic/parser-factories.md#start-with-scalar-parsers){ data-preview }
to [lists and parser composition](../guides/basic/parser-factories.md#build-lists-with-split-compose-and-each){ data-preview }.

!!! tip "Start strict, loosen intentionally"
    A strict parser may feel fussy on day one, but it prevents quiet test bugs.
    If authors need more vocabulary later, add it deliberately.
