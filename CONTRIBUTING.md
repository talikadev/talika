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
- Add focused executable examples for every user-facing capability.
- Preserve missing-field versus explicitly-empty-cell behavior.

## Tests

Changes should include focused unit tests and, for user-facing behavior, an
example under `examples/`. Test error messages through structured attributes
and stable codes where possible rather than relying only on complete strings.

## Compatibility

The supported baseline is Python 3.10+, pytest 8+, and pytest-bdd 8+. CI checks
multiple Python and pytest releases. Deprecations should be documented before
removal, and the package version must be changed only as part of an explicit
release decision.
