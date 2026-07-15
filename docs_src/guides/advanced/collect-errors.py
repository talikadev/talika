# --8<-- [start:feature-import]
Feature: Imported users

  Scenario: Review an authored users table
    Given the imported users:
      | username | age | role  |
      |          | old | admin |
      | sam      | 41  |       |
    Then the table diagnostics should be clear
# --8<-- [end:feature-import]

# --8<-- [start:schema]
from talika import RowTable, TableErrors, field, integer


class ImportedUserTable(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    role = field("role", required=True)
# --8<-- [end:schema]

# --8<-- [start:bad-table]
bad_users = [
    ["username", "age", "role"],
    ["", "old", "admin"],
    ["sam", "41", ""],
]
# --8<-- [end:bad-table]

# --8<-- [start:fail-fast-call]
ImportedUserTable.parse(bad_users)
# --8<-- [end:fail-fast-call]

# --8<-- [start:fail-fast-output]
Required field has an empty value (code=empty_required, schema=ImportedUserTable, field='username', row=2, column=1, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:fail-fast-output]

# --8<-- [start:collect-call]
ImportedUserTable.parse(bad_users, error_mode="collect")
# --8<-- [end:collect-call]

# --8<-- [start:collect-output]
Table contains 3 errors:
  1. Required field has an empty value (code=empty_required, schema=ImportedUserTable, field='username', row=2, column=1, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
  2. Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=ImportedUserTable, field='age', row=2, column=2, value='old'). Hint: Check the cell value or adjust the field parser for this syntax.
  3. Required field has an empty value (code=empty_required, schema=ImportedUserTable, field='role', row=3, column=3, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:collect-output]

# --8<-- [start:inspect-errors]
collected = None

try:
    ImportedUserTable.parse(bad_users, error_mode="collect")
except TableErrors as exc:
    collected = exc

if collected is not None:
    diagnostics = [
        {
            "code": error.code,
            "field": error.field,
            "row": error.row,
            "column": error.column,
            "value": error.value,
        }
        for error in collected
    ]
# --8<-- [end:inspect-errors]

# --8<-- [start:inspect-errors-output]
>> len(collected)
3

>> diagnostics[0]
{'code': 'empty_required', 'field': 'username', 'row': 2, 'column': 1, 'value': ''}

>> diagnostics[1]
{'code': 'parser_failed', 'field': 'age', 'row': 2, 'column': 2, 'value': 'old'}
# --8<-- [end:inspect-errors-output]

# --8<-- [start:entrypoints]
from talika import parse_table, parse_table_as


ImportedUserTable.parse(bad_users, error_mode="collect")
ImportedUserTable.parse_as(bad_users, dict, error_mode="collect")

parse_table(ImportedUserTable, bad_users, error_mode="collect")
parse_table_as(ImportedUserTable, bad_users, dict, error_mode="collect")


def imported_users(datatable, talika):
    return talika.parse(
        datatable,
        schema=ImportedUserTable,
        error_mode="collect",
    )
# --8<-- [end:entrypoints]

# --8<-- [start:boundary-schema]
class AccountTable(RowTable):
    email = field("email", required=True)
    age = field("age", parser=integer())

    def validate_record(self, context):
        if "@" not in self.email:
            raise ValueError("email must contain @")
# --8<-- [end:boundary-schema]

# --8<-- [start:boundary-call]
AccountTable.parse(
    [
        ["email", "age"],
        ["bad-email", "old"],
        ["still-bad", "31"],
    ],
    error_mode="collect",
)
# --8<-- [end:boundary-call]

# --8<-- [start:boundary-output]
Table contains 1 errors:
  1. Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=AccountTable, field='age', row=2, column=2, value='old'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:boundary-output]

# --8<-- [start:validation-schema]
from talika import ColumnTable, id_field


class ScoreTable(ColumnTable):
    id = id_field("IDs")
    score = field("Score", parser=integer())

    def validate_record(self, context):
        if self.score < 0:
            raise ValueError("score cannot be negative")
# --8<-- [end:validation-schema]

# --8<-- [start:validation-call]
ScoreTable.parse(
    [
        ["IDs", "S-1", "S-2", "S-3"],
        ["Score", "-1", "10", "-5"],
    ],
    error_mode="collect",
)
# --8<-- [end:validation-call]

# --8<-- [start:validation-output]
Table contains 2 errors:
  1. Record validation failed: score cannot be negative (code=record_validation_failed, schema=ScoreTable, column=2, item_id='S-1')
  2. Record validation failed: score cannot be negative (code=record_validation_failed, schema=ScoreTable, column=4, item_id='S-3')
# --8<-- [end:validation-output]
