# --8<-- [start:feature-basic]
Feature: User setup

  Scenario: Create users from a table
    Given the users exist:
      | username | age |
      | alice    | 34  |
    Then alice can sign in
# --8<-- [end:feature-basic]

# --8<-- [start:schema]
from talika import RowTable, field, integer


class UserTable(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    role = field("role", default="viewer")
# --8<-- [end:schema]

# --8<-- [start:direct-step]
from pytest_bdd import given, scenario, then


@scenario("users.feature", "Create users from a table")
def test_create_users():
    pass


@given("the users exist:", target_fixture="users")
def users(datatable):
    return UserTable.parse(datatable)


@then("alice can sign in")
def alice_can_sign_in(users):
    assert users[0].username == "alice"
    assert users[0].age == 34
    assert users[0].role == "viewer"
# --8<-- [end:direct-step]

# --8<-- [start:direct-output]
>> users[0]
UserTable(username='alice', age=34, role='viewer')

>> users[0].as_dict()
{'username': 'alice', 'age': 34, 'role': 'viewer'}
# --8<-- [end:direct-output]

# --8<-- [start:raw-datatable]
datatable = [
    ["username", "age"],
    ["alice", "34"],
]

users = UserTable.parse(datatable)
# --8<-- [end:raw-datatable]

# --8<-- [start:fixture-step]
@given("the users exist:", target_fixture="users")
def users(datatable, talika):
    return talika.parse(datatable, schema=UserTable)
# --8<-- [end:fixture-step]

# --8<-- [start:fixture-equivalent]
UserTable.parse(datatable)
# --8<-- [end:fixture-equivalent]

# --8<-- [start:fixture-records-step]
@given("the user records exist:", target_fixture="user_records")
def user_records(datatable, talika):
    return talika.parse(datatable, schema=UserTable)
# --8<-- [end:fixture-records-step]

# --8<-- [start:context-step]
def parse_username(value, context):
    return context.user_data["prefix"] + value


class ContextUserTable(RowTable):
    username = field("username", parser=parse_username)


@given("the imported users exist:", target_fixture="users")
def imported_users(datatable, talika):
    return talika.parse(
        datatable,
        schema=ContextUserTable,
        context={"prefix": "QA-"},
    )
# --8<-- [end:context-step]

# --8<-- [start:context-output]
>> users[0]
ContextUserTable(username='QA-alice')

>> users[0].as_dict()
{'username': 'QA-alice'}
# --8<-- [end:context-output]

# --8<-- [start:functional-api]
from talika import parse_table, parse_table_as


records = parse_table(UserTable, datatable)
values = parse_table_as(UserTable, datatable, dict)

assert records[0].username == "alice"
assert values[0]["username"] == "alice"
assert records[0].as_dict() == {
    "username": "alice",
    "age": 34,
    "role": "viewer",
}
# --8<-- [end:functional-api]

# --8<-- [start:output-model]
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    age: int


class UserOutputTable(RowTable):
    output_model = User

    username = field("username", required=True)
    age = field("age", parser=integer())


records = UserOutputTable.parse(datatable)
public_users = UserOutputTable.parse_as(datatable)

assert public_users == [User(username="alice", age=34)]
assert isinstance(records[0], UserOutputTable)
# --8<-- [end:output-model]

# --8<-- [start:output-model-output]
>> public_users
[User(username='alice', age=34)]

>> records[0]
UserOutputTable(username='alice', age=34)
# --8<-- [end:output-model-output]

# --8<-- [start:collect-step]
class StrictUserTable(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())


@given("the strict users exist:", target_fixture="users")
def strict_users(datatable, talika):
    return talika.parse(
        datatable,
        schema=StrictUserTable,
        error_mode="collect",
    )
# --8<-- [end:collect-step]

# --8<-- [start:collect-error]
StrictUserTable.parse(
    [
        ["username", "age"],
        ["", "old"],
    ],
    error_mode="collect",
)
# --8<-- [end:collect-error]

# --8<-- [start:collect-error-output]
Table contains 2 errors:
  1. Required field has an empty value 
  (code=empty_required, schema=StrictUserTable, field='username', 
  row=2, column=1, value=''). 
  Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
  2. Field parser failed: invalid literal for int() with base 10: 'old' 
  (code=parser_failed, schema=StrictUserTable, field='age', 
  row=2, column=2, value='old'). 
  Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:collect-error-output]

# --8<-- [start:shared-context-step]
import pytest

@pytest.fixture
def parser_context():
    return {"prefix": "DEV-"}


@given("the dev users exist:", target_fixture="users")
def dev_users(datatable, talika, parser_context):
    return talika.parse(
        datatable,
        schema=ContextUserTable,
        context=parser_context,
    )
# --8<-- [end:shared-context-step]
