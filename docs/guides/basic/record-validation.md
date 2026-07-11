---
icon: lucide/shield-check
tags:
  - Validation
  - Records
  - Parse context
  - Diagnostics
---

# Record Validation

Use `validate_record()` for rules that need one complete parsed record.

Field parsers answer "how should this cell become a Python value?" Record
validation answers "is this parsed record acceptable?" That difference matters.
A parser should not need to know every other field in the row. A record
validator can read `self.age`, `self.role`, `self.email`, defaults, references,
and parse-time context together.

```gherkin title="A user table with record rules"
--8<-- "docs_src/guides/basic/record-validation.py:feature-basic"
```

!!! tip "Use record validation after parsing"
    If a rule needs two or more fields from the same record, put it in
    `validate_record()`. If the rule only converts one cell, keep it as a
    parser.

## Add a Record Validator

Define `validate_record(self, context)` on the schema class. Talika calls it
after the record has been parsed and populated.

```python title="A row schema with record validation"
--8<-- "docs_src/guides/basic/record-validation.py:basic-contract"
```

This validator checks two record-level rules:

- a user must be at least 18
- a user role must be part of the allowed role set passed in parse context

```python title="Parsing valid records"
--8<-- "docs_src/guides/basic/record-validation.py:basic-parse"
```

```bash { .talika-terminal title="Validated records" .speed-3}
--8<-- "docs_src/guides/basic/record-validation.py:basic-output"
```

The values inside `validate_record()` are already parsed. `age` is an integer
because its field parser has run, and `role` is present even when it came from
a default.

!!! note "Validation returns None"
    A validator should return `None` when the record is valid. Raise an
    exception when the record is invalid.

## Validation Runs After Parsers and Defaults

Record validation happens after field parsing and default handling. That lets a
validator work with the same values your test code will see.

```python title="Validation sees parsed and defaulted values"
--8<-- "docs_src/guides/basic/record-validation.py:order-contract"
```

The table below omits `enabled`, so the default is applied before validation:

```python title="A valid score record"
--8<-- "docs_src/guides/basic/record-validation.py:order-parse"
```

```bash { .talika-terminal title="Validation order result" .speed-3}
--8<-- "docs_src/guides/basic/record-validation.py:order-output"
```

If the parsed score violates the context policy, the record validator raises:

```python title="A record that fails after parsing"
--8<-- "docs_src/guides/basic/record-validation.py:order-error"
```

```text title="Record validation diagnostic"
--8<-- "docs_src/guides/basic/record-validation.py:order-error-output"
```

!!! warning "Do not duplicate parser checks"
    Avoid re-parsing strings in `validate_record()`. If a field should be an
    integer, parse it as an integer on the field and let validation inspect the
    integer value.

## Use Parse Context for Runtime Policy

The `context` argument is a `ParseContext`. It carries the read-only
`user_data` mapping supplied to `parse(..., context={...})`.

That is useful when the rule changes by test environment, fixture, tenant,
scenario, or project configuration. In the user example, allowed roles are
runtime policy. The schema owns the rule shape, while the parse call supplies
the allowed set.

```python title="A role rejected by context policy"
--8<-- "docs_src/guides/basic/record-validation.py:role-error"
```

```text title="Context policy diagnostic"
--8<-- "docs_src/guides/basic/record-validation.py:role-error-output"
```

The error includes the record source row. It does not include a column because
ordinary `ValueError` from `validate_record()` describes the whole record, not
one specific field cell.

!!! tip "Pass policy, not mutable state"
    Prefer small context values such as allowed sets, limits, feature flags, or
    service handles. Keep the validator deterministic for the current parse
    call.

## Raise Ordinary Exceptions for Record-Level Errors

For rules that describe the whole record, raise a normal exception with a clear
message.

```python title="A user below the minimum age"
--8<-- "docs_src/guides/basic/record-validation.py:age-error"
```

```text title="Record-level validation failure"
--8<-- "docs_src/guides/basic/record-validation.py:age-error-output"
```

Talika wraps the exception as `record_validation_failed` and attaches the
record location. For row tables, that usually means the source row. For column
tables, that usually means the item column and item ID.

This is enough for many validation errors. A message such as `kai must be at
least 18` clearly describes the record-level problem, and the diagnostic points
to the row that needs attention.

