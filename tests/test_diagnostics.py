from dataclasses import FrozenInstanceError
from datetime import date
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

import pytest

import talika.engine as engine
from talika import (
    ColumnTable,
    Diagnostic,
    DiagnosticSeverity,
    RowTable,
    SchemaDefinitionError,
    TableCell,
    TableData,
    TableError,
    TableErrorCode,
    TableErrors,
    ValidationResult,
    field,
    id_field,
    integer,
    reference,
    validate_table,
)


def test_diagnostic_model_is_immutable_and_presence_aware():
    cause = ValueError("bad value")
    diagnostic = Diagnostic(
        code="custom",
        message="Custom failure",
        item_id=None,
        source_value=None,
        cause=cause,
    )

    assert diagnostic.diagnostic_version == 1
    assert diagnostic.severity is DiagnosticSeverity.ERROR
    assert diagnostic.has_item_id
    assert diagnostic.item_id is None
    assert diagnostic.has_source_value
    assert diagnostic.source_value is None
    assert not diagnostic.has_logical_value
    assert diagnostic.cause is cause
    assert diagnostic.as_dict()["source_value"] is None
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = "changed"  # type: ignore[misc]


def test_diagnostic_cause_is_not_serialized_or_compared():
    first = Diagnostic(code="custom", message="Failure", cause=ValueError("one"))
    second = Diagnostic(code="custom", message="Failure", cause=RuntimeError("two"))

    assert first == second
    assert "cause" not in first.as_dict()


def test_validation_result_filters_warnings_without_invalidating_records():
    warning = Diagnostic(
        code="project_warning",
        message="Review this value",
        severity=DiagnosticSeverity.WARNING,
    )
    result = ValidationResult(records=("record",), diagnostics=(warning,))

    assert result.valid
    assert result.errors == ()
    assert result.warnings == (warning,)
    assert result.records == ("record",)


def test_diagnostic_serialization_avoids_object_reprs_and_cycles():
    class Status(Enum):
        READY = "ready"

    class ProjectValue:
        pass

    cyclic = []
    cyclic.append(cyclic)
    diagnostic = Diagnostic(
        code="custom",
        message="Failure",
        item_id=ProjectValue(),
        logical_value={
            "cycle": cyclic,
            "date": date(2026, 7, 15),
            "decimal": Decimal("1.50"),
            "enum": Status.READY,
            "infinity": float("inf"),
            "mapping": {2: "two", 1: "one"},
            "path": Path("table.feature"),
            "set": {"b", "a"},
            "uuid": UUID("12345678-1234-5678-1234-567812345678"),
        },
    )
    payload = diagnostic.as_dict()

    assert payload["item_id"] == {
        "type": f"{ProjectValue.__module__}.{ProjectValue.__qualname__}"
    }
    logical = payload["logical_value"]
    assert logical["cycle"][0] == {"type": "builtins.list"}
    assert logical["date"] == "2026-07-15"
    assert logical["decimal"] == "1.50"
    assert logical["enum"]["name"] == "READY"
    assert logical["infinity"] == {"type": "float", "value": "infinity"}
    assert logical["mapping"] == {
        "type": "mapping",
        "entries": [[1, "one"], [2, "two"]],
    }
    assert logical["path"] == "table.feature"
    assert logical["set"] == ["a", "b"]
    assert logical["uuid"] == "12345678-1234-5678-1234-567812345678"
    assert "0x" not in str(payload)


def test_table_error_is_a_compatible_diagnostic_adapter():
    cell = TableCell(
        value="Article",
        source_row=7,
        source_column=4,
        source_value="3:Article",
        source_uri="file:///features/content.feature",
    )
    error = TableError.from_cell(
        "Invalid value",
        cell,
        schema="Content",
        field_name="kind",
        field_label="Type",
        code=TableErrorCode.INVALID_TRANSFORM,
    )

    assert error.schema == "Content"
    assert error.field == "Type"
    assert error.field_name == "kind"
    assert error.field_label == "Type"
    assert error.value == "3:Article"
    assert error.logical_value == "Article"
    assert error.source_uri == "file:///features/content.feature"
    assert error.diagnostic.source_value == "3:Article"
    assert error.diagnostic.logical_value == "Article"

    aggregate = TableErrors([error])
    assert aggregate.diagnostics == (error.diagnostic,)

    definition = SchemaDefinitionError("Invalid schema", schema="Content")
    assert definition.diagnostic.code == "schema_definition"


def test_validate_returns_records_only_for_a_valid_table():
    class Users(RowTable):
        name = field("name", required=True)
        age = field("age", parser=integer())

    valid = Users.validate(
        [
            [
                "name",
                "age",
            ],
            ["Alice", "30"],
        ]
    )
    invalid = Users.validate([["name", "age"], ["", "bad"]])

    assert isinstance(valid, ValidationResult)
    assert valid.valid
    assert len(valid.records) == 1
    valid.records[0].name = "Changed"
    assert valid.records[0].name == "Changed"

    assert not invalid.valid
    assert invalid.records == ()
    assert [item.code for item in invalid.errors] == [
        "empty_required",
        "parser_failed",
    ]
    assert invalid.warnings == ()
    assert validate_table(Users, [["name", "age"], ["", "bad"]]) == invalid


