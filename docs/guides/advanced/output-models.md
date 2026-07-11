---
icon: lucide/box
tags:
  - Output models
  - Dataclasses
  - Pydantic
  - Records
---

# Output Models

Talika schemas are excellent at parsing authored tables. They know labels,
aliases, parsers, defaults, source cells, validation rules, references, and
table shape.

Application code often wants something narrower. A test setup may want a
dataclass, a Pydantic model, a factory payload, or a small dictionary that can
be passed directly to a helper. Output models let the schema do the table work
first, then convert each validated record into the public object your test
code wants to use.

```gherkin title="A table that should become project objects"
--8<-- "docs_src/guides/advanced/output-models.py:feature-users"
```

!!! tip "Separate parsing from public output"
    Let the schema own the table contract. Let the output model represent the
    object your tests or factories actually need after the table has been
    parsed and validated.

## Start With Schema Records

Without an output model, `parse()` returns schema record objects.

```python title="A normal schema record"
--8<-- "docs_src/guides/advanced/output-models.py:record-schema"
```

```python title="The authored datatable"
--8<-- "docs_src/guides/advanced/output-models.py:user-table"
```

```bash { .talika-terminal title="Default parse output" .speed-3}
--8<-- "docs_src/guides/advanced/output-models.py:record-output"
```

Schema records are useful. They carry parsed values and Talika metadata. They
also support helpers such as `as_dict()` and `source_for(...)`.

The tradeoff is that schema records are table-facing objects. They still
belong to the parsing layer. If the rest of the test suite already uses a
`User` dataclass or a domain factory payload, returning schema records may
push table-specific details farther into the code than necessary.

!!! note "Schema records are not wrong"
    Use schema records when the caller needs table source metadata,
    intermediate fields, or schema methods. Use output models when the caller
    should receive project objects.

## Add a Dataclass Output Model

Set `output_model` to a callable that accepts the parsed record fields as
keyword arguments. A dataclass is the simplest example.

```python title="A dataclass output model"
--8<-- "docs_src/guides/advanced/output-models.py:dataclass-model"
```

After fields are parsed and defaults are applied, Talika calls:

```python title="Default output-model call"
--8<-- "docs_src/guides/advanced/output-models.py:default-model-call"
```

That means the output model receives Python values, not raw table text. In the
example below, `age` reaches the dataclass as `34`, not `"34"`.

```python title="parse() and parse_records() side by side"
--8<-- "docs_src/guides/advanced/output-models.py:parse-vs-records"
```

```bash { .talika-terminal title="Public output and schema records" .speed-3}
--8<-- "docs_src/guides/advanced/output-models.py:parse-vs-records-output"
```

`parse()` returns the public objects. `parse_records()` skips output conversion
and returns schema instances.

!!! warning "Match output fields to parsed fields"
    The default `output_model` call uses every value from `record.as_dict()`.
    The model constructor must accept those names, or you should override
    `build_output()` and choose the payload yourself.

## Keep Records When You Need Source Detail

Output objects are intentionally clean. They usually do not know about table
rows, columns, original text, aliases, or Talika source cells.

Use `parse_records()` when the caller needs those details.

```python title="Inspecting source metadata before output conversion"
--8<-- "docs_src/guides/advanced/output-models.py:source-records"
```

This is common in diagnostics, custom assertions, and helper code that needs
to explain where a table value came from. A domain object such as `User` should
not normally need to know that `age` came from row 2, column 2 of a feature
file. The schema record is the right object for that job.

!!! tip "Use parse_records for table-aware work"
    If the code needs `source_for(...)`, `table_source`, `item_id`, or schema
    methods, ask for records. If the code only needs clean project data, use
    `parse()`.

## Validation Runs Before Output Conversion

Output conversion happens near the end of the lifecycle. Talika first parses
fields, applies defaults, resolves references, and runs validation. Only then
does it build the public output object.

```python title="Validation before model construction"
--8<-- "docs_src/guides/advanced/output-models.py:validation-before-output"
```

