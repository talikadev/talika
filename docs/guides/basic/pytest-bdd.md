---
icon: lucide/clipboard-check
tags:
  - pytest-bdd
  - BDD
  - Data tables
  - Fixtures
  - Parsing
---

# pytest-bdd

Talika does not replace `pytest-bdd`. It parses the datatable that
`pytest-bdd` already passes to a step function.

That keeps the integration simple:

1. the feature file owns the authored Gherkin table
2. `pytest-bdd` passes that table to the step as `datatable`
3. Talika parses the datatable through your schema
4. the rest of the test uses parsed records or output objects

```gherkin title="A pytest-bdd scenario with a datatable"
--8<-- "docs_src/guides/basic/pytest-bdd.py:feature-basic"
```

!!! tip "Parse at the boundary"
    Parse the datatable in the step that receives it. After that point, pass
    parsed users, content records, or domain objects through fixtures and test
    helpers.

## Define the Schema Outside the Step

Keep the schema as ordinary Python code. The schema should be importable by
pytest, by helper modules, and by tooling that wants to inspect or validate
feature tables.

```python title="users_schema.py"
--8<-- "docs_src/guides/basic/pytest-bdd.py:schema"
```

This schema is not tied to `pytest-bdd`. It can parse any compatible datatable,
including the one received by a BDD step.

```python title="The raw datatable shape"
--8<-- "docs_src/guides/basic/pytest-bdd.py:raw-datatable"
```

The same schema can be used in unit tests, fixture setup, static checking, or
plain helper functions. `pytest-bdd` is only one place where the datatable
originates.

!!! note "Do not put schema declarations inside step functions"
    Step functions should describe test flow. Schema classes describe table
    contracts. Keeping them separate makes the schema reusable and easier to
    inspect.

## Parse Directly in a Step

The simplest integration is to call `UserTable.parse(datatable)` in the step
that receives the table.

```python title="Direct schema parsing in a step"
--8<-- "docs_src/guides/basic/pytest-bdd.py:direct-step"
```

The `target_fixture="users"` argument makes the parsed result available to
later steps as the `users` fixture.

```bash { .talika-terminal title="Parsed users fixture" .speed-3}
--8<-- "docs_src/guides/basic/pytest-bdd.py:direct-output"
```

This style is direct and explicit. It is often the clearest choice when the
step uses one schema and there is no need for an additional parser facade.

!!! warning "Keep raw datatables short-lived"
    A raw datatable is just nested strings. Parse it before handing data to the
    rest of the test so later code works with meaningful records.

## Use the `talika` Fixture

Talika registers a `talika` pytest fixture through the package's pytest plugin.
The fixture is a small facade around schema methods.

```python title="Parsing through the talika fixture"
--8<-- "docs_src/guides/basic/pytest-bdd.py:fixture-step"
```

This does the same parsing work as:

```python title="The equivalent direct call"
--8<-- "docs_src/guides/basic/pytest-bdd.py:fixture-equivalent"
```

The fixture does not create another schema registry or another parsing
lifecycle. It simply delegates to the schema passed with `schema=...`.

During a pytest-bdd step, the plugin binds the feature's absolute filename and
Gherkin cell coordinates to the exact raw `datatable` object. Calling
`talika.parse(...)`, `talika.parse_records(...)`, or `talika.validate(...)`
upgrades that object to source-aware `TableData`, then clears the binding after
the step succeeds or fails. Each fixture instance keeps its own binding, so
parallel tests do not share provenance.

!!! note "Direct schema calls cannot infer a feature filename"
    `UserTable.parse(datatable)` still parses correctly, but a raw nested list
    carries no pytest-bdd metadata. Use the `talika` fixture when diagnostics
    should automatically include the feature URI and absolute Gherkin cell
    coordinates. Scenario-outline runtime locations point to pytest-bdd's
    rendered template cell.

!!! tip "Use the fixture for dependency-injection style"
    Some teams prefer step functions where parsing always flows through a
    fixture argument. Use `talika.parse(...)` when that style makes your BDD
    steps more consistent.

## Pass Parse Context from Steps

Step functions are a natural place to pass scenario-specific project data into
Talika.

```python title="Passing context through the fixture"
--8<-- "docs_src/guides/basic/pytest-bdd.py:context-step"
```

The context mapping becomes `context.user_data` for parsers, default factories,
record validators, table validators, and output builders.

```bash { .talika-terminal title="Context-aware parsed result" .speed-3}
--8<-- "docs_src/guides/basic/pytest-bdd.py:context-output"
```

Use this for values that belong to the current scenario or test setup:
configured domains, allowed roles, generated prefixes, service handles, or
fixture-provided data.

