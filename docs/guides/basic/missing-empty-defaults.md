---
icon: lucide/eraser
---

# Missing, Empty, Defaults

Talika treats three cases differently:

- a field is missing because its label is not in the table
- a field is present, but one cell is explicitly empty
- a field is absent and the schema supplies a default

Those cases look similar when a test fails, but they mean different things to
the person editing the feature file. A missing label is a table-shape choice. A
blank cell is authored data. A default is schema-owned data.

```gherkin title="A table with omitted optional fields"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:feature-missing"
```

!!! tip "First ask whether the label exists"
    Before thinking about defaults or empty strings, ask whether the field label
    appears in the table at all. Talika's behavior starts from that boundary.

## The Field Parsing Lifecycle

Whenever Talika processes a field in a BDD table, it evaluates the presence of the field label, default configurations, empty policies, parsers, and validators in a strict, predictable sequence:

1. **Label Presence Check**: Talika checks if the field's canonical label or any of its declared aliases appear in the table header for row tables, or in the field-label column for column tables.
    - *If absent*: Talika looks for a `default_factory`, then a `default`. If neither is declared, the field becomes `None`.
    - *If present*: Talika proceeds to the cell evaluation step.
2. **Empty Value Check**: If the field is present, Talika inspects the cell text.
    - *If non-empty*: Talika runs the field parser when one is declared. If there is no parser, the text is returned as-is.
    - *If empty*: Talika evaluates the field's `empty` policy (`raw`, `none`, `parse`, or `error`). If `empty="parse"`, it passes the blank string to the parser. Otherwise, it sets the value based on the policy or raises a `TableError` if `empty="error"` or the field is required.
3. **Record-Level Validation**: Once field values have been parsed, defaulted, or preserved as text, Talika runs `validate_record(self, context)` on each record.
4. **Table-Level Validation**: Once all individual records have successfully passed record validation, Talika runs `validate_records(cls, records, context)` to validate relationships across the entire collection.

## Missing Optional Fields

A field is missing when none of its accepted labels appear in the table. In a
row table, that means the header is absent. In a column table, that means the
field row is absent.

```python title="Optional fields with defaults"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:defaults-contract"
```

This schema has four fields:

- `username` is required.
- `role` is optional and has a static default.
- `team` is optional and has a context-aware default factory.
- `notes` is optional and has no default.

When the table only provides `username`, Talika fills the missing optional
fields:

```python title="Parsing a table with missing optional fields"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:missing-parse"
```

```bash { .talika-terminal title="Missing optional field result" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:missing-output"
```

The fallback order is direct:

- if `default_factory` is declared, call it
- otherwise, if `default` is declared, use it
- otherwise, return `None`

!!! note "Defaults run only for absent fields"
    Defaults do not run because a cell is blank. They run because the field is
    not present in the table.

## Empty Cells Are Present Values

Now compare the same schema with a table that includes every label but leaves
some cells empty.

```python title="Parsing explicit empty cells"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-present"
```

```bash { .talika-terminal title="Empty cells are present" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-present-output"
```

The `role` default is not used. The `team` factory is not called. The `notes`
field does not become `None`. Each field exists in the authored table, so the
blank cell is treated as an explicit value.

This distinction is the main thing to remember. A blank cell can be deliberate:
it may mean "clear this value", "leave this optional text empty", or "this
field is intentionally blank for this record." Talika does not silently replace
that author choice with a default.

!!! warning "Do not use defaults as blank-cell cleanup"
    If a blank cell should become `None`, be parsed, or be rejected, configure
    the field's empty-cell policy. A default is not a cleanup rule for visible
    blank cells.

## Missing and Empty Required Fields

Required fields add two checks:

1. the field label must be present
2. the value must not be empty by default

When the required label is absent, Talika reports a missing required field:

```python title="Missing required label"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:missing-required"
```

```text title="Missing required label diagnostic"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:missing-required-output"
```

When the label is present but the cell is blank, Talika reports the source cell:

```python title="Empty required cell"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-required"
```

```text title="Empty required cell diagnostic"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-required-output"
```

These diagnostics intentionally point to different fixes. For a missing label,
the author adds a column or row. For an empty cell, the author fills the cell or
the schema changes what blank means.

