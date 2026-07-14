"""Static validation of Gherkin data tables against talika schemas.

The Gherkin dependency is imported lazily so normal runtime parsing remains
dependency-free. Install the ``cli`` extra when using feature-file discovery
or the ``talika check`` command.

!!! info
    Static checking still runs schema parsers and validators. Supply
    deterministic dependencies through parse context when project validators
    normally depend on services or generators.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import TableError, TableErrorCode, TableErrors
from .schema import BaseTable
from .table import TableCell, TableData


@dataclass(frozen=True)
class FeatureTable:
    """One discovered Gherkin step data table.

    Attributes:
        path: Feature file path.
        feature: Feature name.
        scenario: Scenario or background name.
        step: Step text that owns the data table.
        table: Source-aware table converted from Gherkin AST cells.

    !!! info
        The stored ``TableData`` uses feature-file line and column coordinates,
        not indexes relative to the data table block.

    """

    path: Path
    feature: str
    scenario: str
    step: str
    table: TableData


@dataclass(frozen=True)
class FeatureDiagnostic:
    """One schema diagnostic associated with a feature file and step.

    Attributes:
        path: Feature file path.
        feature: Feature name.
        scenario: Scenario or background name.
        step: Step text that owns the failing data table.
        error: Structured table error raised by schema parsing.

    !!! info
        CLI JSON output is a rendering of this object plus the nested
        ``TableError`` attributes.

    """

    path: Path
    feature: str
    scenario: str
    step: str
    error: TableError


def _gherkin_tools() -> tuple[Any, Any]:
    """Load the optional official Gherkin parser and pickle compiler.

    Returns:
        The Gherkin ``Parser`` and ``Compiler`` classes.

    Raises:
        TableError: If the optional ``cli`` dependency is not installed.

    !!! warning
        This dependency is intentionally lazy so core table parsing has no
        runtime dependency on Gherkin parsing packages.

    """
    try:
        from gherkin.parser import Parser  # type: ignore[import-untyped]
        from gherkin.pickles.compiler import Compiler  # type: ignore[import-untyped]
    except ImportError as exc:
        raise TableError(
            "Feature checking requires the 'cli' extra: pip install 'talika[cli]'",
            code=TableErrorCode.CHECKER_FAILED,
        ) from exc
    return Parser, Compiler


def _table_data(data_table: Mapping[str, Any]) -> TableData:
    """Convert a Gherkin AST data table into ``TableData``.

    Args:
        data_table: Gherkin AST mapping containing rows, cells, and locations.

    Returns:
        Source-aware ``TableData`` with feature-file coordinates.

    !!! info
        Coordinates come from the official parser's cell locations, so errors
        point to the feature file rather than to a normalized table index.

    """
    rows = []
    for row in data_table["rows"]:
        cells = []
        for cell in row["cells"]:
            location = cell["location"]
            cells.append(
                TableCell(
                    value=cell["value"],
                    source_row=location["line"],
                    source_column=location["column"],
                    source_value=cell["value"],
                )
            )
        rows.append(cells)
    return TableData.from_cells(rows)


def _scenario_nodes(feature: Mapping[str, Any]) -> Iterable[Mapping[str, Any]]:
    """Yield scenarios and backgrounds from a Gherkin feature node.

    Args:
        feature: Parsed Gherkin feature mapping.

    Yields:
        Scenario or background mappings, including nodes nested inside rules.

    !!! info
        Outline expansion is handled separately with the official Gherkin
        compiler after this traversal identifies the original scenario node.

    """
    for child in feature.get("children", []):
        if "scenario" in child:
            yield child["scenario"]
        elif "background" in child:
            yield child["background"]
        elif "rule" in child:
            yield from _scenario_nodes(child["rule"])


def _example_cells(
    scenario_node: Mapping[str, Any],
) -> dict[str, dict[str, Mapping[str, Any]]]:
    """Map each Examples body-row ID to its parameter source cells."""
    mapped: dict[str, dict[str, Mapping[str, Any]]] = {}
    for examples in scenario_node.get("examples", []):
        header = examples.get("tableHeader")
        if not header:
            continue
        names = [cell["value"] for cell in header.get("cells", [])]
        for row in examples.get("tableBody", []):
            mapped[row["id"]] = dict(zip(names, row.get("cells", []), strict=False))
    return mapped


def _compiled_table_data(
    source_table: Mapping[str, Any],
    compiled_table: Mapping[str, Any],
    parameters: Mapping[str, Mapping[str, Any]],
) -> TableData:
    """Combine compiled logical values with precise AST source locations."""
    rows: list[list[TableCell]] = []
    for source_row, compiled_row in zip(
        source_table["rows"], compiled_table["rows"], strict=True
    ):
        cells: list[TableCell] = []
        for source_cell, compiled_cell in zip(
            source_row["cells"], compiled_row["cells"], strict=True
        ):
            source_value = source_cell["value"]
            parameter_name = (
                source_value[1:-1]
                if source_value.startswith("<")
                and source_value.endswith(">")
                and source_value.count("<") == 1
                and source_value.count(">") == 1
                else None
            )
            effective_source = (
                parameters.get(parameter_name, source_cell)
                if parameter_name is not None
                else source_cell
            )
            location = effective_source["location"]
            cells.append(
                TableCell(
                    value=compiled_cell["value"],
                    source_row=location["line"],
                    source_column=location["column"],
                    source_value=effective_source["value"],
                )
            )
        rows.append(cells)
    return TableData.from_cells(rows)


def _outline_tables(
    *,
    source_path: Path,
    feature_name: str,
    scenario_node: Mapping[str, Any],
    pickles: Iterable[Mapping[str, Any]],
    step_filter: str | None,
) -> list[FeatureTable]:
    """Expand one scenario outline into logical feature tables."""
    scenario_id = scenario_node["id"]
    example_rows = _example_cells(scenario_node)
    source_steps = {step["id"]: step for step in scenario_node.get("steps", [])}
    discovered: list[FeatureTable] = []
    for pickle in pickles:
        ast_ids = pickle.get("astNodeIds", [])
        if scenario_id not in ast_ids:
            continue
        example_id = next(
            (node_id for node_id in ast_ids if node_id in example_rows), None
        )
        if example_id is None:
            continue
        parameters = example_rows[example_id]
        for compiled_step in pickle.get("steps", []):
            step_id = next(
                (
                    node_id
                    for node_id in compiled_step.get("astNodeIds", [])
                    if node_id in source_steps
                ),
                None,
            )
            if step_id is None:
                continue
            source_step = source_steps[step_id]
            source_table = source_step.get("dataTable")
            compiled_table = compiled_step.get("argument", {}).get("dataTable")
            step_text = source_step.get("text", "")
            if (
                source_table is None
                or compiled_table is None
                or (step_filter is not None and step_text != step_filter)
            ):
                continue
            discovered.append(
                FeatureTable(
                    path=source_path,
                    feature=feature_name,
                    scenario=scenario_node.get("name", ""),
                    step=step_text,
                    table=_compiled_table_data(
                        source_table,
                        compiled_table,
                        parameters,
                    ),
                )
            )
    return discovered


def discover_feature_tables(
    path: str | Path,
    *,
    step: str | None = None,
    scenario: str | None = None,
) -> list[FeatureTable]:
    """Return matching feature-file data tables.

    Args:
        path: Feature file path.
        step: Optional exact step text filter.
        scenario: Optional exact scenario/background name filter.

    Returns:
        Matching ``FeatureTable`` objects.

    Raises:
        TableError: If discovery cannot read or compile the feature file.

    !!! example
        ```python
        tables = discover_feature_tables("users.feature", step="the users:")
        ```

    """
    source_path = Path(path)
    try:
        Parser, Compiler = _gherkin_tools()
        document = Parser().parse(source_path.read_text(encoding="utf-8"))
        document["uri"] = str(source_path)
        pickles = Compiler().compile(document)
    except TableError:
        raise
    except Exception as exc:
        raise TableError(
            f"Feature discovery failed for {source_path}: {exc}",
            code=TableErrorCode.CHECKER_FAILED,
        ) from exc
    feature = document.get("feature")
    if feature is None:
        return []

    discovered = []
    for scenario_node in _scenario_nodes(feature):
        scenario_name = scenario_node.get("name", "")
        if scenario is not None and scenario_name != scenario:
            continue
        if scenario_node.get("examples"):
            discovered.extend(
                _outline_tables(
                    source_path=source_path,
                    feature_name=feature.get("name", ""),
                    scenario_node=scenario_node,
                    pickles=pickles,
                    step_filter=step,
                )
            )
            continue
        for step_node in scenario_node.get("steps", []):
            data_table = step_node.get("dataTable")
            step_text = step_node.get("text", "")
            if data_table is None or (step is not None and step_text != step):
                continue
            discovered.append(
                FeatureTable(
                    path=source_path,
                    feature=feature.get("name", ""),
                    scenario=scenario_name,
                    step=step_text,
                    table=_table_data(data_table),
                )
            )
    return discovered


def check_feature(
    path: str | Path,
    *,
    schema: type[BaseTable],
    step: str | None = None,
    scenario: str | None = None,
    context: Mapping[str, Any] | None = None,
) -> list[FeatureDiagnostic]:
    """Validate matching feature tables without executing pytest scenarios.

    Custom parsers and validators still run. Projects whose schemas require
    services should supply deterministic checking dependencies through
    ``context`` or through the CLI's context-factory option.

    Args:
        path: Feature file path.
        schema: Schema used to parse matching data tables.
        step: Optional exact step text filter.
        scenario: Optional exact scenario/background name filter.
        context: Optional project data passed to schema parsing.

    Returns:
        Structured diagnostics for every matching table failure.

    !!! warning
        Custom validation code executes during checking. Keep context factories
        deterministic and free of external side effects in CI/editor workflows.

    """
    return check_feature_tables(
        discover_feature_tables(path, step=step, scenario=scenario),
        schema=schema,
        context=context,
    )


def check_feature_tables(
    tables: Iterable[FeatureTable],
    *,
    schema: type[BaseTable],
    context: Mapping[str, Any] | None = None,
) -> list[FeatureDiagnostic]:
    """Validate already-discovered feature tables against one schema.

    Args:
        tables: Feature tables returned by ``discover_feature_tables``.
        schema: Schema used to parse each data table.
        context: Optional project data passed to schema parsing.

    Returns:
        Structured diagnostics for every matching table failure.

    !!! info
        ``check_feature`` discovers tables and delegates here. The CLI calls
        this helper after its own discovery pass so it can count matches
        without parsing the feature file twice.

    """
    diagnostics: list[FeatureDiagnostic] = []
    for discovered in tables:
        try:
            schema.parse_records(
                discovered.table,
                context=context,
                error_mode="collect",
            )
        except TableErrors as exc:
            errors = exc.errors
        except TableError as exc:
            errors = (exc,)
        else:
            errors = ()
        diagnostics.extend(
            FeatureDiagnostic(
                path=discovered.path,
                feature=discovered.feature,
                scenario=discovered.scenario,
                step=discovered.step,
                error=error,
            )
            for error in errors
        )
    return diagnostics
