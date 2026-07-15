import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

from talika import (
    ColumnTable,
    RowTable,
    TableData,
    TableError,
    check_feature,
    discover_feature_tables,
    discriminator_field,
    field,
    id_field,
    reference,
)
from talika.checker import FeatureTable, check_feature_tables
from talika.cli import main

FEATURE = """Feature: Static checking

  Scenario: Invalid users
    Given the following checked users:
      | name  | age |
      |       | old |
"""


class CheckedUserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)


FEATURE_PATH = "tests/data/invalid_users.feature"


def test_discovery_uses_real_feature_file_coordinates():
    tables = discover_feature_tables(FEATURE_PATH, step="the following checked users:")

    assert len(tables) == 1
    assert tables[0].scenario == "Invalid users"
    assert tables[0].table.cell(2, 1).source_row == 6
    assert tables[0].table.cell(2, 1).source_column == 15
    assert tables[0].table.source_uri == Path(FEATURE_PATH).resolve().as_uri()


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
    assert diagnostics[0].diagnostic is diagnostics[0].error.diagnostic
    assert diagnostics[0].diagnostic.source_uri == Path(FEATURE_PATH).resolve().as_uri()


def test_cli_reports_text_diagnostics(capsys):
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
    assert payload["format_version"] == 1
    assert payload["matched_tables"] == 1
    assert payload["error_count"] == 2
    assert payload["warning_count"] == 0
    assert payload["diagnostics"][0]["code"] == "empty_required"
    assert payload["diagnostics"][0]["hint"]
    assert payload["diagnostics"][0]["diagnostic_version"] == 1
    assert payload["diagnostics"][0]["field_name"] == "name"
    assert payload["diagnostics"][0]["field_label"] == "name"
    assert payload["diagnostics"][0]["has_item_id"] is False
    assert payload["diagnostics"][0]["has_source_value"] is True
    assert payload["diagnostics"][0]["source_value"] == ""
    assert payload["diagnostics"][0]["logical_value"] == ""
    assert (
        payload["diagnostics"][0]["source_uri"] == Path(FEATURE_PATH).resolve().as_uri()
    )


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