If the record is invalid, the output model is not constructed.

```python title="A record rejected before output conversion"
--8<-- "docs_src/guides/advanced/output-models.py:validation-before-output-call"
```

```text title="Record validation still owns this failure"
--8<-- "docs_src/guides/advanced/output-models.py:validation-before-output-result"
```

This keeps responsibilities clear. The schema explains table rules and
record-level rules. The output model receives records that have already passed
those rules.

!!! note "Output models can still validate themselves"
    A dataclass `__post_init__`, Pydantic model, or factory can still reject
    data. Talika reports that as an output failure because the table record had
    already parsed and validated successfully.

## Build Custom Output

Use `build_output()` when the public object is not a direct constructor call
from every parsed field.

Common reasons include:

- the factory needs parse context
- the output should omit table-only fields
- field names differ between the table schema and the public object
- the output object should be a dictionary, command object, or factory payload
- construction requires a service or helper supplied through context

```python title="A custom output builder"
--8<-- "docs_src/guides/advanced/output-models.py:custom-builder"
```

The builder receives a validated schema record and the parse context.

```python title="Building output with parse context"
--8<-- "docs_src/guides/advanced/output-models.py:custom-builder-call"
```

```text title="Custom output"
--8<-- "docs_src/guides/advanced/output-models.py:custom-builder-output"
```

This is often better than forcing the table fields to match a constructor
exactly. The schema can keep table labels readable, while `build_output()`
performs the small translation needed by the test setup.

!!! warning "Do not hide parsing rules in build_output"
    `build_output()` should convert a validated record into public output. Keep
    cell parsing in field parsers and record rules in validators so failures
    still point to the right table layer.

## Handle Output Construction Errors

If output construction raises an exception, Talika wraps it in a source-aware
`TableError` with `code=output_failed`.

```python title="An output model that rejects one record"
--8<-- "docs_src/guides/advanced/output-models.py:output-error"
```

```python title="Parsing a record rejected by the model"
--8<-- "docs_src/guides/advanced/output-models.py:output-error-call"
```

```text title="Output failure diagnostic"
--8<-- "docs_src/guides/advanced/output-models.py:output-error-result"
```

The diagnostic points to the record location because the failure happened
while building the public object for that record. For row tables, that usually
means the source row. For column tables, it usually means the item column and
item ID.

!!! tip "Use clear model errors"
    The exception message from the output constructor becomes part of the table
    diagnostic. Keep those messages useful for someone editing the authored
    table.

## Use Pydantic as a Normal Output Model

Pydantic models use the same output contract. The model is called with parsed
field values as keyword arguments.

```python title="A Pydantic output model"
--8<-- "docs_src/guides/advanced/output-models.py:pydantic-model"
```

```bash { .talika-terminal title="Pydantic output" .speed-3}
--8<-- "docs_src/guides/advanced/output-models.py:pydantic-output"
```

Talika does not need a separate parsing path for this. Pydantic receives the
already parsed values and performs its own model validation during output
construction.

Use this when your test code already speaks in Pydantic models. If Pydantic is
only being used to parse table strings, prefer Talika field parsers instead so
source-aware table diagnostics stay close to the authored cell.

!!! note "Pydantic is an output choice"
    A Pydantic model should represent the public object you want after table
    parsing. It does not replace schema fields, source-aware parsing, or table
    validation.

## Choose the Right Return Shape

Use schema records when the caller is still working with the table as a table:

- source-aware assertions
- custom diagnostics
- helper code that needs `source_for(...)`
- advanced validation or tooling
- type-checker-friendly schema instances

Use output models when the caller is ready to leave the table layer:

- domain dataclasses
- Pydantic models
- factory payloads
- application setup commands
- dictionaries for test helpers

The useful boundary is simple: parse table text into dependable schema records,
then convert those records into the object shape your test code actually wants.

!!! tip "Keep the table boundary explicit"
    A good output model makes the handoff obvious. Before conversion, the data
    still belongs to the authored table. After conversion, it belongs to the
    project code using the parsed result.
