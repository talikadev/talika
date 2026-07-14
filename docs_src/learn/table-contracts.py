# --8<-- [start:gherkin]
Given the users exist
  | name | age | role   | active |
  | Mira | 34  | admin  | yes    |
  | Leo  | 29  | editor | no     |
# --8<-- [end:gherkin]

# --8<-- [start:contract]
from talika import RowTable, boolean, choice, field


class UserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)
    role = field("role", parser=choice("admin", "editor", "viewer"))
    active = field(
        "active",
        parser=boolean(true_values=("yes",), false_values=("no",)),
        default=True,
    )
# --8<-- [end:contract]

# --8<-- [start:meaning]
users = UserTable.parse(datatable)

assert users[0].name == "Mira"
assert users[0].age == 34
assert users[0].role == "admin"
assert users[0].active is True
# --8<-- [end:meaning]

# --8<-- [start:bad-label]
| full name | age | role  | active |
| Mira      | 34  | admin | yes    |
# --8<-- [end:bad-label]