!!! note "Context is copied into read-only user_data"
    Parser and validation code can read `context.user_data`, but should not
    mutate it. Treat it as parse-time configuration.

## Shared Parser Context Fixtures

Instead of defining parse-time context inside every step function, use ordinary
pytest fixtures for shared configuration.

This is a good fit for data that belongs to the test environment rather than to
one table: prefixes, allowed roles, fake service handles, validation thresholds,
or project lookup data. The step still decides when parsing happens, but the
fixture owns how the shared context is assembled.

```python title="Sharing parse context via fixtures"
--8<-- "docs_src/guides/basic/pytest-bdd.py:shared-context-step"
```

This pattern keeps step definitions focused on the authored table. It also
prevents small configuration dictionaries from being copied across many steps,
where they become hard to update consistently.

!!! note "Fixture context is still parse context"
    The fixture does not create a separate Talika mechanism. It simply returns
    a mapping that is passed as `context=...`, then read through
    `context.user_data` by parsers and validators.

## Choose `parse` or `parse_records`

Both schema methods and the `talika` fixture expose two parsing forms.

Use `parse(...)` when the step should receive the schema's public output. If
the schema has an `output_model` or custom output builder, `parse(...)` returns
those output objects.

Use `parse_records(...)` when the step specifically needs Talika schema
records, source metadata, `source_for(...)`, or type-checker-friendly schema
instances.

```python title="Schema records through the fixture"
--8<-- "docs_src/guides/basic/pytest-bdd.py:fixture-records-step"
```

The difference matters when a schema uses output conversion:

```python title="Output model conversion"
--8<-- "docs_src/guides/basic/pytest-bdd.py:output-model"
```

```bash { .talika-terminal title="parse vs parse_records" .speed-3}
--8<-- "docs_src/guides/basic/pytest-bdd.py:output-model-output"
```

!!! warning "Use records when you need source metadata"
    Output objects are often plain dataclasses or domain models. They may not
    carry Talika metadata. Use `parse_records(...)` when a step needs
    `table_source`, `source_for(...)`, or intermediate schema fields.

## Validate Without Raising

Use the fixture's `validate(...)` method when a step or helper needs structured
diagnostics instead of an exception:

```python
result = talika.validate(datatable, schema=UserTable)
assert result.valid, result.errors
```

Validation returns schema records only when the complete table is valid and
always skips output conversion. It preserves the same automatic pytest-bdd
source URI and cell coordinates as the fixture's parsing methods.

## Use the Functional API When Preferred

Some codebases prefer functions over schema classmethod calls. Talika provides
functional helpers for that style.

```python title="Functional parsing helpers"
--8<-- "docs_src/guides/basic/pytest-bdd.py:functional-api"
```

These helpers delegate to the same schema lifecycle:

- `parse_table(UserTable, datatable)` is equivalent to `UserTable.parse(datatable)`
- `parse_table_records(UserTable, datatable)` is equivalent to `UserTable.parse_records(datatable)`
- `validate_table(UserTable, datatable)` is equivalent to `UserTable.validate(datatable)`

They forward `context=...` and `error_mode=...` just like the schema methods.

!!! note "One lifecycle"
    Direct schema parsing, the `talika` fixture, and the functional API all
    call the same schema parser. Choose the calling style that makes the test
    easiest to read.

## Collect Multiple Table Errors

In normal mode, parsing stops at the first error. In `error_mode="collect"`,
Talika can report multiple independent table errors from the same parsing
phase.

```python title="Collect mode from a pytest-bdd step"
--8<-- "docs_src/guides/basic/pytest-bdd.py:collect-step"
```

The same behavior is available through direct schema parsing:

```python title="A datatable with two cell errors"
--8<-- "docs_src/guides/basic/pytest-bdd.py:collect-error"
```

```text title="Collected diagnostics"
--8<-- "docs_src/guides/basic/pytest-bdd.py:collect-error-output"
```

Collect mode is useful in tooling-like tests or CI checks where you want to see
several table problems at once. For ordinary test setup, fail-fast parsing is
often simpler.

!!! warning "Collect mode still respects lifecycle boundaries"
    Talika collects compatible errors from the same phase. It does not keep
    running dependent validation layers after structural parsing has already
    made the records unreliable.

## Keep Step Functions Focused

A good `pytest-bdd` step should usually do one of these things:

- receive a datatable and parse it into a fixture
- pass scenario context into parsing
- assert behavior using parsed records or output objects
- call application setup using parsed data

Avoid repeating table parsing logic across many steps. Once a schema exists,
let it own labels, parsers, defaults, validation, output conversion, and source
diagnostics.

!!! tip "Keep feature text and setup code close"
    The feature file should stay readable to the test author. The step should
    make the boundary clear: authored table in, dependable test objects out.
