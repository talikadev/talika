---
icon: lucide/circle-help
---

# Why Talika?

We built Talika because we needed BDD data tables to stay simple for authors
and still be reliable for test code.

The core package has zero runtime dependencies. You can start with plain Python
schemas, parse ordinary `list[list[str]]` tables, and add only the optional
extras you need for CLI checks or Pydantic output. At the same time, Talika
gives you the pieces to build your own table language: schema validation,
typed cell parsers, custom cell DSL rules, source-aware errors, variants,
references, table transforms, and output models.

In `pytest-bdd`, a Gherkin data table reaches the step function as a raw
`list[list[str]]`. That is simple and flexible, but it means every project has
to decide what the table means:

- which row or column contains labels
- which fields are required
- how strings become `int`, `bool`, `Decimal`, enums, or lists
- what an empty cell means
- whether old labels are still accepted
- what custom words like `random`, `today`, or `3 Articles` mean
- where to point the user when a value is wrong

For one small table, hand-written parsing is fine. In a real test suite, that
glue starts to spread across step definitions.


```python title="A typical first parser"
--8<-- "docs_src/why/why.py:a"
```

The problem is not the code above. The problem is having many versions of it:
different boolean words, different defaults, different error messages, and
tracebacks that point to Python code instead of the cell in the `.feature`
file.

## The missing layer

Cucumber-JVM has a `DataTableType` layer for converting Gherkin tables into
objects. Python teams using `pytest-bdd` get the raw table and must build that
layer themselves.

That missing layer is where most of the important table decisions actually
live. It is not just "turn rows into dictionaries". A useful table layer should
know the expected labels, choose the right orientation, parse cell values,
apply defaults, reject unknown or misspelled fields, support project vocabulary,
and return errors that point back to the feature file.

Without that layer, these rules usually end up scattered across step
definitions:

- one step accepts `yes` and `no`, another accepts `true` and `false`
- one table treats an empty cell as `None`, another keeps it as `""`
- one parser supports old labels, another breaks when wording changes
- one failure says which cell is wrong, another only raises `ValueError`

Talika fills this gap for Python. It sits between the BDD framework and your
test setup code

The idea is deliberately small: keep the feature table readable, move table
rules into one reusable contract, and let the rest of the test work with normal
Python objects.

```gherkin title="Gherkin"
--8<-- "docs_src/why/why.py:b"
```

```python title="A Talika table contract"
--8<-- "docs_src/why/why.py:c"
```

1.  Defines a new row-oriented table schema. When parsed, each data row in the BDD table will be validated and converted into a `UserTable` record instance.


2. ```required=True```

    This column must be present in the table and its cells cannot be empty.

3. Because it is annotated with : `int`, talika's metaclass automatically infers and assigns an integer parser to this field. You don't need to explicitly pass `parser=integer()`.

4. `parser=split(",")`


    Takes the raw string from the table cell and splits it by commas into a list `[str]`. By default, it automatically strips whitespace around each item and ignores empty segments.

5. `parser=boolean()`

    Strictly converts tokens like "true", "false", "yes", "no" into a bool. Unknown values will raise a validation error   instead of relying on Python's truthiness.

    `default=True`

    If the "active" column is entirely missing from the BDD table, the value for all parsed records will default to True.


6.  Takes raw rows (or source-aware `TableData`) from `datatable`, matches the headers to your declared fields,

    runs the specified parsers (like `split` and `boolean`), and validates everything.


    Returns a list of validated `UserTable` record objects.


```bash { .talika-terminal title="User" }
--8<-- "docs_src/why/why.py:d"
```

Now the table rules live in one reusable contract. The step receives typed
records, and bad data fails with the field, row, column, item ID when present,
original value, stable error code, and a human-readable hint.

## What Talika gives you

Talika is useful because the pieces work together:

