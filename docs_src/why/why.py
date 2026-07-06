# --8<-- [start:a]
headers, *rows = datatable

users = []
for row in rows:
    raw = dict(zip(headers, row, strict=True))
    users.append({
        "name": raw["name"],
        "age": int(raw["age"]),
        "active": raw["active"].lower() in {"true", "yes", "1"},
    })
# --8<-- [end:a]

# --8<-- [start:b]
    Given The following users are present
      | name  | age | roles               | active |
      | Akash | 27  | Developer,Manager   | Yes    |
      | Badal | 25  | Tester,Scrum Master | No     |
# --8<-- [end:b]


# --8<-- [start:c]
from talika import RowTable, boolean, field, split


class UserTable(RowTable):# (1)!
    name = field("name", required=True) # (2)!
    age: int = field("age") # (3)!
    roles = field("roles", parser=split(",")) # (4)!
    active = field("active", parser=boolean(), default=True) # (5)!


users = UserTable.parse(datatable) # (6)!
# --8<-- [end:c]

# --8<-- [start:d]
>> users
[
    UserTable(name='Akash', age=27, roles=['Developer', 'Manager'], active=True), 
    UserTable(name='Badal', age=25, roles=['Tester', 'Scrum Master'], active=False)
]


>> users[0]
UserTable(name='Akash', age=27, roles=['Developer', 'Manager'], active=True)


>> users[0].name
'Akash'


>> users[0].age
27


>> type(users[0].age)
<class 'int'>


>> users[0].roles
['Developer', 'Manager']
# --8<-- [end:d]

# --8<-- [start:e]

from talika import ColumnGroupExpander, NumericRange, PrefixRepeat


table_transformer = ColumnGroupExpander(
    key_row="IDs",
    range_rule=NumericRange("-"),
    repeat_rule=PrefixRepeat(" "),
)

# --8<-- [end:e]

# --8<-- [start:f]
Given the following Content is created
| IDs  | 1-3        |
| Type | 3 Articles |

# --8<-- [end:f]


# --8<-- [start:g]
from talika import CellDSL


cells = CellDSL()


@cells.token("random", fields=("headline",))
def random_headline(context):
    return context.user_data["faker"].headline()


@cells.pattern(r"(?P<count>\d+) words", fields=("body",))
def generated_words(match, context):
    return context.user_data["faker"].words(int(match["count"]))

# --8<-- [end:g]


# --8<-- [start:h]
records = UserTable.parse_records(datatable)

users = [
    UserFactory(**record.as_dict())
    for record in records
]

# --8<-- [end:h]

# --8<-- [start:i]
from pydantic import BaseModel
from talika import RowTable, field


class User(BaseModel):
    name: str
    age: int


class UserTable(RowTable):
    output_model = User

    name = field("name", required=True)
    age: int = field("age")


users: list[User] = UserTable.parse(datatable)

# --8<-- [end:i]