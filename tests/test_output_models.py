from dataclasses import dataclass

import pytest

from talika import RowTable, TableError, field, integer


@dataclass(frozen=True)
class User:
    name: str
    age: int


def test_dataclass_output_model_receives_parsed_values():
    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

    users = UserTable.parse([["name", "age"], ["Alice", "30"]])

    assert users == [User(name="Alice", age=30)]


def test_parse_records_skips_output_model_conversion():
    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

    users = UserTable.parse_records([["name", "age"], ["Alice", "30"]])

    assert isinstance(users[0], UserTable)
    assert users[0].name == "Alice"
    assert users[0].age == 30


def test_validation_runs_on_schema_records_before_model_conversion():
    seen = {}

    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

        def validate_record(self, context):
            seen["source"] = self.source_for("age").source_value
            if self.age < 18:
                raise ValueError("User must be an adult")

    with pytest.raises(TableError, match="must be an adult"):
        UserTable.parse([["name", "age"], ["Alice", "16"]])

    assert seen["source"] == "16"


def test_output_model_errors_include_record_location():
    @dataclass
    class StrictUser:
        name: str

        def __post_init__(self):
            raise ValueError("model rejected user")

    class UserTable(RowTable):
        output_model = StrictUser
        name = field("name")

    with pytest.raises(TableError, match="model rejected user") as error:
        UserTable.parse([["name"], ["Alice"]])

    assert error.value.row == 2
