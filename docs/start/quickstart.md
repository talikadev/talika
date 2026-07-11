---
icon: lucide/rocket
tags:
  - Quickstart
  - BDD
  - Data tables
  - Parsing
  - Schemas
---

# Quickstart

This quickstart builds a small `UserTable` contract and uses it to parse a
real `pytest-bdd` data table.

By the end, the table text from a feature file will become Python records with
an integer age, a list of roles, a strict boolean flag, source-aware errors, and
a clear choice between `parse()` and `parse_records()`.

The examples assume Talika is already available in your test environment.

## Start with a feature table

A `pytest-bdd` data table is friendly in a feature file:

```gherkin title="users.feature"
--8<-- "docs_src/start/quickstart.py:feature"
```

Inside the step function, `pytest-bdd` passes the same table as plain nested
strings:

```python title="What pytest-bdd passes to the step"
--8<-- "docs_src/start/quickstart.py:datatable"
```

That shape is useful because it is simple, but it has no contract. Python does
not know that `age` should become an `int`, that `active` should be a strict
boolean, or that `name` is required.

!!! tip "The mental model"
    Talika sits between the authored table and your test setup code. The feature
    file stays readable, while the Python side receives records with parsed
    values and source-aware validation.

## Write the first contract

Use `RowTable` when the first row contains field labels and each later row is
one record.

```python title="users_table.py"
--8<-- "docs_src/start/quickstart.py:contract"
```

There are two names to keep in your head:

- The string passed to `field(...)` is the table label. It must match the text
  written in the feature table.
- The Python attribute name is what your code reads after parsing.

So `name = field("name", required=True)` means: find a column labelled `name`,
reject the table if that field is missing or empty, then expose the parsed value
as `record.name`.

The same pattern scales to typed fields:

- `age: int` lets Talika infer the integer parser from the annotation.
- `roles = field("roles", parser=split(","))` turns one cell into a list.
- `active = field("active", parser=boolean(), default=True)` accepts explicit
  boolean words and supplies `True` only when the whole `active` column is
  absent.

!!! warning "Missing is different from empty"
    `default=True` is used when the column is not present in the table. An
    explicit empty cell is still authored data, so Talika treats it according
    to the field's empty-cell policy instead of silently replacing it with the
    default.

## Parse it

Call `UserTable.parse(datatable)` at the boundary where your step receives the
datatable.

```python title="Parse the datatable"
--8<-- "docs_src/start/quickstart.py:parse"
```

Here is the same example as a small file you can run:

```python title="users_table.py"
--8<-- "docs_src/start/quickstart.py:complete"
```

```bash { .talika-terminal title="Run the first table" .speed-2}
--8<-- "docs_src/start/quickstart.py:complete-output"
```

The important part is not the pretty `repr`. It is the data boundary:

- `users[0].age` is `27`, not `"27"`.
- `users[0].roles` is `["Developer", "Manager"]`, not one comma-separated
  string.
- `users[0].active` is `True`, parsed by a strict boolean parser.
- `users[0].as_dict()` gives you a normal dictionary when you want to pass the
  parsed values into a factory or fixture.

!!! info "Why strict boolean parsing matters"
    Python's `bool("no")` is `True`, because every non-empty string is truthy.
    Talika's `boolean()` parser does not use Python truthiness. It accepts known
    tokens such as `yes`, `no`, `true`, and `false`, and rejects anything vague.

## Defaults are for absent fields

If the feature table does not mention `active` at all, the schema default is
used:

```python title="Missing optional column"
--8<-- "docs_src/start/quickstart.py:missing-active"
```

That makes optional columns useful for feature files. Authors can keep simple
tables short, while the schema still gives Python a complete value.

## Choose parse or parse_records

For many schemas, `parse()` and `parse_records()` appear to return the same
thing because the default public output is the Talika record itself. The
difference matters once your schema declares an output model.

```python title="Public output versus Talika records"
--8<-- "docs_src/start/quickstart.py:output-model"
```

Use `parse()` for the normal step result. It returns the schema's public output:

- by default, Talika record objects
- with `output_model`, your dataclass, Pydantic model, or custom output object
- with a custom `build_output()`, whatever your schema chooses to return

Use `parse_records()` when you specifically need Talika's record object. That
record keeps helper methods and source metadata:

```python title="Inspecting source metadata"
--8<-- "docs_src/start/quickstart.py:parse-records-source"
```

!!! note "A practical rule"
    In step definitions, start with `parse()`. Reach for `parse_records()` when
    you are building fixtures, debugging table coordinates, calling `as_dict()`,
    or raising your own source-aware `TableError`.

## Use the contract in pytest-bdd

In a real test, the schema usually lives beside the step module or in a small
`tables.py` module shared by related steps.

```python title="test_users.py"
--8<-- "docs_src/start/quickstart.py:step"
```

That is the whole integration. `pytest-bdd` still owns scenarios and step
matching. Talika only owns the table boundary.

If you like a consistent parsing facade in pytest code, Talika also provides a
`talika` fixture:

```python title="The talika fixture"
--8<-- "docs_src/start/quickstart.py:fixture"
```

Both examples call the same schema parser. Pick the style that keeps your test
suite easiest to read.

## See a useful failure

Now change the authored table so three cells are wrong:

```python title="Bad input"
--8<-- "docs_src/start/quickstart.py:bad-table"
```

`error_mode="collect"` asks Talika to report independent problems in one pass.
That is useful while writing feature files because the author can fix several
cells before running the scenario again.

```bash { .talika-terminal title="Collected table errors" .speed-2}
--8<-- "docs_src/start/quickstart.py:collect-output"
```

Read one error from left to right:

- `code=empty_required` is stable enough for tooling.
- `schema=UserTable` tells you which contract rejected the table.
- `field='name'` tells you which table field failed.
- `row=2, column=1` points back to the authored cell.
- `value=''` preserves the original bad value.
- the hint tells the author what kind of fix makes sense.

That is the main point of Talika: your step code stops hand-parsing strings,
and table authors get failures that point to the table they wrote.