- `RowTable` and `ColumnTable` for the two common table shapes
- `field()`, `id_field()`, aliases, defaults, and empty-cell policies
- parser factories for booleans, numbers, choices, lists, and composition
- `CellDSL` for project-owned cell vocabulary
- variants when one table contains different record types
- references between records in the same scenario
- source-aware diagnostics with stable error codes
- optional static checks for `.feature` files
- optional output as dataclasses, Pydantic models, or custom objects

That source-aware part matters. A useful failure should tell the author where
to look:

```text
Field parser failed: invalid literal for int() with base 10: 'old'
(code=parser_failed, schema=UserTable, field='age', row=2, column=2, value='old').
Hint: Check the cell value or adjust the field parser for this syntax.
```

The error points to the authored table, not only to the parser function.

## Custom table language

Talika does not force one DSL on every team. It gives you safe hooks to create
the vocabulary your feature files need.

For example, a compact content table might let authors write `1-3` for three
IDs and `3 Articles` to repeat one value across those IDs:

```python title="Compact table syntax"
--8<-- "docs_src/why/why.py:e"
```

```gherkin title="Author-friendly table"
--8<-- "docs_src/why/why.py:f"
```



Talika can expand that into three logical records while preserving the original
source cell. If `3 Articles` is wrong, the diagnostic can still point to that
exact cell.

For cell-level vocabulary, use `CellDSL`:

```python title="Project-owned cell DSL"
--8<-- "docs_src/why/why.py:g"
```

Now your tables can use simple words like `random` or `20 words`, and your
project decides exactly what those words mean.

## How Talika compares

| Tool | What it is good at | What Talika adds |
| --- | --- | --- |
| `pytest-bdd` datatables | Passing Gherkin table text into Python steps | A schema contract, typed records, validation, source-aware errors, and static checking |
| Cucumber-JVM `DataTableType` | Converting Cucumber data tables in the JVM ecosystem | A Python table-conversion layer designed around `pytest-bdd`, source metadata, row and column tables, variants, and table transforms |
| Pydantic | Validating Python data models after the data already has shape | The earlier step: reading a two-dimensional Gherkin table, matching labels, parsing cells, preserving source coordinates, then optionally building Pydantic models |
| `factory_boy` | Creating test objects and ORM fixtures from Python factories | Parsing human-authored feature tables before fixture creation |
| Scenario Outlines | Running the same scenario with different example values | Structured multi-record data inside one scenario |
| Hand-written dict parsing | Quick one-off conversion | Reusable parsing rules, consistent validation, better diagnostics, and less drift across steps |

These tools can work together. Talika is not trying to replace them.

```python title="Talika with a factory"
--8<-- "docs_src/why/why.py:h"
```

```python title="Talika with Pydantic output"
--8<-- "docs_src/why/why.py:i"
```

Pydantic validates the model. `factory_boy` can build the fixture. Talika owns
the table boundary: labels, cells, source locations, table shape, and table
authoring rules.

## Where Talika shines

Talika is most useful when table data is part of the product language of your
tests:

- QA, product, or developers edit `.feature` files directly.
- You want one reusable contract instead of repeated parsing glue.
- You need strict schema validation without giving up readable tables.
- You want a zero-dependency core and optional integrations only when needed.
- You need custom cell syntax such as `random`, `20 words`, `today`, `1-3`, or
  `3 Articles`.
- You want failures to point to the original `.feature` cell, even after table
  transforms.
- You have column-oriented tables, variants, local references, or table-level
  validation.
- CI or editor tooling should check feature tables before the scenario runs.

## What Talika is not

Talika is intentionally narrow.

It is not a test runner, not a replacement for `pytest-bdd`, not a fixture
factory, not a business workflow engine, and not a general object validation
library. It also does not force one universal Gherkin table DSL.

Talika owns the mechanics of turning authored tables into useful Python
objects. Your project owns the meaning of the table. That is the point: simple
tables for humans, strong contracts for code, and enough extension points to
grow with your test suite.
