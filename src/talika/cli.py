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


def _json_default(value: Any) -> str:
    """Return a readable JSON fallback for project-owned values.

    Args:
        value: Object that ``json.dumps`` does not know how to encode.

    Returns:
        ``repr(value)`` for deterministic diagnostic output.

    !!! info
        Discriminator values and defaults can be project-owned objects, so JSON
        output needs a stable fallback rather than failing serialization.

    """
    return repr(value)


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
    error = diagnostic.error
    return {
        "path": str(diagnostic.path),
        "feature": diagnostic.feature,
        "scenario": diagnostic.scenario,
        "step": diagnostic.step,
        "code": error.code,
        "message": error.message,
        "hint": error.hint,
        "schema": error.schema,
        "field": error.field,
        "row": error.row,
        "column": error.column,
        "item_id": error.item_id,
        "value": error.value if error.has_value else None,
    }


def _print_json(payload: Mapping[str, Any]) -> None:
    """Print JSON with deterministic ordering.

    Args:
        payload: JSON-compatible mapping to render.

    !!! info
        Sorted keys make CLI output easier to snapshot in tests and compare in
        automation logs.

    """
    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default))


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
            lines.append(f"  - {variant.value!r}: {variant.schema_name}")
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
        SystemExit: Through ``argparse`` when arguments or imports are invalid.

    !!! warning
        ``check`` parses matching tables and runs project parsers/validators.
        Use ``--context-factory`` for deterministic dependencies.

    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        schema = _schema(args.schema)
        context = _context(args.context_factory) if args.command == "check" else None
    except (AttributeError, ImportError, TypeError, ValueError) as exc:
        parser.error(str(exc))

    if args.command == "describe":
        if args.format == "json":
            _print_json(schema.describe().as_dict())
        else:
            print(_render_describe_text(schema))
        return 0

    diagnostics = []
    matched_tables = 0

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

    if args.format == "json":
        status = "failed" if diagnostics else "valid"
        if matched_tables == 0:
            status = "no_matches"
        _print_json(
            {
                "status": status,
                "matched_tables": matched_tables,
                "error_count": len(diagnostics),
                "diagnostics": [
                    _diagnostic_payload(diagnostic) for diagnostic in diagnostics
                ],
            }
        )
        if diagnostics:
            return 1
        if matched_tables == 0:
            return 2
        return 0

    for diagnostic in diagnostics:
        error = diagnostic.error
        row = error.row or 1
        column = error.column or 1
        print(
            f"{diagnostic.path}:{row}:{column}: {error.code}: "
            f"{error} [scenario={diagnostic.scenario!r}]"
        )

    if diagnostics:
        print(f"Found {len(diagnostics)} table error(s) in {matched_tables} table(s).")
        return 1
    if matched_tables == 0:
        print("No matching Gherkin data tables were found.")
        return 2
    print(f"Validated {matched_tables} table(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
