# --8<-- [start:feature-users]
Feature: User setup

  Scenario: Build project users from a table
    Given the users:
      | username | age | role  |
      | alice    | 34  | admin |
    Then the test can use project user objects
# --8<-- [end:feature-users]

# --8<-- [start:record-schema]
from talika import RowTable, field, integer


class UserRecordTable(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    role = field("role", default="reader")
# --8<-- [end:record-schema]

# --8<-- [start:user-table]
users_table = [
    ["username", "age", "role"],
    ["alice", "34", "admin"],
]
# --8<-- [end:user-table]

# --8<-- [start:record-output]
>> UserRecordTable.parse(users_table)
[UserRecordTable(username='alice', age=34, role='admin')]

>> UserRecordTable.parse(users_table)[0].as_dict()
{'username': 'alice', 'age': 34, 'role': 'admin'}
# --8<-- [end:record-output]

# --8<-- [start:dataclass-model]
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    username: str
    age: int
    role: str


class UserTable(RowTable):
    output_model = User

    username = field("username", required=True)
    age = field("age", parser=integer())
    role = field("role", default="reader")
# --8<-- [end:dataclass-model]

# --8<-- [start:default-model-call]
User(**record.as_dict())
# --8<-- [end:default-model-call]

# --8<-- [start:parse-vs-records]
source_records = UserTable.parse(users_table)
public_users = UserTable.parse_as(users_table)
# --8<-- [end:parse-vs-records]

# --8<-- [start:parse-vs-records-output]
>> public_users
[User(username='alice', age=34, role='admin')]

>> source_records
[UserTable(username='alice', age=34, role='admin')]

>> type(public_users[0]).__name__
'User'

>> type(source_records[0]).__name__
'UserTable'
# --8<-- [end:parse-vs-records-output]

# --8<-- [start:one-call-output-model]
users = UserTable.parse_as(users_table, User)
# --8<-- [end:one-call-output-model]

# --8<-- [start:source-records]
record = UserTable.parse(users_table)[0]

age_source = record.source_for("age")

assert record.age == 34
assert age_source.source_value == "34"
assert age_source.source_row == 2
assert age_source.source_column == 2
# --8<-- [end:source-records]

# --8<-- [start:validation-before-output]
@dataclass(frozen=True)
class AdultUser:
    username: str
    age: int


class AdultUserTable(RowTable):
    output_model = AdultUser

    username = field("username", required=True)
    age = field("age", parser=integer())

    def validate_record(self, context):
        if self.age < 18:
            raise ValueError("user must be an adult")
# --8<-- [end:validation-before-output]

# --8<-- [start:validation-before-output-call]
AdultUserTable.parse_as(
    [
        ["username", "age"],
        ["kai", "16"],
    ]
)
# --8<-- [end:validation-before-output-call]

# --8<-- [start:validation-before-output-result]
Record validation failed: user must be an adult (code=record_validation_failed, schema=AdultUserTable, row=2)
# --8<-- [end:validation-before-output-result]

# --8<-- [start:custom-builder]
class DisplayUserTable(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())

    @classmethod
    def build_output(cls, record, context):
        prefix = context.user_data.get("prefix", "")
        return {
            "label": f"{prefix}{record.username}",
            "adult": record.age >= 18,
        }
# --8<-- [end:custom-builder]

# --8<-- [start:custom-builder-call]
DisplayUserTable.parse_as(
    [
        ["username", "age"],
        ["alice", "34"],
    ],
    context={"prefix": "QA-"},
)
# --8<-- [end:custom-builder-call]

# --8<-- [start:custom-builder-output]
[{'label': 'QA-alice', 'adult': True}]
# --8<-- [end:custom-builder-output]

# --8<-- [start:output-error]
@dataclass(frozen=True)
class StrictUser:
    username: str
    age: int

    def __post_init__(self):
        if self.username == "blocked":
            raise ValueError("blocked user cannot be exported")


class StrictUserTable(RowTable):
    output_model = StrictUser

    username = field("username", required=True)
    age = field("age", parser=integer())
# --8<-- [end:output-error]

# --8<-- [start:output-error-call]
StrictUserTable.parse_as(
    [
        ["username", "age"],
        ["blocked", "22"],
    ]
)
# --8<-- [end:output-error-call]

# --8<-- [start:output-error-result]
Output model StrictUser rejected the record: blocked user cannot be exported (code=output_failed, schema=StrictUserTable, row=2)
# --8<-- [end:output-error-result]

# --8<-- [start:pydantic-model]
import pydantic


class UserModel(pydantic.BaseModel):
    username: str
    age: int = pydantic.Field(ge=18)


class PydanticUserTable(RowTable):
    output_model = UserModel

    username = field("username", required=True)
    age = field("age", parser=integer())
# --8<-- [end:pydantic-model]

# --8<-- [start:pydantic-output]
>> PydanticUserTable.parse_as([["username", "age"], ["alice", "34"]])
[UserModel(username='alice', age=34)]
# --8<-- [end:pydantic-output]
