---
icon: lucide/table
---

# BDD Data Tables

BDD data tables are a friendly way to put several related examples beside a
Gherkin step. They let a scenario say, "these users exist" or "these content
items are available" without turning every value into a separate sentence.

```gherkin title="A feature table"
--8<-- "docs_src/learn/datatables.py:gherkin"
```

To a reader, that table already has meaning. Asha is an admin. Bruno is an
editor. One user is active and the other is not.

Inside Python, though, the table is just nested strings:

```python title="The datatable passed to Python"
--8<-- "docs_src/learn/datatables.py:datatable"
```

That simplicity is useful. It is also where small parsing decisions begin to
scatter across a test suite.

## The invisible work

Every table needs a few quiet decisions before test code can safely use it:

- which row contains labels
- which labels are required
- whether extra labels are allowed
- how cells become numbers, booleans, lists, dates, enums, or domain objects
- what an empty cell means
- what error should point back to the feature file when a value is wrong

Without a table layer, that work often appears directly inside step functions:

```python title="A first manual parser"
--8<-- "docs_src/learn/datatables.py:manual-python"
```

This is not bad code for one small table. The problem is that every new table
invites another slightly different version of the same glue.

!!! warning "The table still contains text"
    A cell that looks like `yes` is still text. A cell that looks like `30` is
    still text. The table only becomes reliable when the project decides what
    those words mean.

## Where the confusion starts

The common trap is assuming Python will guess the table meaning correctly.

```python title="A boolean surprise"
--8<-- "docs_src/learn/datatables.py:surprise"
```

That is why table parsing should be deliberate. If a feature file says `no`,
test code should not accidentally treat it as true because Python truthiness
works that way.

## The useful mental model

Think of a BDD data table as authored test data, not as ready-to-use Python
data. The table is readable for humans first. A table layer gives it shape,
types, validation, and diagnostics before the rest of the test uses it.

!!! tip "A good table has two readers"
    The feature author reads the table as product language. The test code reads
    the parsed result as Python data. Good documentation and good tooling make
    both readings line up.
