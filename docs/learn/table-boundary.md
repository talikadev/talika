---
icon: lucide/split-square-horizontal
---

# The Table Boundary

The most important idea in Talika is the boundary between authored table text
and dependable Python data.

On one side of the boundary is the feature file:

```gherkin title="Feature text"
--8<-- "docs_src/learn/table-boundary.py:gherkin"
```

On the other side is what the test setup really wants:

```python title="Useful test data"
--8<-- "docs_src/learn/table-boundary.py:desired"
```

The middle is where table work happens. The BDD framework can hand your step a
datatable:

```python title="Step input"
--8<-- "docs_src/learn/table-boundary.py:datatable"
```

But it cannot know your project vocabulary. It does not know whether `verified`
accepts `yes/no`, `true/false`, `Y/N`, or something more domain-specific.

## Why the boundary should be explicit

When table rules are implicit, they hide in step functions. That usually feels
fine at first. Then a second step parses the same idea differently. Later, a
feature author changes a label and the failure points to Python setup code
instead of the table.

An explicit boundary gives the project one place to answer:

- what shape this table has
- which values are allowed
- how text becomes Python values
- how to report mistakes back to the feature author

```python title="One boundary object"
--8<-- "docs_src/learn/table-boundary.py:boundary"
```

!!! example "A table-reading moment"
    The feature author wrote `yes`. The test probably wants `True`. The boundary
    is the place where that translation should be intentional, visible, and
    reusable.

## The boundary is not business logic

A table contract should not create accounts, call services, or perform the
scenario action. It should prepare trustworthy input for that work.

!!! warning "Keep actions outside the table layer"
    Parsing a table and acting on parsed data are different responsibilities.
    Keeping them separate makes failures clearer and keeps scenarios easier to
    change.