!!! note "The original exception is preserved"
    Talika keeps the original exception as the cause. The user-facing
    diagnostic gets table context, while debugging can still inspect the
    underlying exception.

## Point at One Field Cell

Sometimes a record rule should point at a specific authored cell. For example,
an invalid email is a record rule because the check happens after parsing, but
the fix belongs to the `email` cell.

Use `self.source_for("field_name")` with `TableError.from_cell(...)`:

```python title="A source-aware record validator"
--8<-- "docs_src/guides/basic/record-validation.py:source-aware-contract"
```

```python title="An invalid email cell"
--8<-- "docs_src/guides/basic/record-validation.py:source-aware-error"
```

```text title="Source-aware validation diagnostic"
--8<-- "docs_src/guides/basic/record-validation.py:source-aware-error-output"
```

This diagnostic points to row 2, column 3, the exact cell that supplied
`email`. It also carries the original value and a hint for the table author.

!!! warning "source_for needs a source cell"
    `source_for("email")` only works when `email` came from the table. If the
    value came from a default for a missing field, there is no authored cell to
    point at.

## Defaults May Not Have Source Cells

Defaults are schema-owned values. When a field is missing and Talika supplies a
default, there is no table cell behind that value.

```python title="Trying to locate a defaulted field"
--8<-- "docs_src/guides/basic/record-validation.py:default-source-warning"
```

```text title="Missing source-cell diagnostic"
--8<-- "docs_src/guides/basic/record-validation.py:default-source-warning-output"
```

In real validators, check whether the problem belongs to a source cell before
calling `source_for(...)`. If the problem belongs to a defaulted value, raise a
record-level error instead.

!!! tip "Use the most helpful location"
    If one table cell caused the problem, use `TableError.from_cell(...)`. If
    the whole record is invalid, raise a normal exception and let Talika report
    the record location.

## Column Records

Record validation works the same way for `ColumnTable` schemas. The record is
one item column, and diagnostics identify the item column rather than a row.

```gherkin title="A column table with one invalid item"
--8<-- "docs_src/guides/basic/record-validation.py:column-feature"
```

```python title="Column record validation"
--8<-- "docs_src/guides/basic/record-validation.py:column-contract"
```

Here the rule is local to one content item: if the item is a poll, its headline
should be phrased as a question.

```python title="A column item that fails validation"
--8<-- "docs_src/guides/basic/record-validation.py:column-error"
```

```text title="Column validation diagnostic"
--8<-- "docs_src/guides/basic/record-validation.py:column-error-output"
```

The diagnostic includes `item_id='P-1'` and `column=3`, because the invalid
record is the third item column in the authored table.

## Conditional Fields Validation

Record validation is a good place for conditional field rules. These are rules
where one parsed value changes what another field means.

For example, a content item may allow an empty publication date while it is a
draft. Once the status becomes `Published`, the same empty cell is no longer
valid. A field parser cannot make that decision by looking at the publication
date alone; the rule needs the parsed status too.

```python title="Conditional field validation"
--8<-- "docs_src/guides/basic/record-validation.py:conditional-contract"
```

```python title="Parsing a record that violates the conditional rule"
--8<-- "docs_src/guides/basic/record-validation.py:conditional-parse"
```

```text title="Conditional validation error"
--8<-- "docs_src/guides/basic/record-validation.py:conditional-output"
```

The validator points to the empty publication date cell because that is the
cell the author should fix. The rule is about the relationship between two
fields, but the diagnostic should still land on the most actionable source
cell.

!!! tip "Point to the field that needs action"
    Conditional validation often reads two or three fields. When it fails,
    choose the source cell that the feature author should edit first.

## Keep Record Validation Local

Record validation should only inspect `self` and parse context. If a rule needs
to compare multiple records, such as duplicate emails or "at least one primary
user", it belongs in whole-table validation.

Good record-validation rules include:

- age must be at least 18 for this user
- a poll headline must end with a question mark
- an email cell must contain `@`
- a role must be allowed for this parse context
- a start date must be before an end date on the same record

Rules that usually do not belong in `validate_record()` include:

- no two records may share the same email
- at least one record must be primary
- every child record must refer to a parent record in another row
- totals across all records must balance

!!! tip "Validate at the smallest useful scope"
    Put single-cell syntax in parsers, one-record rules in
    `validate_record()`, and cross-record rules in table validation. That keeps
    failures easier to explain and easier to locate.
