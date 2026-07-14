# Contributing

## Development setup

The project uses Python 3.10 or newer and `uv` for reproducible environments:

```powershell
uv sync --all-extras --dev
uv run pytest -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests/typing/public_api.py
uv build
```

## Design principles

- Keep business actions and domain vocabulary outside the core package.
- Prefer small schema declarations over a general grammar framework.
- Preserve original feature-file locations through every transformation.
- Keep direct schema parsing independent from pytest and pytest-bdd.
- Make extension contracts explicit and test custom implementations.
- Add focused tests and documentation for every user-facing capability.
- Preserve missing-field versus explicitly-empty-cell behavior.

## Tests

Changes should include focused unit tests and, for user-facing behavior,
documentation under `docs/`. Test error messages through structured attributes
and stable codes where possible rather than relying only on complete strings.

## Parser architecture

Schema classes are compiled once into a private immutable plan. Keep module
dependencies flowing in this direction:

1. `schema_plan.py` and `engine_types.py` define immutable metadata and small
   runtime values.
2. `schema_compiler.py` collects declarations, resolves inheritance, infers
   supported annotations, and validates configuration.
3. `row_orientation.py`, `column_orientation.py`, `references.py`,
   `validation.py`, and `output.py` own their lifecycle stages and do not
   import the public schema façade.
4. `engine.py` coordinates shared parsing behavior.
5. `schema.py` only exposes the stable schema classes.

The runtime order is input normalization, transformation, orientation
traversal, field parsing and record construction, reference resolution,
validation, then optional output conversion. Preserve this order and existing
diagnostic ordering unless a release explicitly documents a correction.

## Diagnostic ownership

Every Talika-owned failure must use an explicit `TableErrorCode`; do not rely
on the project-facing `table_error` default. The module that owns a lifecycle
stage owns its diagnostic creation:

- table/orientation code owns boundary and shape diagnostics
- the engine owns field conversion, IDs, variants, and phase barriers
- `references.py`, `validation.py`, and `output.py` own their stage failures
- checker/CLI code owns discovery and operational failures
- only the outer lifecycle boundary converts an unexpected Talika exception
  to `internal_error`

Populate both compiled field name and authored label when a declared field is
known. Preserve source URI, original source value, current logical value, and
the original exception cause whenever available. Never use an arbitrary object
`repr()` as a stable message or JSON fallback.

Safe collection happens within phases. Structure/conversion failures stop
references; reference failures stop validation; validation failures stop
output. `validate()` and static checking always skip output. Add regression
tests before changing a phase barrier or diagnostic order.

Diagnostic Model v1 and CLI JSON v1 may gain additive fields or codes. Removing
a field, changing presence semantics, or changing a code's meaning requires a
new model/format version and an explicit compatibility decision. Deliberate
`TableError`, `TableErrors`, and `SchemaDefinitionError` values from project
hooks must pass through unchanged.

Every schema-definition or parser bug needs a regression test before its fix.
Avoid restoring runtime class inspection when the compiled plan already owns
the required metadata.

## Compatibility

The supported baseline is Python 3.10+, pytest 8+, and pytest-bdd 8+. CI checks
multiple Python and pytest releases. Deprecations should be documented before
removal, and the package version must be changed only as part of an explicit
release decision.
