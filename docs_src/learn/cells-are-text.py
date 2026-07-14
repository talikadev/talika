# --8<-- [start:gherkin]
Given the users exist
  | name | age | active | roles         | state |
  | Mira | 34  | no     | Admin, Editor | draft |
# --8<-- [end:gherkin]

# --8<-- [start:python-values]
[
    ["name", "age", "active", "roles", "state"],
    ["Mira", "34", "no", "Admin, Editor", "draft"],
]
# --8<-- [end:python-values]

# --8<-- [start:bad-guesses]
int("34")       # 34
bool("no")      # True
"Admin, Editor" # still one string
# --8<-- [end:bad-guesses]

# --8<-- [start:contract]
from typing import Literal

from talika import RowTable, boolean, field, split


class UserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age")
    active = field(
        "active",
        parser=boolean(true_values=("yes",), false_values=("no",)),
    )
    roles = field("roles", parser=split(","))
    state: Literal["draft", "published"] = field("state")
# --8<-- [end:contract]
