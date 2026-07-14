# Changelog

All notable changes to this project are documented here. Until the first
stable release, additions may refine APIs while preserving the documented
`0.1` behavior whenever practical.

## 0.2.0

Talika 0.2.0 is a stabilization release. It tightens existing parsing,
identity, reference, checking, and packaging behavior without adding a new
table language or rendering layer.

### Breaking stabilization changes

- Reject malformed raw tables, invalid source cells, invalid field options,
  mutable or unhashable static defaults, and `empty="parse"` without a parser
  at their public boundaries.
- Require zero or one ID field on row schemas and exactly one on column
  schemas during class creation; require parsed IDs to be hashable and unique
  in both orientations.
- Treat defaults and default-factory results as final Python values rather
  than sending them through field parsers.
- Make static checking call `parse_records()`, so parsing, transformations,
  defaults, references, and validation still run while output models and
  custom output builders do not.
- Expand scenario outlines once per Examples row using the official Gherkin
  compiler and reject numeric expansions above 10,000 generated keys.

### Bug fixes and hardening

- Isolate annotation inference per field so an unresolved postponed
  annotation cannot disable supported inference elsewhere in a schema.
- Validate reference target availability, hashability, uniqueness, and
  family-wide parser compatibility; collect independent reference failures in
  deterministic order and stop dependent validation/output stages.
- Convert feature discovery, Gherkin parsing, schema import, and context
  factory failures into controlled checker diagnostics and exit code 1.
- Add pull-request CI, line-and-branch coverage enforcement, dependency-bound
  test jobs, strict documentation builds, and wheel/sdist smoke tests.

## 0.1.1

This documentation and release-tooling update makes Talika easier to discover,
understand, and publish while keeping the package API unchanged.

### Documentation

- Redesign the project README as a concise introduction with branding, package
  badges, a Gherkin-to-Python quickstart, key features, and clear paths into the
  full documentation.
- Standardize on **Gherkin data table** throughout package metadata,
  documentation, and public API descriptions.
- Improve the documentation site's light theme and simplify page metadata.

### Release tooling

- Add a manual trusted-publishing workflow that retrieves verified wheel and
  source distributions from a GitHub Release before publishing them to PyPI.

## 0.1.0

The first public alpha release of Talika introduces typed, validated contracts
for Gherkin data tables without imposing a project-specific table vocabulary.

### Schemas and fields

- Parse both row-oriented and column-oriented data tables into typed schema records.
- Declare required, optional, aliased, and identifier fields with static or context-aware defaults.
- Infer converters from scalar, optional, enum, and string-literal type annotations.
- Control empty cells independently from missing fields with preserve, parse, null, and forbid policies.
- Compose reusable field groups and discriminated variants for tables containing multiple record shapes.
- Resolve single and multi-value references between records, including identifiers with custom parsers.

### Parsing and extension points

- Convert cells with built-in string, integer, float, decimal, boolean, choice, mapping, split, optional, compose, and collection parsers.
- Build project-owned cell languages from scoped tokens, regular-expression patterns, predicates, fallbacks, and composable `CellDSL` instances.
- Transform tables before parsing with custom hooks or left-to-right transformer pipelines while preserving original source locations.
- Expand compact column groups with numeric or alphabetic ranges and configurable prefix or suffix repetition rules.
- Return schema records, dataclasses, Pydantic models, keyword-constructed classes, or objects produced by custom output builders.

### Validation and diagnostics

- Validate individual records and complete record collections after conversion, defaults, variants, and references are resolved.
- Report table shape, field, parser, transformation, reference, validation, and output errors with stable codes and source coordinates.
- Choose fail-fast behavior or collect independent failures into an ordered `TableErrors` aggregate.
- Inspect immutable record and field source metadata, including row, column, item identifier, and original transformed cells.

### Integrations and tooling

- Parse tables in pytest-bdd steps through the registered `talika` fixture or the functional parsing API.
- Discover and statically validate Gherkin data tables through the Python checker API or the `talika check` command.
- Emit human-readable or JSON checker diagnostics and supply deterministic project context through CLI context factories.
- Inspect complete field and variant contracts through `describe()`, `talika describe`, or JSON output.
- Ship a dependency-free typed core for Python 3.10 through 3.13 with optional CLI, Pydantic, and testing extras.
