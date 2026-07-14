# Changelog

All notable changes to this project are documented here. Until the first
stable release, additions may refine APIs while preserving the documented
`0.1` behavior whenever practical.

## Unreleased

### Breaking parser correction

- Narrow the default `boolean()` vocabulary to `true` and `false`. Matching
  remains case-insensitive, while `yes/no`, `1/0`, and `on/off` now require
  explicit `true_values` and `false_values` declarations.
- Apply the same strict vocabulary to parsers inferred from `bool`
  annotations. Unknown tokens and whitespace-padded tokens continue to fail
  with `parser_failed` instead of falling back to Python truthiness.
- Reject bare-string token collections, non-string tokens, and non-Boolean
  `case_sensitive` values when `boolean()` is configured, instead of iterating
  or stringifying those values implicitly.

### Introspection and documentation

- Include the effective Boolean token sets and case-sensitivity policy in
  `Schema.describe()` and `talika describe` parser descriptions.
- Document explicit domain vocabularies, whitespace normalization through
  parser composition, annotation behavior, and the migration from the former
  convenience-token defaults.

!!! warning "Migration"
    A schema that intentionally accepts `yes/no`, `1/0`, or `on/off` should
    declare those tokens explicitly. For example:

    ```python
    boolean(true_values=("yes", "1", "on"),
            false_values=("no", "0", "off"))
    ```

## 0.3.0

Talika 0.3 compiles schema declarations into one immutable plan and moves
parsing stages behind a small public schema façade. It also introduces one
Diagnostic Model shared by runtime parsing, non-raising validation, static
checking, pytest-bdd, and the CLI without adding a new table language or
output feature.

### Breaking architecture corrections

- Freeze compiled field metadata, policies, lifecycle hooks, and schema
  registries; customize an existing schema through a subclass instead of
  mutating it after class creation.
- Make `__fields__` and `__variants__` read-only compatibility mappings and
  seal explicit variant registration after the schema family is first
  successfully finalized for parsing.
- Reject reserved field names, non-field shadowing, ambiguous inherited field
  names, and reuse of an already-bound field declaration.
- Report variant-family and reference-contract configuration failures as
  `SchemaDefinitionError` before table input is processed.

### Breaking diagnostic corrections

- Reserve `validate` as a framework schema name and reject fields with that
  Python attribute name during schema compilation.
- Preserve deliberate `TableError`, `TableErrors`, and
  `SchemaDefinitionError` instances raised by parsers, factories,
  transformers, reference-key parsers, validators, and output hooks instead
  of re-wrapping them.
- Allow formatted error strings to include source URI and explicit field/value
  information; integrations should consume structured diagnostic attributes.
- Make invalid non-raising validation results expose no partial records, and
  keep validation/checker paths independent from output conversion.

### Diagnostic Model v1 and validation APIs

- Add top-level `Diagnostic`, `DiagnosticSeverity`, `ValidationResult`, and
  `validate_table` exports plus `Schema.validate(...)` and
  `talika.validate(...)` fixture methods.
- Add immutable, presence-aware diagnostic values with source/logical values,
  field name and label, severity, deterministic `as_dict()`, and programmatic
  exception causes.
- Adapt `TableError`, `TableErrors`, `SchemaDefinitionError`, and
  `FeatureDiagnostic` to expose the shared model while preserving legacy
  attributes and raising APIs.
- Add the warning channel without reclassifying any existing behavior, and add
  `internal_error` for unexpected Talika lifecycle failures.

### Source and pytest-bdd improvements

- Add optional source URIs to tables, cells, parser/default contexts, record
  sources, and diagnostics; normalize filesystem paths to absolute file URIs.
- Preserve original authored and current logical cell values through
  transformations and carry source URIs through built-in transformers and
  transformer pipelines.
- Bind pytest-bdd feature paths and absolute cell coordinates to the exact
  datatable parsed through the instance-local `talika` fixture, including
  automatic cleanup after successful and failed steps.

### Checker and JSON compatibility

- Move static checking to `Schema.validate()`, include errors and warnings in
  discovery order, and continue skipping output construction.
- Version CLI JSON as `format_version=1`, add error/warning counts and every
  Diagnostic Model v1 field, and preserve legacy `path`, `schema`, `field`, and
  `value` aliases.
- Encode project values deterministically without arbitrary `repr()` fallback,
  preserve diagnostic-bearing schema/internal failures, and retain existing
  exit codes.

### Architecture and maintenance

- Add a private immutable `SchemaPlan` with normalized field, orientation,
  policy, hook, variant, and reference metadata.
- Split schema compilation, row and column traversal, reference resolution,
  validation, output conversion, and introspection away from the public
  `schema.py` façade.
- Replace runtime schema/MRO inspection with compiled plan indexes while
  retaining diagnostic order, source coordinates, and exception causes.
- Keep parsed record values mutable while preserving immutable record source
  metadata and extras.
- Assign explicit documented codes to Talika-owned table, transformation,
  identity, reference, validation, output, checker, and internal failures.
- Centralize lifecycle outcomes so raising parsing, collection, validation,
  checking, and CLI rendering consume the same diagnostics in the same order.

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
