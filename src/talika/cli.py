"""Command-line interface for static Gherkin data table validation.

The CLI exposes two operations: ``check`` validates Gherkin data tables against
a schema without executing pytest scenarios, and ``describe`` renders a schema
contract for humans or tools.

!!! info
    The public console script and ``python -m talika`` both delegate to
    ``main()`` in this module.
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .checker import FeatureDiagnostic, check_feature_tables, discover_feature_tables
from .diagnostics import Diagnostic, DiagnosticSeverity, stable_json_value
from .errors import SchemaDefinitionError, TableError, TableErrorCode
from .schema import BaseTable


def _import_object(reference: str) -> Any:
    """Import a ``module:attribute`` or ``path.py:attribute`` reference.

    Args:
        reference: Import reference supplied by the CLI user.

    Returns:
        The referenced Python object.

    Raises:
        ValueError: If the reference does not use ``module:attribute`` syntax.
        ImportError: If a referenced Python file cannot be imported.
        AttributeError: If the attribute path cannot be resolved.

    !!! warning
        File references are imported under generated module names. They are
        intended for CLI loading, not for establishing stable import names.

    """
    try:
        module_name, attribute_path = reference.rsplit(":", 1)
    except ValueError as exc:
        raise ValueError("Import references must use module:attribute syntax") from exc
    module_path = Path(module_name)
    if module_name.endswith(".py") or module_path.exists():
        if not module_path.exists():
            raise ImportError(f"Python module file does not exist: {module_path}")
        resolved = module_path.resolve()
        generated_name = f"_talika_cli_{resolved.stem}_{abs(hash(resolved))}"
        spec = importlib.util.spec_from_file_location(generated_name, resolved)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import Python module file: {resolved}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[generated_name] = module
        spec.loader.exec_module(module)
        value = module
    else:
        value = importlib.import_module(module_name)
    for part in attribute_path.split("."):
        value = getattr(value, part)
    return value


def _schema(reference: str) -> type[BaseTable]:
    """Load and validate a table schema import reference.

    Args:
        reference: ``module:Schema`` or ``path.py:Schema`` reference.

    Returns:
        A concrete talika schema class.

    Raises:
        TypeError: If the reference does not resolve to a ``BaseTable``
            subclass.

    !!! info
        Validation happens before command execution so user-facing errors point
        at import configuration rather than producing partial output.

    """
    value = _import_object(reference)
    if not isinstance(value, type) or not issubclass(value, BaseTable):
        raise TypeError(f"{reference!r} is not a talika schema")
    return value


def _context(reference: str | None) -> Mapping[str, Any] | None:
    """Call an optional zero-argument project context factory.

    Args:
        reference: Optional import reference to a callable.

    Returns:
        ``None`` or the mapping returned by the project factory.

    Raises:
        TypeError: If the reference is not callable or does not return a
            mapping.

    !!! warning
        The factory is executed by static checking. It should be deterministic
        and avoid external side effects.

    """
    if reference is None:
        return None
    factory = _import_object(reference)
    if not callable(factory):
        raise TypeError("Context factory reference is not callable")
    value = factory()
    if not isinstance(value, Mapping):
        raise TypeError("Context factory must return a mapping")
    return value


def _diagnostic_data(diagnostic: Diagnostic) -> dict[str, Any]:
    """Return Model v1 fields plus supported legacy aliases."""
    payload = diagnostic.as_dict()
    payload.update(
        {
            "schema": diagnostic.schema_name,
            "field": diagnostic.field_label or diagnostic.field_name,
            "value": (
                stable_json_value(diagnostic.source_value)
                if diagnostic.has_source_value
                else None
            ),
        }
    )
    return payload


def _diagnostic_payload(diagnostic: FeatureDiagnostic) -> dict[str, Any]:
    """Convert one feature diagnostic to a stable CLI JSON object.

    Args:
        diagnostic: Feature diagnostic produced by static checking.

    Returns:
        Dictionary containing file identity, scenario identity, and structured
        table error attributes.

    !!! info
        The shape is intentionally flat so CI systems and editor integrations
        can consume diagnostics without understanding Python exception objects.

    """
    payload = _diagnostic_data(diagnostic.diagnostic)
    payload.update(
        {
            "path": str(diagnostic.path),
            "feature": diagnostic.feature,
            "scenario": diagnostic.scenario,
            "step": diagnostic.step,
        }
    )
    return payload


def _print_json(payload: Mapping[str, Any]) -> None:
    """Print JSON with deterministic ordering.

    Args:
        payload: JSON-compatible mapping to render.

    !!! info
        Sorted keys make CLI output easier to snapshot in tests and compare in
        automation logs.

    """
    print(
        json.dumps(
            stable_json_value(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
    )


def _checker_failure(exc: Exception) -> TableError:
    """Normalize an operational CLI failure without exposing a traceback."""
    if isinstance(exc, TableError):
        return exc
    if isinstance(exc, SchemaDefinitionError):
        return TableError.from_diagnostic(exc.diagnostic)
    error = TableError(
        f"Static checker failed: {exc}",
        code=TableErrorCode.CHECKER_FAILED,
        cause=exc,
    )
    return error


def _render_checker_failure(error: TableError, output_format: str) -> None:
    """Render a controlled checker-level failure in text or JSON form."""
    if output_format == "json":
        _print_json(
            {
                "status": "failed",
                "format_version": 1,
                "matched_tables": 0,
                "error_count": 1,
                "warning_count": 0,
                "diagnostics": [
                    {
                        **_diagnostic_data(error.diagnostic),
                        "path": None,
                        "feature": None,
                        "scenario": None,
                        "step": None,
                    }
                ],
            }
        )
        return
    concise_message = error.message.splitlines()[0]
    print(f"talika: {error.code}: {concise_message}")


def _render_describe_text(schema: type[BaseTable]) -> str:
    """Return a compact human-readable schema contract.

    Args:
        schema: Schema class to describe.

    Returns:
        Multi-line text containing orientation, policies, fields, and variants.

    !!! info
        JSON output uses ``schema.describe().as_dict()``. This renderer is
        optimized for quick terminal inspection.

    """
    contract = schema.describe()
    lines = [
        f"Schema: {contract.schema_name}",
        f"Orientation: {contract.orientation}",
        (
            "Policies: "
            f"unknown_fields={contract.unknown_fields}, "
            f"inapplicable_fields={contract.inapplicable_fields}"
        ),
    ]
    if contract.transformer:
        lines.append(f"Transformer: {contract.transformer}")
    if contract.output_model:
        lines.append(f"Output model: {contract.output_model}")

    lines.append("Fields:")
    for field in contract.fields:
        flags = []
        if field.required:
            flags.append("required")
        if field.is_id:
            flags.append("id")
        if field.is_discriminator:
            flags.append("discriminator")
        if field.has_default:
            flags.append("default")
        suffix = f" ({', '.join(flags)})" if flags else ""
        aliases = f", aliases={list(field.aliases)!r}" if field.aliases else ""
        parser = f", parser={field.parser}" if field.parser else ""
        empty = f", empty={field.empty}" if field.empty != "raw" else ""
        lines.append(
            f"  - {field.name}: label={field.label!r}{aliases}{parser}{empty}{suffix}"
        )

    if contract.variants:
        lines.append("Variants:")
        for variant in contract.variants:
            value = json.dumps(
                stable_json_value(variant.value),
                sort_keys=True,
                allow_nan=False,
            )
            lines.append(f"  - {value}: {variant.schema_name}")
            variant_fields = ", ".join(field.name for field in variant.fields)
            lines.append(f"    fields: {variant_fields}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Create the public argument parser.

    Returns:
        Configured ``argparse.ArgumentParser`` for CLI commands.

    !!! example
        ```python
        parser = build_parser()
        args = parser.parse_args(["describe", "pkg:Schema"])
        ```

    """
    parser = argparse.ArgumentParser(prog="talika")
    subparsers = parser.add_subparsers(dest="command", required=True)
    check = subparsers.add_parser(
        "check",
        help="validate Gherkin data tables without running pytest scenarios",
    )
    check.add_argument("paths", nargs="+", type=Path)
    check.add_argument("--schema", required=True, help="module:SchemaClass")
    check.add_argument("--step", help="exact step text containing the table")
    check.add_argument("--scenario", help="exact scenario name")
    check.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for diagnostics",
    )
    check.add_argument(
        "--context-factory",
        help="optional module:function returning parse context data",
    )
    describe = subparsers.add_parser(
        "describe",
        help="print a talika schema contract",
    )
    describe.add_argument("schema", help="module:SchemaClass")
    describe.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format for the schema contract",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a conventional process exit code.

    Args:
        argv: Optional argument sequence. ``None`` reads process arguments.

    Returns:
        ``0`` for success, ``1`` for validation failures, or ``2`` when filters
        match no tables.

    Raises:
        SystemExit: Through ``argparse`` only when command syntax is invalid.

    !!! warning
        ``check`` parses matching tables and runs project parsers/validators.
        Use ``--context-factory`` for deterministic dependencies.

    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        schema = _schema(args.schema)
        context = _context(args.context_factory) if args.command == "check" else None
    except Exception as exc:
        _render_checker_failure(_checker_failure(exc), args.format)
        return 1

    if args.command == "describe":
        try:
            if args.format == "json":
                _print_json(schema.describe().as_dict())
            else:
                print(_render_describe_text(schema))
            return 0
        except Exception as exc:
            _render_checker_failure(_checker_failure(exc), args.format)
            return 1

    diagnostics = []
    matched_tables = 0

    try:
        for path in args.paths:
            tables = discover_feature_tables(
                path,
                step=args.step,
                scenario=args.scenario,
            )
            matched_tables += len(tables)
            diagnostics.extend(
                check_feature_tables(
                    tables,
                    schema=schema,
                    context=context,
                )
            )
    except Exception as exc:
        _render_checker_failure(_checker_failure(exc), args.format)
        return 1

    if args.format == "json":
        error_count = sum(
            diagnostic.diagnostic.severity is DiagnosticSeverity.ERROR
            for diagnostic in diagnostics
        )
        warning_count = len(diagnostics) - error_count
        status = "failed" if error_count else "valid"
        if matched_tables == 0:
            status = "no_matches"
        _print_json(
            {
                "format_version": 1,
                "status": status,
                "matched_tables": matched_tables,
                "error_count": error_count,
                "warning_count": warning_count,
                "diagnostics": [
                    _diagnostic_payload(diagnostic) for diagnostic in diagnostics
                ],
            }
        )
        if error_count:
            return 1
        if matched_tables == 0:
            return 2
        return 0

    for diagnostic in diagnostics:
        error = diagnostic.error
        row = error.row or 1
        column = error.column or 1
        severity = "warning: " if error.severity is DiagnosticSeverity.WARNING else ""
        print(
            f"{diagnostic.path}:{row}:{column}: {severity}{error.code}: "
            f"{error} [scenario={diagnostic.scenario!r}]"
        )

    error_count = sum(
        diagnostic.diagnostic.severity is DiagnosticSeverity.ERROR
        for diagnostic in diagnostics
    )
    warning_count = len(diagnostics) - error_count
    if error_count:
        print(f"Found {error_count} table error(s) in {matched_tables} table(s).")
        return 1
    if matched_tables == 0:
        print("No matching Gherkin data tables were found.")
        return 2
    suffix = f" with {warning_count} warning(s)" if warning_count else ""
    print(f"Validated {matched_tables} table(s){suffix}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
