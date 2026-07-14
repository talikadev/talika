---
icon: lucide/file-json
tags:
  - Schemas
  - Introspection
  - Contracts
  - Metadata
---

# Schema Contracts

`describe()` lets tools inspect a schema without parsing a table.

That is different from validation. Validation asks, "Does this authored table
fit the schema?" A schema contract asks, "What does this schema expect?"

```python title="A schema with fields, aliases, defaults, and variants"
--8<-- "docs_src/guides/advanced/schema-contracts.py:schema"
```

This schema can parse tables, but it can also describe itself.

```python title="Reading a schema contract"
--8<-- "docs_src/guides/advanced/schema-contracts.py:describe"
```

`describe()` returns a frozen `TableContract`. It is safe to cache, compare,
serialize, or use as input for documentation and editor tooling.

Talika builds this contract from the same immutable compiled schema plan used
by parsing. Description therefore does not re-walk the class hierarchy or
reinterpret mutable class attributes. The compiled plan itself is private;
`TableContract` remains the supported introspection API.

!!! tip "Use contracts for tooling"
    A schema contract is metadata. It does not parse cells, run validators, hit
    references, or build output objects. It tells tools what the schema has
    declared.

## Inspect Table Identity

The contract starts with the table-level shape and policies.

```bash { .talika-terminal title="Schema identity and policies" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:identity-output"
```

`orientation` is `row` or `column`. The policies show how the schema treats
unknown table labels and fields that belong to a different selected variant.

!!! note "Contracts describe configuration"
    The contract records configured policies such as `unknown_fields` and
    `inapplicable_fields`. It does not know whether a particular feature table
    contains unknown or inapplicable fields.

## Inspect Fields

Each declared field becomes a `FieldContract`.

```bash { .talika-terminal title="Field summary" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:fields-output"
```

Field contracts include the Python attribute name, authored table label,
aliases, required flag, ID/discriminator flags, default information, parser
name, reference target, and empty-cell policy.

```bash { .talika-terminal title="One field as a dictionary" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:field-dict-output"
```

Use `as_dict()` when a tool wants ordinary containers instead of dataclass
objects.

!!! warning "Callable names are display names"
    Parser, default factory, transformer, output model, and output builder names
    are meant for display and diagnostics. Do not treat them as import paths.

## Inspect Variants

Discriminator variants appear in the same contract.

```bash { .talika-terminal title="Variant contracts" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:variants-output"
```

Each item in `contract.variants` is a `VariantContract`. It includes the
discriminator value, generated schema name, active fields, output model name,
and output builder name.

```bash { .talika-terminal title="A variant-specific field" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:variant-field-output"
```

This is useful for generated docs that need to show which fields apply to
`Article`, which fields apply to `Poll`, and which fields are shared.

!!! example "A good contract table"
    A generated schema page can list required labels, aliases, defaults, parser
    names, and variant-only fields without needing an example feature file.

## Inspect Configured Hooks

Contracts also name configured hooks such as table transformers and output
models.

```python title="A schema with transformer and output hooks"
--8<-- "docs_src/guides/advanced/schema-contracts.py:hook-schema"
```

```bash { .talika-terminal title="Hook metadata" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:hook-output"
```

This is enough for a tool to say, "This schema uses a grouped-column
transformer and builds `ContentItem` objects", without importing private
implementation details.

## Use CLI Describe

The CLI exposes the same contract for terminal workflows. This is useful when
you want to inspect a schema outside Python, generate documentation in a build
step, or compare schema metadata in CI.

The command imports the schema target and renders `describe()` output. Like
`talika check`, the schema target should be an importable module path such as
`app.schemas:ContentTable`.

```bash { .talika-terminal title="Describe a schema" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:cli-text-command"
```

```bash { .talika-terminal title="Human-readable contract" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:cli-text-output"
```

Use JSON output when another tool should consume the contract:

```bash { .talika-terminal title="Describe a schema as JSON" .speed-3}
--8<-- "docs_src/guides/advanced/schema-contracts.py:cli-json-command"
```

The JSON shape is the same information as `ContentTable.describe().as_dict()`.

!!! tip "Use text for humans and JSON for tools"
    Text output is meant for quick inspection. JSON output is better for schema
    drift checks, generated pages, and editor integrations.

## Use Contracts Carefully

Schema contracts are useful for:

- generated reference pages
- editor completions for table labels
- schema drift checks in CI
- comparing required labels across versions
- documenting variants and aliases for feature authors

They are not a replacement for parsing real tables. A contract can tell you
that `Headline` is required. Static checking or normal parsing tells you
whether a specific feature table actually provided it.
