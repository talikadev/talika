# --8<-- [start:gherkin]
Given the users exist
  | name  | role   | active |
  | Asha  | admin  | yes    |
  | Bruno | editor | no     |
# --8<-- [end:gherkin]

# --8<-- [start:datatable]
[
    ["name", "role", "active"],
    ["Asha", "admin", "yes"],
    ["Bruno", "editor", "no"],
]
# --8<-- [end:datatable]

# --8<-- [start:manual-python]
headers, *rows = datatable

users = []
for row in rows:
    values = dict(zip(headers, row, strict=True))
    users.append(
        {
            "name": values["name"],
            "role": values["role"],
            "active": values["active"].lower() in {"yes", "true", "1"},
        }
    )
# --8<-- [end:manual-python]

# --8<-- [start:surprise]
bool("no")
# True
# --8<-- [end:surprise]
