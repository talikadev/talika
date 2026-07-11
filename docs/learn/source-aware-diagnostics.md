---
icon: lucide/map-pin
tags:
  - Diagnostics
  - Source metadata
  - Error handling
  - Validation
---

# Source-Aware Diagnostics

The best table error tells the reader where to look. Not just which Python
function failed, but which authored cell caused the problem.

```gherkin title="A table with bad cells"
--8<-- "docs_src/learn/source-aware-diagnostics.py:bad-table"
```

A useful diagnostic points back to the table:

```text title="A source-aware error"
--8<-- "docs_src/learn/source-aware-diagnostics.py:error"
```

That message carries two kinds of information:

- human text that explains the failure
- structured details that tools can inspect

## What the fields are for

`schema` tells you which contract was parsing the table. `field` tells you
which declared table field failed. `row` and `column` point to the authored
cell. `value` preserves what the author wrote. `code` gives tooling a stable
category.

!!! example "Reading the diagnostic"
    The reader does not need to inspect the parser function first. They can go
    to row 2, column 2, see `old`, and understand why an integer field rejected
    it.

## Several errors at once

During authoring, it is often better to report independent problems together:

```text title="Collected diagnostics"
--8<-- "docs_src/learn/source-aware-diagnostics.py:collected"
```

See how to [build an error from a source cell](../guides/advanced/source-model.md#build-errors-from-source-cells){ data-preview }
and how to [inspect an aggregate of collected errors](../guides/advanced/collect-errors.md#inspect-the-aggregate){ data-preview }.

This helps feature authors fix a table in one pass instead of chasing one
failure per test run.

!!! tip "Diagnostics are part of the user experience"
    A table parser is not only successful when valid data passes. It is also
    successful when invalid data fails in a way that a reader can fix quickly.