def test_validate_runs_validation_but_skips_output_conversion():
    calls: list[str] = []

    class Users(RowTable):
        name = field("name")

        @classmethod
        def validate_record(cls, record, context):
            calls.append("validate")

        @classmethod
        def build_output(cls, record, context):
            calls.append("output")
            raise RuntimeError("output should not run")

    result = Users.validate([["name"], ["Alice"]])

    assert result.valid
    assert calls == ["validate"]
    with pytest.raises(TableError, match="output should not run"):
        Users.parse([["name"], ["Alice"]])


def test_custom_table_errors_pass_through_parsers_and_validation():
    custom = TableError("Project diagnostic", code="project_error")

    def parser(value, context):
        raise custom

    class Values(RowTable):
        value = field("value", parser=parser)

    with pytest.raises(TableError) as captured:
        Values.parse([["value"], ["bad"]])
    assert captured.value is custom

    result = Values.validate([["value"], ["bad"], ["also bad"]])
    assert result.records == ()
    assert result.diagnostics == (custom.diagnostic, custom.diagnostic)


def test_custom_table_errors_pass_through_every_extension_boundary():
    factory_error = TableError("Factory diagnostic", code="factory_project_error")

    def factory(context):
        raise factory_error

    class FactoryRows(RowTable):
        present = field("present")
        generated = field("generated", default_factory=factory)

    with pytest.raises(TableError) as factory_captured:
        FactoryRows.parse([["present"], ["value"]])
    assert factory_captured.value is factory_error

    validation_error = TableError(
        "Validation diagnostic", code="validation_project_error"
    )

    class ValidatedRows(RowTable):
        value = field("value")

        def validate_record(self, context):
            raise validation_error

    with pytest.raises(TableError) as validation_captured:
        ValidatedRows.parse([["value"], ["bad"]])
    assert validation_captured.value is validation_error

    output_error = TableError("Output diagnostic", code="output_project_error")

    class OutputRows(RowTable):
        value = field("value")

        @classmethod
        def build_output(cls, record, context):
            raise output_error

    with pytest.raises(TableError) as output_captured:
        OutputRows.parse([["value"], ["bad"]])
    assert output_captured.value is output_error

    reference_error = TableError("Reference diagnostic", code="reference_project_error")

    def identifier(value, context):
        if context.field_name == "parent":
            raise reference_error
        return int(value)

    class ReferencedColumns(ColumnTable):
        id = id_field("IDs", parser=identifier)
        parent = reference("Parent")

    with pytest.raises(TableError) as reference_captured:
        ReferencedColumns.parse([["IDs", "1", "2"], ["Parent", "", "1"]])
    assert reference_captured.value is reference_error


def test_wrapped_user_errors_keep_their_cause():
    def parser(value, context):
        raise ValueError("not a project value")

    class Values(RowTable):
        value = field("value", parser=parser)

    result = Values.validate([["value"], ["bad"]])

    assert result.errors[0].code == "parser_failed"
    assert isinstance(result.errors[0].cause, ValueError)


def test_unexpected_internal_errors_are_normalized(monkeypatch):
    class Values(RowTable):
        value = field("value")

    def broken_engine(*args, **kwargs):
        raise RuntimeError("private failure")

    monkeypatch.setattr(engine, "parse_row_table", broken_engine)

    result = Values.validate([["value"], ["one"]])
    assert result.errors[0].code == "internal_error"
    assert isinstance(result.errors[0].cause, RuntimeError)

    with pytest.raises(TableError) as captured:
        Values.parse([["value"], ["one"]])
    assert captured.value.code == "internal_error"
    assert isinstance(captured.value.__cause__, RuntimeError)


def test_source_uri_reaches_records_and_diagnostics(tmp_path):
    source = tmp_path / "users.feature"

    class Users(RowTable):
        name = field("name", required=True)

    valid_table = TableData.from_rows([["name"], ["Alice"]], source=source)
    invalid_table = TableData.from_rows([["name"], [""]], source=source)

    valid = Users.validate(valid_table)
    invalid = Users.validate(invalid_table)

    assert valid.records[0].table_source.source_uri == source.resolve().as_uri()
    assert invalid.errors[0].source_uri == source.resolve().as_uri()


def test_transformations_inherit_source_uri_when_the_result_omits_it(tmp_path):
    source = tmp_path / "values.feature"

    class Values(RowTable):
        value = field("value")

        @classmethod
        def transform_table(cls, table, context):
            return TableData.from_rows(table.to_rows())

    result = Values.validate(TableData.from_rows([["value"], ["one"]], source=source))

    assert result.records[0].table_source.source_uri == source.resolve().as_uri()


def test_validate_is_a_reserved_schema_field_name():
    with pytest.raises(SchemaDefinitionError, match="reserved"):

        class InvalidRows(RowTable):
            validate = field("validate")
