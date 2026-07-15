# --8<-- [start:feature]
Given the users exist
  | name  | age | roles              | active |
  | Akash | 27  | Developer, Manager | true   |
  | Badal | 25  | Tester             | false  |
# --8<-- [end:feature]

# --8<-- [start:datatable]
datatable = [
    ["name", "age", "roles", "active"],
    ["Akash", "27", "Developer, Manager", "true"],
    ["Badal", "25", "Tester", "false"],
]
# --8<-- [end:datatable]

# --8<-- [start:contract]
from talika import RowTable, boolean, field, split


class UserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)
    roles = field("roles", parser=split(","))
    active = field("active", parser=boolean(), default=True)
# --8<-- [end:contract]

# --8<-- [start:parse]
users = UserTable.parse(datatable)

assert users[0].name == "Akash"
assert users[0].age == 27
assert users[0].roles == ["Developer", "Manager"]
assert users[0].active is True
# --8<-- [end:parse]

# --8<-- [start:complete]
from pprint import pprint

from talika import RowTable, boolean, field, split


class UserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)
    roles = field("roles", parser=split(","))
    active = field("active", parser=boolean(), default=True)


datatable = [
    ["name", "age", "roles", "active"],
    ["Akash", "27", "Developer, Manager", "true"],
    ["Badal", "25", "Tester", "false"],
]

users = UserTable.parse(datatable)

pprint(users)
print(users[0].as_dict())
print(type(users[0].age))
# --8<-- [end:complete]

# --8<-- [start:complete-output]
$ python users_table.py
[UserTable(name='Akash', age=27, roles=['Developer', 'Manager'], active=True),
 UserTable(name='Badal', age=25, roles=['Tester'], active=False)]
{'name': 'Akash', 'age': 27, 'roles': ['Developer', 'Manager'], 'active': True}
<class 'int'>
# --8<-- [end:complete-output]

# --8<-- [start:missing-active]
minimal_datatable = [
    ["name", "age", "roles"],
    ["Chinmay", "30", "Developer"],
]

users = UserTable.parse(minimal_datatable)

assert users[0].active is True
# --8<-- [end:missing-active]

# --8<-- [start:output-model]
from dataclasses import dataclass

from talika import RowTable, field


@dataclass(frozen=True)
class User:
    name: str
    age: int


class UserTable(RowTable):
    output_model = User

    name = field("name", required=True)
    age: int = field("age", required=True)


datatable = [
    ["name", "age"],
    ["Akash", "27"],
]

records = UserTable.parse(datatable)
users = UserTable.parse_as(datatable)

assert isinstance(records[0], UserTable)
assert records[0].as_dict() == {"name": "Akash", "age": 27}
assert users == [User(name="Akash", age=27)]
# --8<-- [end:output-model]

# --8<-- [start:parse-records-source]
record = records[0]
name_cell = record.source_for("name")

assert name_cell.source_row == 2
assert name_cell.source_column == 1
assert name_cell.source_value == "Akash"
# --8<-- [end:parse-records-source]

# --8<-- [start:step]
from pytest_bdd import given


@given("the users exist", target_fixture="users")
def users(datatable):
    return UserTable.parse(datatable)
# --8<-- [end:step]

# --8<-- [start:fixture]
@given("the users exist", target_fixture="users")
def users(datatable, talika):
    return talika.parse(datatable, schema=UserTable)
# --8<-- [end:fixture]

# --8<-- [start:bad-table]
bad_datatable = [
    ["name", "age", "roles", "active"],
    ["", "old", "Developer", "maybe"],
]

UserTable.parse(bad_datatable, error_mode="collect")
# --8<-- [end:bad-table]

# --8<-- [start:collect-output]
$ python users_table.py
Table contains 3 errors:
  1. Required field has an empty value (code=empty_required, schema=UserTable, field='name', row=2, column=1, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
  2. Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=UserTable, field='age', row=2, column=2, value='old'). Hint: Check the cell value or adjust the field parser for this syntax.
  3. Field parser failed: Expected one of ['false', 'true'] (code=parser_failed, schema=UserTable, field='active', row=2, column=4, value='maybe'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:collect-output]
