---
icon: lucide/message-square-warning
tags:
  - Diagnostics
  - Validation
  - Error handling
  - Tooling
---

# Diagnostics And Validation Results

Talika uses one immutable diagnostic model for runtime parsing, non-raising
validation, static checking, pytest-bdd integration, and CLI JSON. This keeps a
failure's code, source location, field identity, and values consistent no
matter which entry point reports it.

Start with an ordinary feature table and schema. No diagnostic-specific schema
configuration is required.

```gherkin title="A table with an invalid age"
--8<-- "docs_src/guides/advanced/diagnostics.py:feature-users"
```

```python title="The table contract"
--8<-- "docs_src/guides/advanced/diagnostics.py:schema"
```

```python title="The Python datatable"
--8<-- "docs_src/guides/advanced/diagnostics.py:datatable"
```

## Choose Raising or Non-Raising Validation

Use the raising APIs when invalid table data should stop normal test setup. A
failed `parse()` call raises `TableError`, or `TableErrors` when collect mode
finds several independent failures.

```python title="Raise when the table is invalid"
--8<-- "docs_src/guides/advanced/diagnostics.py:raising-api"
```

Use `validate()` when a tool, test, or editor needs to inspect a result value
without catching authored-data exceptions:

```python title="Return a validation result"
--8<-- "docs_src/guides/advanced/diagnostics.py:validate-api"
```

```bash { .talika-terminal title="Inspecting an invalid result" .speed-3}
--8<-- "docs_src/guides/advanced/diagnostics.py:validation-output"
```

The functional and pytest-bdd forms run the same lifecycle. They are useful
when a project prefers dependency injection or explicit function calls:

```python title="Equivalent validation entry points"
--8<-- "docs_src/guides/advanced/diagnostics.py:functional-api"
```

!!! tip "Choose the API at the call site"
    A schema does not need separate raising and non-raising versions. Use
    `parse()` in ordinary setup code and `validate()` where diagnostics are
    data that another tool or assertion needs to inspect.

## Understand ValidationResult

`ValidationResult[RecordType]` is frozen and contains immutable tuples:

- `records` contains schema records only when the complete table is valid
- `diagnostics` contains errors and warnings in discovery order
- `errors` and `warnings` filter that tuple without reordering it
- `valid` is true when there are no error-severity diagnostics

Validation always uses safe collect semantics. It runs table transformation,
field parsing, defaults, IDs, variants, references, and record/table
validators. It deliberately skips output models and `build_output()`.

```python title="An invalid result never contains partial records"
--8<-- "docs_src/guides/advanced/diagnostics.py:invalid-result"
```

Invalid results never expose partially parsed records. This prevents callers
from accidentally using records produced before a later field, reference, or
validator failed. Successful records remain mutable, matching `parse()`.

!!! note "Declaration and API errors still raise"
    `validate()` handles authored table-data diagnostics without raising.
    Invalid schema families, unsupported `error_mode` values, and other API
    misuse still raise because they cannot be represented as a table result.

## Keep Warnings Without Invalidating Records

Validation hooks may raise a `TableError` with
`severity=DiagnosticSeverity.WARNING`. Warning-only validation remains valid
and keeps its complete records.

```python title="A record validator that reports a warning"
--8<-- "docs_src/guides/advanced/diagnostics.py:warning-schema"
```

```python title="Validate a warning-only table"
--8<-- "docs_src/guides/advanced/diagnostics.py:warning-validate"
```

```bash { .talika-terminal title="A valid result with one warning" .speed-3}
--8<-- "docs_src/guides/advanced/diagnostics.py:warning-output"
```

`validate()` returns warnings in `result.diagnostics` and `result.warnings`.
The raising APIs emit a public `TalikaWarning` through Python's warnings system
and still return their data. If warnings and errors coexist, warnings remain in
discovery order, no partial records are returned, and raising APIs emit the
warnings before raising the error failures.

!!! warning "Warnings belong to validation"
    A parser, default factory, or transformer must produce a value for later
    lifecycle stages. Failures at those value-producing boundaries remain
    errors even if a project-created `TableError` requests warning severity.

## Read a Diagnostic

`Diagnostic` is a frozen, slotted value with `diagnostic_version = 1`.

```python title="Select stable diagnostic fields"
--8<-- "docs_src/guides/advanced/diagnostics.py:inspect-diagnostic"
```

```bash { .talika-terminal title="Structured parser diagnostic" .speed-3}
--8<-- "docs_src/guides/advanced/diagnostics.py:diagnostic-output"
```

`field_name` identifies the Python declaration. `field_label` identifies the
authored canonical label or alias. An unknown authored label has no field name,
but is retained as the field label.

`source_value` is what the author wrote. `logical_value` is what a transformer
made available to later parsing. Both may be useful when compact syntax is
expanded or normalized.

```python title="Distinguish omitted values from explicit None"
--8<-- "docs_src/guides/advanced/diagnostics.py:presence-flags"
```

The `has_item_id`, `has_source_value`, and `has_logical_value` flags distinguish
an omitted value from a value explicitly set to `None`. The public value
property returns `None` in both cases, so inspect the presence flag when that
distinction matters.

`cause` retains the original exception for programmatic debugging. It is
excluded from equality and JSON because exceptions are not stable data.
`as_dict()` returns deterministic JSON-compatible Model v1 fields.

!!! note "Use structured data in integrations"
    Human-readable exception text may improve over time. Test runners, editor
    integrations, and other tools should use diagnostic attributes or
    `as_dict()` instead of parsing formatted messages.

## Keep Raising APIs Compatible

