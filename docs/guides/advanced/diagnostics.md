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

Use the raising APIs when invalid table data should fail immediately:

```python
records = UserTable.parse(datatable)
```

Use `validate()` when a tool, test, or editor needs a result value:

```python
result = UserTable.validate(datatable)

if result.valid:
    records = result.records
else:
    for diagnostic in result.errors:
        print(diagnostic.code, diagnostic.row, diagnostic.column)
```

The functional and pytest forms run the same lifecycle:

```python
from talika import validate_table

result = validate_table(UserTable, datatable, context={"locale": "en"})
result = talika.validate(datatable, schema=UserTable, context={"locale": "en"})
```

## Understand ValidationResult

`ValidationResult[RecordType]` is frozen and contains immutable tuples:

- `records` contains schema records only when the complete table is valid
- `diagnostics` contains errors and warnings in discovery order
- `errors` and `warnings` filter that tuple without reordering it
- `valid` is true when there are no error-severity diagnostics

Validation always uses safe collect semantics. It runs table transformation,
field parsing, defaults, IDs, variants, references, and record/table
validators. It deliberately skips output models and `build_output()`.

```python
result = UserTable.validate([["name", "age"], ["Alice", "bad"]])

assert not result.valid
assert result.records == ()
assert result.errors[0].code == "parser_failed"
```

Invalid results never expose partially parsed records. This prevents callers
from accidentally using records produced before a later field, reference, or
validator failed. Successful records remain mutable, matching `parse()`.

## Validation warnings

Validation hooks may raise a `TableError` with
`severity=DiagnosticSeverity.WARNING`. Warning-only validation remains valid
and keeps its complete records.

`validate()` returns warnings in `result.diagnostics` and `result.warnings`.
The raising APIs emit a public `TalikaWarning` through Python's warnings system
and still return their data. If warnings and errors coexist, warnings remain in
discovery order, no partial records are returned, and raising APIs emit the
warnings before raising the error failures.

Schema declaration errors and API misuse still raise. For example, an invalid
schema family raises `SchemaDefinitionError`, and an unsupported `error_mode`
raises `ValueError`; neither is authored table data.

## Read A Diagnostic

`Diagnostic` is a frozen, slotted value with `diagnostic_version = 1`.

```python
diagnostic = result.diagnostics[0]

print(diagnostic.code)          # parser_failed
print(diagnostic.severity)      # DiagnosticSeverity.ERROR
print(diagnostic.schema_name)   # UserTable
print(diagnostic.field_name)    # age
print(diagnostic.field_label)   # Age
print(diagnostic.source_uri)    # file:///.../users.feature, when known
print(diagnostic.row, diagnostic.column)
```

`field_name` identifies the Python declaration. `field_label` identifies the
authored canonical label or alias. An unknown authored label has no field name,
but is retained as the field label.

`source_value` is what the author wrote. `logical_value` is what a transformer
made available to later parsing. Both may be useful when compact syntax is
expanded or normalized.

```python
if diagnostic.has_source_value:
    print("authored:", diagnostic.source_value)
if diagnostic.has_logical_value:
    print("logical:", diagnostic.logical_value)
```

The `has_item_id`, `has_source_value`, and `has_logical_value` flags distinguish
an omitted value from a value explicitly set to `None`. The public value
property returns `None` in both cases, so inspect the presence flag when that
distinction matters.

`cause` retains the original exception for programmatic debugging. It is
excluded from equality and JSON because exceptions are not stable data.
`as_dict()` returns deterministic JSON-compatible Model v1 fields.

## Raising APIs Remain Compatible

`TableError`, `TableErrors`, and `SchemaDefinitionError` remain the exceptions
used by existing applications.

- `TableError.diagnostic` is the underlying immutable `Diagnostic`
- legacy properties such as `schema`, `field`, `value`, `code`, and coordinates
  remain available
- `TableErrors.errors` remains an immutable tuple of `TableError`
- `TableErrors.diagnostics` exposes the corresponding diagnostic tuple
- `SchemaDefinitionError.diagnostic` uses `code="schema_definition"`

Formatted exception strings may gain source and explicit field information.
Integrations should consume structured properties instead of parsing text.

## Raise Deliberate Project Diagnostics

At every user extension boundary, a deliberate `TableError`, `TableErrors`, or
`SchemaDefinitionError` passes through unchanged. This applies to parsers,
default factories, transformers, reference-key parsers, validators, and output
builders.

```python
from talika import TableError, field

def project_code(value, context):
    if not value.startswith("USR-"):
        raise TableError(
            "User code must start with USR-",
            code="project_user_code",
            schema=context.schema,
            field_name=context.field_name,
            field_label=context.field_label,
            source_uri=context.source_uri,
            row=context.row,
            column=context.column,
            source_value=context.source_value,
        )
    return value

code = field("Code", parser=project_code)
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

- Use `parse()` for raising validation that returns schema records.
- Use `parse_as()` for explicit or configured output conversion.
- Use `validate()` for non-raising tooling and complete-table acceptance.
- Use static checking for feature-file discovery plus `validate()`.
- Use CLI JSON when another process needs versioned deterministic data.

All of these entry points share the compiled schema and diagnostic lifecycle.
