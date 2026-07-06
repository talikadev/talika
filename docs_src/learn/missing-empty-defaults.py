# --8<-- [start:missing-column]
Given the users exist
  | name | role  |
  | Mira | admin |
# --8<-- [end:missing-column]

# --8<-- [start:empty-cell]
Given the users exist
  | name | role  | active |
  | Mira | admin |        |
# --8<-- [end:empty-cell]

# --8<-- [start:contract]
from talika import RowTable, boolean, field


class UserTable(RowTable):
    name = field("name", required=True)
    role = field("role", required=True)
    active = field("active", parser=boolean(), default=True)
# --8<-- [end:contract]

# --8<-- [start:explicit-none]
from talika import optional, string


nickname = field("nickname", parser=optional(string(strip=True)))
# --8<-- [end:explicit-none]
