import json
import sys
from types import ModuleType

from talika import RowTable, check_feature, discover_feature_tables, field
from talika.checker import FeatureTable
from talika.cli import main

FEATURE = """Feature: Static checking

  Scenario: Invalid users
    Given the following checked users:
      | name  | age |
      |       | old |
"""


class CheckedUserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age")


FEATURE_PATH = "tests/data/invalid_users.feature"


def test_discovery_uses_real_feature_file_coordinates():
    tables = discover_feature_tables(FEATURE_PATH, step="the following checked users:")

    assert len(tables) == 1
    assert tables[0].scenario == "Invalid users"
    assert tables[0].table.cell(2, 1).source_row == 6
    assert tables[0].table.cell(2, 1).source_column == 15


def test_static_checker_collects_schema_diagnostics():
    diagnostics = check_feature(
        FEATURE_PATH,
        schema=CheckedUserTable,
        step="the following checked users:",
    )

    assert [diagnostic.error.code for diagnostic in diagnostics] == [
        "empty_required",
        "parser_failed",
    ]
    assert diagnostics[0].error.row == 6


def test_cli_reports_valid_example(capsys):
    module = ModuleType("talika_cli_test_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_cli_test_schema:CheckedUserTable",
                "--step",
                "the following checked users:",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 1
    output = capsys.readouterr().out
    assert "empty_required" in output
    assert "Found 2 table error(s)" in output


def test_cli_reports_json_diagnostics(capsys):
    module = ModuleType("talika_cli_json_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_cli_json_schema:CheckedUserTable",
                "--step",
                "the following checked users:",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["matched_tables"] == 1
    assert payload["diagnostics"][0]["code"] == "empty_required"
    assert payload["diagnostics"][0]["hint"]


def test_cli_describes_schema_as_text(capsys):
    module = ModuleType("talika_cli_describe_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "describe",
                "talika_cli_describe_schema:CheckedUserTable",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Schema: CheckedUserTable" in output
    assert "Orientation: row" in output
    assert "name: label='name'" in output


def test_module_entrypoint_describes_schema_as_text(capsys):
    from talika.__main__ import main as module_main

    module = ModuleType("talika_module_describe_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = module_main(
            [
                "describe",
                "talika_module_describe_schema:CheckedUserTable",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 0
    assert "Schema: CheckedUserTable" in capsys.readouterr().out


def test_cli_describes_schema_as_json(capsys):
    module = ModuleType("talika_cli_describe_json_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "describe",
                "talika_cli_describe_json_schema:CheckedUserTable",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_name"] == "CheckedUserTable"
    assert payload["fields"][0]["label"] == "name"


def test_cli_fails_when_filters_match_no_tables(capsys):
    module = ModuleType("talika_cli_empty_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_cli_empty_schema:CheckedUserTable",
                "--step",
                "a step that does not exist",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 2
    assert "No matching" in capsys.readouterr().out


def test_cli_reuses_discovered_tables(monkeypatch, capsys):
    import talika.cli as cli

    module = ModuleType("talika_cli_reuse_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    calls = []
    table = discover_feature_tables(
        FEATURE_PATH,
        step="the following checked users:",
    )[0]

    def discover_once(path, *, step=None, scenario=None):
        calls.append((path, step, scenario))
        return [
            FeatureTable(
                path=table.path,
                feature=table.feature,
                scenario=table.scenario,
                step=table.step,
                table=table.table,
            )
        ]

    monkeypatch.setattr(cli, "discover_feature_tables", discover_once)
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_cli_reuse_schema:CheckedUserTable",
                "--step",
                "the following checked users:",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 1
    assert len(calls) == 1
    assert "Found 2 table error(s)" in capsys.readouterr().out
