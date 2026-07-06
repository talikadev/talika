---
icon: lucide/box
---

# From Records To Test Objects

After a table is parsed, the test needs something useful to work with. That
might be a Talika record, a dictionary for a factory, a dataclass, a Pydantic
model, or a project object.

The first parsed result is usually a record:

```python title="A parsed record"
--8<-- "docs_src/learn/records-and-outputs.py:record"
```

Records are intentionally small. They hold declared fields as attributes and
keep source information for diagnostics.

## Records are good at the boundary

Records are especially useful when the next step is a fixture or factory:

```python title="Passing parsed data to a factory"
--8<-- "docs_src/learn/records-and-outputs.py:factory"
```

The record owns table parsing concerns. The factory owns object creation. Those
two jobs should stay separate.

!!! tip "Keep the boundary boring"
    The parsed record should be predictable: fields in, validated values out.
    Let application factories, API clients, or ORM setup code do the rest.

## Sometimes you want project objects directly

A schema can build a public output object after parsing and validation:

```python title="A dataclass output"
--8<-- "docs_src/learn/records-and-outputs.py:dataclass-output"
```

Now normal parsing can return `User` objects, while record parsing still gives
access to Talika's source-aware record.

```python title="parse() versus parse_records()"
--8<-- "docs_src/learn/records-and-outputs.py:parse-vs-records"
```

## The practical distinction

Use `parse()` when the step wants the schema's normal output. Use
`parse_records()` when you need the intermediate record: source metadata,
`as_dict()`, or table-focused validation support.

!!! note "The names are literal"
    `parse()` means "give me the public parsed result." `parse_records()` means
    "give me the table records before public output conversion."
