---
icon: lucide/workflow
tags:
  - Parsing lifecycle
  - Validation
  - Transformation
  - Output models
---

# The Table Lifecycle

By this point, the full mental model is visible: a feature table starts as
authored text and ends as validated Python output.

Here is a compact content table:

```gherkin title="Authored compact table"
--8<-- "docs_src/learn/table-lifecycle.py:source-table"
```

The test code would rather work with a logical table:

```python title="Logical table after expansion"
--8<-- "docs_src/learn/table-lifecycle.py:logical-table"
```

The lifecycle is the path between those two views and the final output objects.

```text title="Conceptual lifecycle"
--8<-- "docs_src/learn/table-lifecycle.py:lifecycle"
```

## Each stage has a job

Source-aware cells remember where the value came from. A table transform can
turn compact authoring syntax into a more regular logical table. Shape checks
make sure labels and rows are usable. Field parsers convert cell text into
Python values. Validation checks the records and the table as a whole. Output
construction gives the test the object style it wants.

`parse()` and non-raising `validate()` stop after validation and return schema
records. `parse_as()` continues into output construction. Each phase produces
the same Diagnostic Model v1 values, and an error stops later work that
depends on complete records. Warning-only validation keeps the records.

```python title="One schema can own the lifecycle"
--8<-- "docs_src/learn/table-lifecycle.py:contract"
```

!!! tip "You usually customize one stage"
    Most projects do not need to replace the whole lifecycle. They define the
    table shape, choose parsers, maybe add validation, and let the rest of the
    pipeline stay ordinary.

## Why the lifecycle matters

Calling this "just parsing" misses the point. The hard part is not only turning
one string into one value. The hard part is preserving author intent while the
table moves through shape checks, transformations, validation, references, and
output construction.

The advanced guides show how to [preserve authored cells during transformation](../guides/advanced/transform-tables.md#preserve-the-authored-cell){ data-preview }
and how [validation fits before output conversion](../guides/advanced/output-models.md#validation-runs-before-output-conversion){ data-preview }.

!!! note "The source cell remains important"
    Even after a compact table expands into several logical records, the
    original authored cell should still be available for diagnostics. That is
    what makes advanced table language safe for feature authors.