def test_cli_no_match_json_uses_the_versioned_empty_shape(capsys):
    module = ModuleType("talika_cli_empty_json_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_cli_empty_json_schema:CheckedUserTable",
                "--step",
                "a step that does not exist",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload == {
        "diagnostics": [],
        "error_count": 0,
        "format_version": 1,
        "matched_tables": 0,
        "status": "no_matches",
        "warning_count": 0,
    }


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


OUTLINE_FEATURE = """Feature: Outline checking

  Scenario Outline: Users
    Given the outline users:
      | name   | age   | token     |
      | <name> | <age> | user-<id> |

    Examples: Primary
      | name  | age | id |
      | Alice | old | 1  |
      | Bob   | 2   | 2  |

    Examples: Secondary
      | name  | age | id |
      | Carol | 3   | 3  |
"""


def test_scenario_outlines_expand_with_compiled_values_and_source_locations(tmp_path):
    path = tmp_path / "outline.feature"
    path.write_text(OUTLINE_FEATURE, encoding="utf-8")

    tables = discover_feature_tables(path, step="the outline users:")

    assert len(tables) == 3
    assert [table.scenario for table in tables] == ["Users"] * 3
    assert [table.step for table in tables] == ["the outline users:"] * 3
    assert tables[0].table.to_rows()[1] == ["Alice", "old", "user-1"]
    assert tables[1].table.to_rows()[1] == ["Bob", "2", "user-2"]
    assert tables[2].table.to_rows()[1] == ["Carol", "3", "user-3"]

    exact = tables[0].table.cell(2, 1)
    mixed = tables[0].table.cell(2, 3)
    assert (exact.source_row, exact.source_value) == (10, "Alice")
    assert (mixed.source_row, mixed.source_value) == (6, "user-<id>")


def test_outlines_count_each_example_and_keep_original_filters(tmp_path, capsys):
    class OutlineUsers(RowTable):
        name = field("name")
        age: int = field("age", required=True)
        token = field("token")

    path = tmp_path / "outline.feature"
    path.write_text(OUTLINE_FEATURE, encoding="utf-8")
    module = ModuleType("talika_outline_schema")
    module.OutlineUsers = OutlineUsers
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                str(path),
                "--schema",
                "talika_outline_schema:OutlineUsers",
                "--scenario",
                "Users",
                "--step",
                "the outline users:",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["matched_tables"] == 3
    assert payload["error_count"] == 1
    assert payload["format_version"] == 1
    assert payload["warning_count"] == 0
    assert payload["diagnostics"][0]["row"] == 10


def test_static_checking_never_calls_output_builders():
    calls = []

    class OutputTable(RowTable):
        value = field("value")

        @classmethod
        def build_output(cls, record, context):
            calls.append(record.value)
            raise AssertionError("output conversion must not run")

    diagnostics = check_feature_tables(
        [
            FeatureTable(
                path=Path("inline.feature"),
                feature="Inline",
                scenario="One",
                step="the values:",
                table=TableData.from_rows([["value"], ["accepted"]]),
            )
        ],
        schema=OutputTable,
    )

    assert diagnostics == []
    assert calls == []


def test_invalid_gherkin_is_a_controlled_checker_failure(tmp_path):
    path = tmp_path / "broken.feature"
    path.write_text("not gherkin", encoding="utf-8")

    with pytest.raises(TableError) as captured:
        discover_feature_tables(path)

    assert captured.value.code == "checker_failed"
    assert captured.value.__cause__ is not None


def test_missing_feature_file_is_a_controlled_checker_failure(tmp_path):
    with pytest.raises(TableError) as captured:
        discover_feature_tables(tmp_path / "missing.feature")

    assert captured.value.code == "checker_failed"
    assert isinstance(captured.value.__cause__, FileNotFoundError)


def test_unreadable_utf8_is_a_controlled_checker_failure(tmp_path):
    path = tmp_path / "binary.feature"
    path.write_bytes(b"\xff\xfe")

    with pytest.raises(TableError) as captured:
        discover_feature_tables(path)

    assert captured.value.code == "checker_failed"
    assert isinstance(captured.value.__cause__, UnicodeDecodeError)


def test_background_discovery_is_not_duplicated_by_outline_expansion(tmp_path):
    path = tmp_path / "background.feature"
    path.write_text(
        """Feature: Background and outline

  Background: Setup
    Given the defaults:
      | value |
      | base  |

  Scenario Outline: Cases
    Given the values:
      | value   |
      | <value> |

    Examples:
      | value |
      | one   |
      | two   |
""",
        encoding="utf-8",
    )

    tables = discover_feature_tables(path)

    assert [table.scenario for table in tables] == ["Setup", "Cases", "Cases"]


def test_cli_operational_failure_uses_stable_json_shape(capsys, tmp_path):
    module = ModuleType("talika_missing_feature_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                str(tmp_path / "missing.feature"),
                "--schema",
                "talika_missing_feature_schema:CheckedUserTable",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["matched_tables"] == 0
    assert payload["error_count"] == 1
    assert payload["diagnostics"][0]["code"] == "checker_failed"
    assert payload["diagnostics"][0]["scenario"] is None


def test_cli_missing_file_text_failure_has_no_traceback(capsys, tmp_path):
    module = ModuleType("talika_missing_feature_text_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                str(tmp_path / "missing.feature"),
                "--schema",
                "talika_missing_feature_text_schema:CheckedUserTable",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    output = capsys.readouterr().out
    assert exit_code == 1
    assert "checker_failed" in output
    assert "Traceback" not in output


@pytest.mark.parametrize("output_format", ["text", "json"])
def test_cli_invalid_gherkin_is_controlled(capsys, tmp_path, output_format):
    path = tmp_path / "invalid.feature"
    path.write_text("not gherkin", encoding="utf-8")
    module = ModuleType(f"talika_invalid_gherkin_{output_format}")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                str(path),
                "--schema",
                f"{module.__name__}:CheckedUserTable",
                "--format",
                output_format,
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    output = capsys.readouterr().out
    assert exit_code == 1
    if output_format == "json":
        assert json.loads(output)["diagnostics"][0]["code"] == "checker_failed"
    else:
        assert "checker_failed" in output


def test_bad_schema_import_and_context_factory_are_exit_one(capsys):
    assert main(["check", FEATURE_PATH, "--schema", "missing_module:Schema"]) == 1
    assert "checker_failed" in capsys.readouterr().out

    module = ModuleType("talika_bad_context")
    module.CheckedUserTable = CheckedUserTable

    def broken_context():
        raise RuntimeError("context unavailable")

    module.broken_context = broken_context
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_bad_context:CheckedUserTable",
                "--context-factory",
                "talika_bad_context:broken_context",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    assert exit_code == 1
    assert "context unavailable" in capsys.readouterr().out


def test_bad_schema_import_uses_controlled_json(capsys):
    exit_code = main(
        [
            "check",
            FEATURE_PATH,
            "--schema",
            "missing_module:Schema",
            "--format",
            "json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert payload["diagnostics"][0]["code"] == "checker_failed"


def test_cli_preserves_schema_definition_diagnostics(capsys):
    class BrokenReferences(ColumnTable):
        id = id_field("IDs")
        kind = discriminator_field("Kind")
        parent = reference("Parent", target="missing")

    module = ModuleType("talika_broken_reference_schema")
    module.BrokenReferences = BrokenReferences
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_broken_reference_schema:BrokenReferences",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "schema_definition"


def test_cli_preserves_internal_error_diagnostics(monkeypatch, capsys):
    import talika.cli as cli

    module = ModuleType("talika_internal_error_schema")
    module.CheckedUserTable = CheckedUserTable
    sys.modules[module.__name__] = module

    def broken_check(*args, **kwargs):
        raise TableError("Internal failure", code="internal_error")

    monkeypatch.setattr(cli, "check_feature_tables", broken_check)
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_internal_error_schema:CheckedUserTable",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["diagnostics"][0]["code"] == "internal_error"


def test_bad_context_factory_uses_controlled_json(capsys):
    module = ModuleType("talika_bad_json_context")
    module.CheckedUserTable = CheckedUserTable

    def broken_context():
        raise RuntimeError("context unavailable")

    module.context = broken_context
    sys.modules[module.__name__] = module
    try:
        exit_code = main(
            [
                "check",
                FEATURE_PATH,
                "--schema",
                "talika_bad_json_context:CheckedUserTable",
                "--context-factory",
                "talika_bad_json_context:context",
                "--format",
                "json",
            ]
        )
    finally:
        sys.modules.pop(module.__name__, None)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert payload["status"] == "failed"
    assert "context unavailable" in payload["diagnostics"][0]["message"]
