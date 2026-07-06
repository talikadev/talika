# --8<-- [start:record]
users = UserTable.parse(datatable)

assert users[0].name == "Mira"
assert users[0].age == 34
assert users[0].as_dict() == {"name": "Mira", "age": 34}
# --8<-- [end:record]

# --8<-- [start:factory]
records = UserTable.parse_records(datatable)

created_users = [UserFactory(**record.as_dict()) for record in records]
# --8<-- [end:factory]

# --8<-- [start:dataclass-output]
from dataclasses import dataclass

from talika import RowTable, field


@dataclass(frozen=True)
class User:
    name: str
    age: int


class UserTable(RowTable):
    output_model = User

    name = field("name", required=True)
    age: int = field("age")


# --8<-- [end:dataclass-output]

# --8<-- [start:parse-vs-records]
users = UserTable.parse(datatable)
records = UserTable.parse_records(datatable)

assert users[0] == User(name="Mira", age=34)
assert records[0].source_for("name").source_value == "Mira"
# --8<-- [end:parse-vs-records]
