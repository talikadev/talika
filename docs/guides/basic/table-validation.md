---
icon: lucide/list-checks
tags:
  - Validation
  - Data tables
  - Parse context
  - Table rules
---

# Table Validation

Use `validate_records()` for rules that need the whole parsed table.

Record validation checks one record at a time. Table validation checks the
collection: duplicates, required combinations, aggregate limits, ordering,
cross-record relationships, and policy that only makes sense after every record
has been parsed.

```gherkin title="A roster with a whole-table rule"
--8<-- "docs_src/guides/basic/table-validation.py:feature-basic"
```

!!! tip "Use the smallest useful validation scope"
    Put one-cell syntax in parsers, one-record rules in `validate_record()`,
    and cross-record rules in `validate_records()`. The smaller the scope, the
    easier the failure is to explain.

## Add a Table Validator

Define `validate_records(cls, records, context)` as a class method on the
schema. Talika calls it after records are parsed, after local references are
resolved, and after each record has passed `validate_record()`.

```python title="A row schema with table validation"
--8<-- "docs_src/guides/basic/table-validation.py:basic-contract"
```

This table validator checks three whole-table rules:

- no two records may share the same email
- at least one user must be marked primary
- every email must belong to the configured domain

```python title="Parsing a valid roster"
--8<-- "docs_src/guides/basic/table-validation.py:basic-parse"
```

```bash { .talika-terminal title="Validated table records" .speed-3}
--8<-- "docs_src/guides/basic/table-validation.py:basic-output"
```

The `records` argument contains parsed schema records. Field parsers and
defaults have already run, so `primary` is a boolean and `role` may come from a
default.

!!! note "The hook validates the collection"
    `validate_records()` should return `None` when the table is valid. Raise an
    exception when the collection is invalid.

## Use Parse Context for Table Policy

The `context` argument is the same parse context used by parsers, defaults, and
record validators. It carries read-only `user_data` from the parse call.

```python title="A table validator reading context"
--8<-- "docs_src/guides/basic/table-validation.py:context-contract"
```

```python title="Parsing with context"
--8<-- "docs_src/guides/basic/table-validation.py:context-parse"
```

```bash { .talika-terminal title="Context seen by table validation" .speed-3}
--8<-- "docs_src/guides/basic/table-validation.py:context-output"
```

Use context for policies that change by test setup: allowed domains, minimum
counts, publication limits, scenario mode, known external IDs, or service
objects used by validation.

!!! warning "Keep context explicit"
    Avoid reading mutable global state inside table validation. Passing policy
    through `parse(..., context={...})` makes the rule visible at the call site
    and keeps tests easier to reason about.

## Detect Duplicates with Source-Aware Errors

Duplicate checks are a common table-level rule. The validator must remember
what it has already seen, then report the later cell that introduced the
duplicate.

```python title="A duplicate email"
--8<-- "docs_src/guides/basic/table-validation.py:duplicate-error"
```

```text title="Duplicate diagnostic"
--8<-- "docs_src/guides/basic/table-validation.py:duplicate-error-output"
```

The diagnostic points to row 3, column 1, because that is the second occurrence
of the duplicate email. The first occurrence is useful for comparison, but the
second occurrence is the cell the author usually changes.

!!! tip "Point at the actionable cell"
    When a table-level rule can identify one offending cell, use
    `TableError.from_cell(...)` with `record.source_for("field_name")`. That
    gives the author a precise place to edit.

## Raise Plain Errors for Whole-Table Problems

Some table rules do not belong to one cell. For example, "at least one primary
user is required" is a property of the collection.

```python title="A table with no primary user"
--8<-- "docs_src/guides/basic/table-validation.py:primary-error"
```

```text title="Whole-table validation diagnostic"
--8<-- "docs_src/guides/basic/table-validation.py:primary-error-output"
```

Talika wraps ordinary exceptions as `table_validation_failed`. The diagnostic
names the schema, but it does not claim a row or column because no single cell
caused the problem.

