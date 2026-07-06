# --8<-- [start:feature-basic]
Given the users exist
  | username | email             | active |
  | alice    | alice@example.com | true   |
  | bob      | bob@example.com   | false  |
# --8<-- [end:feature-basic]

# --8<-- [start:datatable-basic]
datatable = [
    ["username", "email", "active"],
    ["alice", "alice@example.com", "true"],
    ["bob", "bob@example.com", "false"],
]
# --8<-- [end:datatable-basic]

# --8<-- [start:contract-basic]
from talika import RowTable, boolean, field


class UserTable(RowTable):
    username = field("username", required=True)
    email = field("email", required=True)
    active = field("active", parser=boolean(), required=True)
# --8<-- [end:contract-basic]

# --8<-- [start:parse-basic]
users = UserTable.parse(datatable)

assert users[0].username == "alice"
assert users[0].email == "alice@example.com"
assert users[0].active is True
assert users[1].active is False
# --8<-- [end:parse-basic]

# --8<-- [start:record-output]
>> users[0]
UserTable(username='alice', email='alice@example.com', active=True)

>> users[0].as_dict()
{'username': 'alice', 'email': 'alice@example.com', 'active': True}
# --8<-- [end:record-output]

# --8<-- [start:required-missing]
UserTable.parse(
    [
        ["username", "email"],
        ["alice", "alice@example.com"],
    ]
)
# --8<-- [end:required-missing]

# --8<-- [start:required-missing-output]
Required field is missing from the table 
(code=missing_required, schema=UserTable, field='active'). 
Hint: Add this field to the table, or make the schema field optional if the project should supply it.
# --8<-- [end:required-missing-output]

# --8<-- [start:required-empty]
UserTable.parse(
    [
        ["username", "email", "active"],
        ["", "alice@example.com", "true"],
    ]
)
# --8<-- [end:required-empty]

# --8<-- [start:required-empty-output]
Required field has an empty value 
(code=empty_required, schema=UserTable, field='username', 
row=2, column=1, value=''). 
Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:required-empty-output]

# --8<-- [start:defaults-contract]
def default_team(context):
    return context.user_data["team"]


class UserWithDefaults(RowTable):
    username = field("username", required=True)
    role = field("role", default="viewer")
    team = field("team", default_factory=default_team)
# --8<-- [end:defaults-contract]

# --8<-- [start:defaults-parse]
users = UserWithDefaults.parse(
    [
        ["username"],
        ["alice"],
    ],
    context={"team": "platform"},
)

assert users[0].role == "viewer"
assert users[0].team == "platform"
# --8<-- [end:defaults-parse]

# --8<-- [start:empty-is-present]
users = UserWithDefaults.parse(
    [
        ["username", "role"],
        ["alice", ""],
    ],
    context={"team": "platform"},
)

assert users[0].role == ""
# --8<-- [end:empty-is-present]

# --8<-- [start:id-contract]
from talika import id_field


seen_item_ids = []


def parse_display_name(value, context):
    seen_item_ids.append(context.item_id)
    return value.strip().title()


def default_audit_name(context):
    return f"audit-{context.item_id}"


class UserWithId(RowTable):
    display_name = field("display name", parser=parse_display_name)
    user_id = id_field("user id")
    audit_name = field("audit name", default_factory=default_audit_name)
# --8<-- [end:id-contract]

# --8<-- [start:id-parse]
users = UserWithId.parse_records(
    [
        ["display name", "user id"],
        ["alice rao", "U-100"],
    ]
)

assert seen_item_ids == ["U-100"]
assert users[0].display_name == "Alice Rao"
assert users[0].audit_name == "audit-U-100"
assert users[0].table_source.item_id == "U-100"
# --8<-- [end:id-parse]

# --8<-- [start:id-error]
def parse_status(value, context):
    raise ValueError("unsupported status")


class StatusTable(RowTable):
    status = field("status", parser=parse_status)
    user_id = id_field("user id")


StatusTable.parse(
    [
        ["status", "user id"],
        ["blocked", "U-500"],
    ]
)
# --8<-- [end:id-error]

# --8<-- [start:id-error-output]
Field parser failed: unsupported status 
(code=parser_failed, schema=StatusTable, field='status', 
row=2, column=1, item_id='U-500', value='blocked'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:id-error-output]

# --8<-- [start:ragged-row]
UserTable.parse(
    [
        ["username", "email", "active"],
        ["alice", "alice@example.com"],
    ]
)
# --8<-- [end:ragged-row]

# --8<-- [start:ragged-row-output]
Ragged row: expected 3 cells, got 2 
(code=ragged_row, schema=UserTable, row=2). 
Hint: Make every data row contain the same number of cells as the header row.
# --8<-- [end:ragged-row-output]

# --8<-- [start:record-metadata]
# Access row metadata
row_number = users[0].table_source.row
assert row_number == 2

# Access a specific cell's source metadata
cell = users[0].source_for("email")
assert cell.value == "alice@example.com"
assert cell.source_row == 2
assert cell.source_column == 2
assert cell.source_value == "alice@example.com"
# --8<-- [end:record-metadata]

# --8<-- [start:record-metadata-output]
>> users[0].table_source.row
2

>> cell = users[0].source_for("email")
>> cell.source_column
2
# --8<-- [end:record-metadata-output]

