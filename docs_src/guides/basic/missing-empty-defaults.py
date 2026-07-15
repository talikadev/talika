# --8<-- [start:feature-missing]
Given the users exist
  | username |
  | alice    |
# --8<-- [end:feature-missing]

# --8<-- [start:defaults-contract]
from talika import RowTable, field


def default_team(context):
    return context.user_data["team"]


class UserDefaults(RowTable):
    username = field("username", required=True)
    role = field("role", default="viewer")
    team = field("team", default_factory=default_team)
    notes = field("notes")
# --8<-- [end:defaults-contract]

# --8<-- [start:missing-parse]
user = UserDefaults.parse(
    [
        ["username"],
        ["alice"],
    ],
    context={"team": "platform"},
)[0]

assert user.username == "alice"
assert user.role == "viewer"
assert user.team == "platform"
assert user.notes is None
# --8<-- [end:missing-parse]

# --8<-- [start:missing-output]
>> user
UserDefaults(username='alice', role='viewer', team='platform', notes=None)

>> user.as_dict()
{'username': 'alice', 'role': 'viewer', 'team': 'platform', 'notes': None}
# --8<-- [end:missing-output]

# --8<-- [start:empty-present]
user = UserDefaults.parse(
    [
        ["username", "role", "team", "notes"],
        ["alice", "", "", ""],
    ],
    context={"team": "platform"},
)[0]

assert user.role == ""
assert user.team == ""
assert user.notes == ""
# --8<-- [end:empty-present]

# --8<-- [start:empty-present-output]
>> user.as_dict()
{'username': 'alice', 'role': '', 'team': '', 'notes': ''}
# --8<-- [end:empty-present-output]

# --8<-- [start:missing-required]
UserDefaults.parse(
    [
        ["role"],
        ["admin"],
    ],
    context={"team": "platform"},
)
# --8<-- [end:missing-required]

# --8<-- [start:missing-required-output]
Required field is missing from the table 
(code=missing_required, schema=UserDefaults, field='username'). 
Hint: Add this field to the table, or make the schema field optional if the project should supply it.
# --8<-- [end:missing-required-output]

# --8<-- [start:empty-required]
UserDefaults.parse(
    [
        ["username"],
        [""],
    ],
    context={"team": "platform"},
)
# --8<-- [end:empty-required]

# --8<-- [start:empty-required-output]
Required field has an empty value 
(code=empty_required, schema=UserDefaults, field='username', 
row=2, column=1, value=''). 
Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:empty-required-output]

# --8<-- [start:row-factory-contract]
from talika import id_field


def default_audit(context):
    return f"audit-{context.item_id}-{context.user_data['suffix']}"


class RowWithId(RowTable):
    user_id = id_field("user id")
    audit = field("audit", default_factory=default_audit)
# --8<-- [end:row-factory-contract]

# --8<-- [start:row-factory-parse]
record = RowWithId.parse(
    [
        ["user id"],
        ["U-7"],
    ],
    context={"suffix": "qa"},
)[0]

assert record.audit == "audit-U-7-qa"
assert record.table_source.item_id == "U-7"
# --8<-- [end:row-factory-parse]

# --8<-- [start:row-factory-output]
>> record.as_dict()
{'user_id': 'U-7', 'audit': 'audit-U-7-qa'}
# --8<-- [end:row-factory-output]

# --8<-- [start:column-feature]
Given the content exists
  | IDs    | A-1   | P-1 |
  | Status | draft |     |
# --8<-- [end:column-feature]

# --8<-- [start:column-contract]
from talika import ColumnTable


class ContentDefaults(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", default_factory=default_audit)
    status = field("Status")
# --8<-- [end:column-contract]

# --8<-- [start:column-parse]
items = ContentDefaults.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Status", "draft", ""],
    ],
    context={"suffix": "qa"},
)

assert items[0].headline == "audit-A-1-qa"
assert items[0].status == "draft"
assert items[1].headline == "audit-P-1-qa"
assert items[1].status == ""
# --8<-- [end:column-parse]

# --8<-- [start:column-output]
>> [item.as_dict() for item in items]
[
  {'id': 'A-1', 'headline': 'audit-A-1-qa', 'status': 'draft'},
  {'id': 'P-1', 'headline': 'audit-P-1-qa', 'status': ''},
]
# --8<-- [end:column-output]

# --8<-- [start:empty-policies-contract]
from talika import integer


def parse_blank(value, context):
    return "<blank>" if value == "" else value


class EmptyPolicies(RowTable):
    raw_value = field("raw value", parser=integer(), empty="raw")
    parsed_value = field("parsed value", parser=parse_blank, empty="parse")
    none_value = field("none value", empty="none")
    strict_value = field("strict value", empty="error")
# --8<-- [end:empty-policies-contract]

# --8<-- [start:empty-policies-parse]
record = EmptyPolicies.parse(
    [
        ["raw value", "parsed value", "none value"],
        ["", "", ""],
    ]
)[0]

assert record.raw_value == ""
assert record.parsed_value == "<blank>"
assert record.none_value is None
assert record.strict_value is None
# --8<-- [end:empty-policies-parse]

# --8<-- [start:empty-policies-output]
>> record.as_dict()
{'raw_value': '', 'parsed_value': '<blank>', 'none_value': None, 'strict_value': None}
# --8<-- [end:empty-policies-output]

# --8<-- [start:empty-optional-error]
EmptyPolicies.parse(
    [
        ["strict value"],
        [""],
    ]
)
# --8<-- [end:empty-optional-error]

# --8<-- [start:empty-optional-error-output]
Optional field has an empty value 
(code=empty_optional, schema=EmptyPolicies, field='strict value', 
row=2, column=1, value=''). 
Hint: Fill the cell, omit the field, or choose a different empty-cell policy for this schema field.
# --8<-- [end:empty-optional-error-output]

# --8<-- [start:required-parse-empty]
class RequiredValue(RowTable):
    value = field(required=True, parser=parse_blank)


RequiredValue.parse(
    [
        ["value"],
        [""],
    ]
)
# --8<-- [end:required-parse-empty]

# --8<-- [start:required-parse-empty-output]
Required field has an empty value
(code=empty_required, schema=RequiredValue, field='value', row=2, column=1, value='')
# --8<-- [end:required-parse-empty-output]

# --8<-- [start:default-factory-error]
def broken_default(context):
    raise RuntimeError("team service unavailable")


class BrokenDefault(RowTable):
    username = field("username")
    team = field("team", default_factory=broken_default)


BrokenDefault.parse(
    [
        ["username"],
        ["alice"],
    ]
)
# --8<-- [end:default-factory-error]

# --8<-- [start:default-factory-error-output]
Default factory failed: team service unavailable 
(code=default_factory_failed, schema=BrokenDefault, field='team')
# --8<-- [end:default-factory-error-output]

# --8<-- [start:invalid-defaults]
field("value", default="x", default_factory=lambda context: "y")
field("value", required=True, default="x")
# --8<-- [end:invalid-defaults]

# --8<-- [start:invalid-defaults-output]
ValueError: field cannot declare both default and default_factory
ValueError: required fields cannot declare defaults
# --8<-- [end:invalid-defaults-output]
