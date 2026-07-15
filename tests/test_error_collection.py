import pytest

from talika import (
    ColumnTable,
    RowTable,
    TableError,
    TableErrors,
    field,
    id_field,
)


def test_collect_mode_reports_multiple_cells_in_discovery_order():
    class UserTable(RowTable):
        name = field("name", required=True)
        age: int = field("age", required=True)

    with pytest.raises(TableErrors) as captured:
        UserTable.parse(
            [
                ["name", "age"],
                ["", "old"],
                ["", "older"],
            ],
            error_mode="collect",
        )

    errors = captured.value.errors
    assert len(errors) == 4
    assert [error.code for error in errors] == [
        "empty_required",
        "parser_failed",
        "empty_required",
        "parser_failed",
    ]
    assert [(error.row, error.column) for error in errors] == [
        (2, 1),
        (2, 2),
        (3, 1),
        (3, 2),
    ]


def test_first_mode_remains_the_default():
    class UserTable(RowTable):
        name = field("name", required=True)
        age: int = field("age", required=True)

    with pytest.raises(TableError) as captured:
        UserTable.parse([["name", "age"], ["", "old"]])

    assert not isinstance(captured.value, TableErrors)
    assert captured.value.code == "empty_required"


def test_collect_mode_combines_valid_record_validation_failures():
    class ScoreTable(ColumnTable):
        id = id_field("IDs")
        score: int = field("Score", required=True)

        def validate_record(self, context):
            if self.score < 0:
                raise ValueError("score cannot be negative")

    with pytest.raises(TableErrors) as captured:
        ScoreTable.parse(
            [["IDs", "1", "2"], ["Score", "-1", "-2"]],
            error_mode="collect",
        )

    assert len(captured.value) == 2
    assert all(error.code == "record_validation_failed" for error in captured.value)


def test_invalid_error_mode_is_rejected():
    class ValueTable(RowTable):
        value = field("value")

    with pytest.raises(ValueError, match="error_mode"):
        ValueTable.parse([["value"], ["one"]], error_mode="everything")


def test_collect_mode_reports_column_ragged_rows_as_aggregate():
    class ValueTable(ColumnTable):
        id = id_field("IDs")
        value = field("Value")

    with pytest.raises(TableErrors) as captured:
        ValueTable.parse([["IDs", "1"], ["Value"]], error_mode="collect")

    assert len(captured.value) == 1
    assert captured.value.errors[0].code == "ragged_row"


def test_collect_mode_reports_all_missing_required_fields_without_data_rows():
    class UserTable(RowTable):
        name = field("name", required=True)
        role = field("role", required=True)

    with pytest.raises(TableErrors) as captured:
        UserTable.parse([["unknown"]], error_mode="collect")

    assert [error.code for error in captured.value] == [
        "unknown_field",
        "missing_required",
        "missing_required",
    ]
    assert [error.field for error in captured.value.errors[1:]] == ["name", "role"]
