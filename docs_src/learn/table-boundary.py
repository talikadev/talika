# --8<-- [start:gherkin]
Given the account holders exist
  | name | age | verified |
  | Mira | 34  | yes      |
# --8<-- [end:gherkin]

# --8<-- [start:datatable]
datatable = [
    ["name", "age", "verified"],
    ["Mira", "34", "yes"],
]
# --8<-- [end:datatable]

# --8<-- [start:desired]
AccountHolder(name="Mira", age=34, verified=True)
# --8<-- [end:desired]

# --8<-- [start:boundary]
from talika import RowTable, boolean, field


class AccountHolderTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)
    verified = field("verified", parser=boolean(), default=False)


holders = AccountHolderTable.parse(datatable)
# --8<-- [end:boundary]