```python title="A plain table validation exception"
--8<-- "docs_src/guides/basic/table-validation.py:plain-error"
```

```text title="Plain exception wrapper"
--8<-- "docs_src/guides/basic/table-validation.py:plain-error-output"
```

!!! note "Use ordinary exceptions for collection-level failures"
    If the problem is "the table as a whole does not satisfy this rule", raise
    a normal exception with a clear message. Let Talika wrap it as a table
    validation failure.

## Validate Policy Against Specific Cells

Sometimes a policy is table-wide but the failure still belongs to one cell. In
the roster example, the allowed email domain comes from parse context and
applies to every record. The failing value is still the `email` cell.

```python title="A domain policy failure"
--8<-- "docs_src/guides/basic/table-validation.py:domain-error"
```

```text title="Domain policy diagnostic"
--8<-- "docs_src/guides/basic/table-validation.py:domain-error-output"
```

This pattern is useful when a shared rule scans all records but can point to
the exact value that broke the rule. Use `TableError.from_cell(...)` for the
specific cell and keep the message focused on the policy.

!!! warning "Do not hide table policy inside parsers"
    A parser should not need to know every other record. If the rule needs the
    collection or a configured table policy, keep it in `validate_records()`.

## Column Table Validation

`validate_records()` works the same way for `ColumnTable`. The records are
still a sequence of parsed schema records, but each record came from an item
column.

```gherkin title="A column table with too many published items"
--8<-- "docs_src/guides/basic/table-validation.py:column-feature"
```

```python title="Column table aggregate rule"
--8<-- "docs_src/guides/basic/table-validation.py:column-contract"
```

This validator enforces a table-level publication limit. The rule needs all
records because one item being published is valid, but two published items
break the scenario policy.

```python title="A column table that breaks the limit"
--8<-- "docs_src/guides/basic/table-validation.py:column-error"
```

```text title="Column table validation diagnostic"
--8<-- "docs_src/guides/basic/table-validation.py:column-error-output"
```

The diagnostic points to the second published item. It includes both
`item_id='P-1'` and the source row/column for that item's `Publish` cell.

!!! note "Records are orientation-neutral"
    Inside `validate_records()`, row and column records are both normal schema
    records. The main difference is the source metadata attached to each
    record.

## Cross-Record Reference Checks

A common use case for whole-table validation is relational integrity between
records. For example, an organizational table may have a `manager id` field
that should point to another record's `user id`.

This is not a field parser problem. The `manager id` cell can be syntactically
valid and still refer to a user that does not exist. It is also not a
single-record validation problem, because one record cannot know every ID in
the table.

Because table validation runs after all records have been parsed, it can collect
the valid IDs first and then check every reference against that collection.

```python title="Validating references across records"
--8<-- "docs_src/guides/basic/table-validation.py:reference-contract"
```

```python title="Parsing a table with a broken reference"
--8<-- "docs_src/guides/basic/table-validation.py:reference-error"
```

```text title="Broken reference validation error"
--8<-- "docs_src/guides/basic/table-validation.py:reference-error-output"
```

The validator should point to the referencing cell, not the missing target. In
this example, the authored `manager id` is the value the feature author can
change, so the diagnostic belongs there.

!!! note "References can be checked before test setup"
    Whole-table validation lets you reject broken relationships before the test
    creates users, content, or other domain objects from the parsed records.

## Choose Table Validation Deliberately

Table validation is powerful because it can inspect everything. That also makes
it easy to put too much logic there. Keep it for rules that genuinely need the
collection.

Good table-validation rules include:

- no duplicate emails
- at least one primary user exists
- no more than one item is published in a scenario
- start and end rows form a complete set
- every record belongs to a configured domain
- totals across all rows balance

Rules that usually belong elsewhere include:

- one cell must parse as an integer
- one user's age must be at least 18
- one email must contain `@`
- one status token must be recognized
- one field should default when omitted

!!! tip "Make the failing scope match the rule"
    If the rule is about one cell, use a parser. If it is about one record, use
    record validation. If it is about the collection, use table validation.