`TableError`, `TableErrors`, and `SchemaDefinitionError` remain the exceptions
used by existing applications. The shared diagnostic model sits underneath
these exceptions; adopting structured diagnostics does not require rewriting
normal fail-fast parsing code.

- `TableError.diagnostic` is the underlying immutable `Diagnostic`
- legacy properties such as `schema`, `field`, `value`, `code`, and coordinates
  remain available
- `TableErrors.errors` remains an immutable tuple of `TableError`
- `TableErrors.diagnostics` exposes the corresponding diagnostic tuple
- `SchemaDefinitionError.diagnostic` uses `code="schema_definition"`

Formatted exception strings may gain source and explicit field information.
Integrations should consume structured properties instead of parsing text.
Application code can continue catching the public exception types, while
tooling reads their `diagnostic` or `diagnostics` properties.

## Raise Deliberate Project Diagnostics

At every user extension boundary, a deliberate `TableError`, `TableErrors`, or
`SchemaDefinitionError` passes through unchanged. This applies to parsers,
default factories, transformers, reference-key parsers, validators, and output
builders.

```python title="A project-owned parser diagnostic"
--8<-- "docs_src/guides/advanced/diagnostics.py:project-diagnostic"
```

Raise an ordinary exception when Talika should classify the extension point:
parser exceptions become `parser_failed`, default-factory exceptions become
`default_factory_failed`, and so on. The wrapper retains the original cause.

Unexpected exceptions escaping Talika's own lifecycle become `internal_error`
with a bug-report hint. Control-flow exceptions such as `KeyboardInterrupt` and
`SystemExit` are never intercepted.

## Respect Lifecycle Barriers

Diagnostics remain in discovery order; Talika does not sort them. It collects
independent failures within a safe phase, then stops before dependent work:

1. schema finalization and context normalization
2. raw table validation and transformation
3. shape, labels, variants, fields, and IDs
4. reference indexing and resolution
5. record and whole-table validation
6. output conversion for `parse_as()` only

Structure or conversion errors stop references and validation. Reference
errors stop validators and output. Validation errors stop output. These
barriers avoid secondary diagnostics produced from incomplete data.

## Diagnostic Code Catalog

Talika-owned failures always use an explicit code. `table_error` is reserved as
the default for project-created `TableError` values.

| Code | Lifecycle owner | Meaning |
| --- | --- | --- |
| `table_error` | Project extensions | Default code for a user-created custom error. |
| `schema_definition` | Schema compiler/family finalization | A schema declaration, inheritance contract, variant family, or reference contract is invalid. |
| `invalid_context` | Context normalization | The supplied parse context cannot be normalized. |
| `invalid_table_input` | Table boundary | Raw rows, cells, coordinates, or `TableData` are malformed. |
| `table_empty` | Table boundary/transformation | A table or grouped table has no usable cells. |
| `header_empty` | Orientation | A required row or column header is blank. |
| `ragged_row` | Orientation/transformation | Rows do not form the required rectangular shape. |
| `duplicate_label` | Label validation | A label or canonical-label/alias combination appears more than once. |
| `unknown_field` | Label validation | Authored text names a field the schema does not accept. |
| `missing_required` | Field conversion | A required field is absent. |
| `empty_required` | Field conversion | A required authored cell is blank. |
| `empty_optional` | Field conversion | An optional cell violates its empty-value policy. |
| `default_factory_failed` | Field conversion | A default factory raised a non-Talika exception. |
| `parser_failed` | Field conversion | A field parser raised a non-Talika exception. |
| `transform_failed` | Transformation | A table transformer or range/repeat rule raised unexpectedly. |
| `invalid_transform` | Transformation | A transformer or compact expansion returned an invalid structure. |
| `expansion_limit` | Group expansion | Numeric expansion would create more than 10,000 keys. |
| `unknown_variant` | Variant selection | A discriminator value has no registered variant. |
| `inapplicable_field` | Variant selection | Authored data populates a field unavailable on the selected variant. |
| `duplicate_id` | Identity | Two parsed records use the same ID. |
| `invalid_id` | Identity/orientation | An ID is unhashable or a column ID row has an invalid layout. |
| `reference_failed` | References | Target indexing, key conversion, uniqueness, or lookup failed. |
| `record_validation_failed` | Validation | A record validator raised a non-Talika exception. |
| `table_validation_failed` | Validation | A whole-table validator raised a non-Talika exception. |
| `output_failed` | Output conversion | An output model or custom builder rejected a valid record. |
| `checker_failed` | Static checker/CLI | Feature discovery, import, Gherkin, or context setup failed operationally. |
| `internal_error` | Lifecycle boundary | An unexpected Talika implementation failure escaped its owning stage. |

Code meanings are part of Diagnostic Model v1. New fields and codes may be
added compatibly; removing a field or changing a code's meaning requires a new
diagnostic or format version.

## Choose An API

Choose the narrowest return type the caller needs. Runtime setup usually wants
records or output objects immediately, while checkers and editor integrations
need diagnostics they can retain, filter, and serialize.

- Use `parse()` for raising validation that returns schema records.
- Use `parse_as()` for explicit or configured output conversion.
- Use `validate()` for non-raising tooling and complete-table acceptance.
- Use static checking for feature-file discovery plus `validate()`.
- Use CLI JSON when another process needs versioned deterministic data.

All of these entry points share the compiled schema and diagnostic lifecycle.

!!! tip "Keep one schema contract"
    Switching entry points changes how results are delivered, not what the
    table means. Reuse the same schema for runtime parsing, non-raising checks,
    pytest-bdd steps, and CLI validation.
