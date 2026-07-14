---
icon: lucide/terminal
tags:
  - Static analysis
  - Feature files
  - CLI
  - Validation
---

# Static Checking

Static checking validates feature-file tables without running the pytest
scenario that owns them.

That is useful when table problems should be caught earlier: in CI, in a
pre-commit hook, in an editor integration, or in a documentation example that
should be checked like source code.

```gherkin title="A feature table with two table problems"
--8<-- "docs_src/guides/advanced/static-checking.py:feature"
```

This table has an empty required `name` cell and an `age` cell that cannot be
parsed as an integer.

```python title="A schema that can be used by tests and static checks"
--8<-- "docs_src/guides/advanced/static-checking.py:schema"
```

!!! note "Static does not mean shallow"
    Static checking does not merely inspect labels. It runs the schema parser,
    field parsers, record validators, table validators, references, defaults,
    and transformations. It deliberately uses `parse_records()`, so output
    models and custom `build_output()` hooks do not run during checking.

## Discover Feature Tables

The checker first finds Gherkin data tables that match your filters. Discovery
preserves feature-file coordinates, not just table-relative positions.

```python title="Finding matching data tables"
--8<-- "docs_src/guides/advanced/static-checking.py:discover-api"
```

```bash { .talika-terminal title="Discovered table metadata" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:discover-output"
```

The second row of the datatable is still row 6 in the feature file. That is the
coordinate an editor, CI log, or reviewer needs.

Scenario outlines are expanded with the official Gherkin compiler. Each
Examples row produces one logical `FeatureTable` and counts as one matched
table. Filters and returned metadata keep the original outline scenario and
step text. A cell that is exactly `<parameter>` points to the corresponding
Examples cell; a mixed template such as `user-<id>` keeps the template cell as
its source while exposing the compiled logical value.

!!! tip "Filter narrowly"
    Use `step` when one schema belongs to one step text. Use `scenario` when a
    file has several similar tables and you only want to check one scenario.

## Check with the Python API

Use `check_feature(...)` when Python code should discover and validate matching
tables in one call.

```python title="Checking a feature file"
--8<-- "docs_src/guides/advanced/static-checking.py:check-api"
```

Static checking uses collect mode, so one table can return several diagnostics.

```bash { .talika-terminal title="Collected checker diagnostics" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:check-output"
```

Each diagnostic keeps the feature file identity, scenario name, step text, and
the structured table error.

```python title="Returned checker object types"
--8<-- "docs_src/guides/advanced/static-checking.py:object-types"
```

```bash { .talika-terminal title="Feature table and diagnostic objects" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:object-types-output"
```

`FeatureTable` represents one discovered step datatable. `FeatureDiagnostic`
represents one table error attached back to the feature, scenario, and step
that produced it. These objects are useful when you are building a custom
checker, editor integration, or report generator and do not want to parse CLI
text.

```bash { .talika-terminal title="Readable table errors" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:error-output"
```

!!! warning "Your lifecycle code still runs"
    If a parser, validator, reference rule, or transformer normally talks to a
    service, reads a clock, or depends on random data, make
    the checking path deterministic. Static checking should be boring and
    repeatable.

## Check from the CLI

The `talika check` command is the same idea from a terminal. It discovers
matching feature tables, parses them with the schema, and prints diagnostics.

The CLI uses the optional Gherkin parser dependency, so install the `cli` extra
in environments that run feature-file checks.

```bash { .talika-terminal title="Validate a feature table" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:cli-command"
```

```bash { .talika-terminal title="Text diagnostics" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:cli-output"
```

The schema target is written as `module:SchemaClass`. Point it at a plain schema
module, not a pytest module that has to execute scenario decorators.

!!! tip "Keep schemas importable"
    A good CLI schema module only declares schemas, parsers, validators, and
    deterministic helpers. It should not need pytest fixtures or browser setup
    just to import.

## Emit JSON for Tools

Use JSON when another tool should consume the result.

```bash { .talika-terminal title="Validate with JSON output" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:json-command"
```

```bash { .talika-terminal title="Structured checker output" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:json-output"
```

The output is intentionally flat. Tools do not need to parse human text. They
can read `code`, `path`, `row`, `column`, `message`, `hint`, and `value`
directly.

## Pass Deterministic Context

Schemas often use parse context for project rules. The CLI can call a
zero-argument context factory and pass the returned mapping into parsing.

```python title="A context factory for checking"
--8<-- "docs_src/guides/advanced/static-checking.py:context-factory"
```

```bash { .talika-terminal title="Check with context" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:context-command"
```

Use this for stable lists, configuration flags, fake clocks, or lookup tables
that validators need while checking.

!!! warning "Avoid live dependencies in checking context"
    A checker that needs a database, external API, or non-deterministic service
    becomes slow and surprising. Prefer small in-memory data that represents
    the contract you want feature files to satisfy.

## Read Exit Codes

The CLI returns conventional exit codes:

- `0` when all matched tables are valid
- `1` when one or more matched tables have diagnostics
- `1` when setup or discovery fails, including missing/unreadable files,
  invalid Gherkin, schema-import failures, or context-factory failures
- `2` when the filters match no tables

Operational failures are concise and traceback-free in text mode. JSON mode
keeps the normal top-level shape with `status="failed"`, zero matched tables,
one error, and nullable table-specific diagnostic fields. Invalid command
syntax remains argparse exit code `2`.

When no tables match, the command prints:

```bash { .talika-terminal title="No matching tables" .speed-3}
--8<-- "docs_src/guides/advanced/static-checking.py:no-match-output"
```

That `2` exit code is deliberate. In CI, "we checked nothing" is usually a
different problem from "we checked tables and found validation failures."