!!! tip "Use required for scenario meaning"
    Make a field required when the scenario would be unclear without it. Do not
    use `required=True` just to get a Python type. Use parsers and validation
    for conversion and business rules.

## Default Factories

Use `default_factory` when the fallback value depends on the parse operation.
The factory receives a `DefaultContext`, not a cell context, because there is
no source cell for a missing field.

```python title="A row ID used by a default factory"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:row-factory-contract"
```

```python title="Parsing a missing field with an item-aware default"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:row-factory-parse"
```

```bash { .talika-terminal title="Default factory result" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:row-factory-output"
```

The factory can read:

- `context.schema`
- `context.field_name`
- `context.field_label`
- `context.item_id`
- `context.user_data`

There is no `row`, `column`, or `source_value`, because the field was absent.

!!! note "Default factories are not parsers"
    A parser converts a present cell. A default factory creates a value when
    the field is missing. Keep those responsibilities separate.

## Defaults in Column Tables

In column tables, a missing optional row applies to each item column. If the
field has a default factory, the factory runs once per item and receives that
item's ID.

```gherkin title="A column table with one missing row and one blank cell"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:column-feature"
```

```python title="Column defaults"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:column-contract"
```

The `Headline` row is absent, so `headline` is generated for both `A-1` and
`P-1`. The `Status` row is present. `A-1` has `draft`, and `P-1` has an
explicit empty cell.

```python title="Parsing column defaults and empty cells"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:column-parse"
```

```bash { .talika-terminal title="Column default result" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:column-output"
```

This is the same rule as row tables, just turned sideways. Missing row means
the field is absent. Empty item cell means the field is present for that item
with a blank value.

!!! warning "A missing row and a blank item cell are not interchangeable"
    Removing the `Status` row would make every item's status `None` by default.
    Keeping the row and leaving one item blank makes only that item hold an
    explicit empty value.

## Empty-Cell Policies

Optional fields can choose what an explicit blank cell means.

```python title="Field policies for explicit empty cells"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-policies-contract"
```

The policies are:

- `empty="raw"` preserves `""`
- `empty="parse"` sends `""` to the parser
- `empty="none"` returns `None`
- `empty="error"` rejects `""`

```python title="Parsing empty cells with policies"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-policies-parse"
```

```bash { .talika-terminal title="Empty policy result" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-policies-output"
```

In this example, `strict_value` is absent from the table, so it is `None`. When
the `strict value` label is present and its cell is blank, Talika rejects it:

```python title="A strict optional field"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-optional-error"
```

```text title="Strict optional diagnostic"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:empty-optional-error-output"
```

!!! example "Choosing a policy"
    Use `raw` when blank text is acceptable, `none` when blank means no value,
    `parse` when your parser owns blank syntax, and `error` when the field may
    be omitted but must not be written blank.

## Required Fields and Empty Parsing

By default, a required field rejects an explicit empty cell. There is one
important exception: if the field explicitly allows empty parsing, the parser
can decide what the blank means.

```python title="A required field that parses an empty cell"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:required-parse-empty"
```

```bash { .talika-terminal title="Required empty parsed by the field" .speed-3}
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:required-parse-empty-output"
```

This should be rare. Use it when an empty string is a real authored syntax for
the field, not as a way to hide incomplete required data.

!!! warning "Be deliberate with required blank parsing"
    Most required fields should reject blank cells. If a required field parses
    blanks, document that table vocabulary clearly in the schema or surrounding
    tests.

## Default Errors and Invalid Declarations

If a default factory fails, Talika reports a default-factory diagnostic. The
error is tied to the field, but there is no row or column because the field was
missing.

```python title="A default factory that fails"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:default-factory-error"
```

```text title="Default factory diagnostic"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:default-factory-error-output"
```

Some field declarations are invalid before parsing starts. A field cannot
declare both a static default and a default factory. A required field cannot
declare a default, because that would make missing required data appear valid.

```python title="Invalid default declarations"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:invalid-defaults"
```

```text title="Invalid default declaration errors"
--8<-- "docs_src/guides/basic/missing-empty-defaults.py:invalid-defaults-output"
```

!!! tip "Keep defaults boring"
    Defaults are easiest to maintain when they are predictable. Use static
    defaults for stable values, factories for context-aware values, and
    validation for rules that need to inspect the completed record.
