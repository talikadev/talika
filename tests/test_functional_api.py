from dataclasses import dataclass

import pytest

from talika import (
    RowTable,
    TableErrors,
    field,
    integer,
    parse_table,
    parse_table_records,
)


class UserTable(RowTable):
    name = field("name", required=True)
    age = field("age", parser=integer())


def test_parse_table_matches_schema_parse():
    datatable = [["name", "age"], ["Alice", "30"]]

    direct = UserTable.parse(datatable)
    functional = parse_table(UserTable, datatable)

    assert functional == direct
    assert functional[0].name == "Alice"
    assert functional[0].age == 30


def test_parse_table_records_returns_schema_records_with_output_model():
    @dataclass(frozen=True)
    class User:
        name: str

    class OutputUserTable(RowTable):
        output_model = User

        name = field("name", required=True)

    public_users = parse_table(OutputUserTable, [["name"], ["Alice"]])
    records = parse_table_records(OutputUserTable, [["name"], ["Alice"]])

    assert public_users == [User(name="Alice")]
    assert isinstance(records[0], OutputUserTable)
    assert records[0].name == "Alice"


def test_parse_table_forwards_context():
    def from_context(value, context):
        return context.user_data["prefix"] + value

    class ContextUserTable(RowTable):
        name = field("name", parser=from_context)

    users = parse_table(
        ContextUserTable,
        [["name"], ["Alice"]],
        context={"prefix": "QA-"},
    )

    assert users[0].name == "QA-Alice"


def test_parse_table_forwards_error_mode_collect():
    class StrictUserTable(RowTable):
        name = field("name", required=True)
        age = field("age", parser=integer())

    with pytest.raises(TableErrors) as error:
        parse_table(
            StrictUserTable,
            [["name", "age"], ["", "old"]],
            error_mode="collect",
        )

    assert [diagnostic.code for diagnostic in error.value] == [
        "empty_required",
        "parser_failed",
    ]
