# --8<-- [start:feature-users]
Given the users exist
  | username | email             | role  | active |
  | alice    | alice@example.com | admin | true   |
  | bob      | bob@example.com   |       | false  |
# --8<-- [end:feature-users]

# --8<-- [start:contract-basic]
from talika import RowTable, boolean, field, integer


class UserFields(RowTable):
    username = field(required=True)
    email = field(required=True)
    role = field(default="viewer")
    active = field(parser=boolean(), default=True)
# --8<-- [end:contract-basic]

# --8<-- [start:subclass-contract]
class BaseUsers(RowTable):
    name = field("name")


class ImportedUsers(BaseUsers):
    name = field("Full name")
# --8<-- [end:subclass-contract]

# --8<-- [start:parse-basic]
users = UserFields.parse(
    [
        ["username", "email", "role", "active"],
        ["alice", "alice@example.com", "admin", "true"],
        ["bob", "bob@example.com", "", "false"],
    ]
)

assert users[0].username == "alice"
assert users[0].role == "admin"
assert users[0].active is True

assert users[1].role == ""
assert users[1].active is False
# --8<-- [end:parse-basic]

# --8<-- [start:parsed-output]
>> users[0]
UserFields(username='alice', email='alice@example.com', role='admin', active=True)

>> users[1].as_dict()
{'username': 'bob', 'email': 'bob@example.com', 'role': '', 'active': False}
# --8<-- [end:parsed-output]

# --8<-- [start:missing-required]
UserFields.parse(
    [
        ["email", "active"],
        ["alice@example.com", "true"],
    ]
)
# --8<-- [end:missing-required]

# --8<-- [start:missing-required-output]
Required field is missing from the table 
(code=missing_required, schema=UserFields, field='username'). 
Hint: Add this field to the table, or make the schema field optional if the project should supply it.
# --8<-- [end:missing-required-output]

# --8<-- [start:empty-required]
UserFields.parse(
    [
        ["username", "email", "active"],
        ["", "alice@example.com", "true"],
    ]
)
# --8<-- [end:empty-required]

# --8<-- [start:empty-required-output]
Required field has an empty value 
(code=empty_required, schema=UserFields, field='username', 
row=2, column=1, value=''). 
Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:empty-required-output]

# --8<-- [start:defaults-contract]
def default_team(context):
    return context.user_data["team"]


class UserDefaults(RowTable):
    username = field("username", required=True)
    role = field("role", default="viewer")
    team = field("team", default_factory=default_team)
# --8<-- [end:defaults-contract]

# --8<-- [start:defaults-parse]
users = UserDefaults.parse(
    [
        ["username"],
        ["alice"],
    ],
    context={"team": "payments"},
)

assert users[0].role == "viewer"
assert users[0].team == "payments"
# --8<-- [end:defaults-parse]

# --8<-- [start:defaults-empty]
users = UserDefaults.parse(
    [
        ["username", "role"],
        ["alice", ""],
    ],
    context={"team": "payments"},
)

assert users[0].role == ""
# --8<-- [end:defaults-empty]

# --8<-- [start:parser-contract]
class AccountFields(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    active = field("active", parser=boolean(), default=True)
# --8<-- [end:parser-contract]

# --8<-- [start:parser-parse]
accounts = AccountFields.parse(
    [
        ["username", "age", "active"],
        ["alice", "34", "true"],
    ]
)

assert accounts[0].age == 34
assert accounts[0].active is True
# --8<-- [end:parser-parse]

# --8<-- [start:parser-error]
AccountFields.parse(
    [
        ["username", "age"],
        ["alice", "thirty four"],
    ]
)
# --8<-- [end:parser-error]

# --8<-- [start:parser-error-output]
Field parser failed: invalid literal for int() with base 10: 'thirty four' 
(code=parser_failed, schema=AccountFields, field='age', 
row=2, column=2, value='thirty four'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:parser-error-output]

# --8<-- [start:aliases-contract]
class LegacyUserFields(RowTable):
    name = field(
        "name",
        aliases=("full name", "display name"),
        required=True,
    )
# --8<-- [end:aliases-contract]

# --8<-- [start:aliases-parse]
users = LegacyUserFields.parse(
    [
        ["full name"],
        ["Alice Doe"],
    ]
)

assert users[0].name == "Alice Doe"
# --8<-- [end:aliases-parse]

# --8<-- [start:duplicate-alias]
LegacyUserFields.parse(
    [
        ["name", "full name"],
        ["Alice", "Alice Doe"],
    ]
)
# --8<-- [end:duplicate-alias]

# --8<-- [start:duplicate-alias-output]
Table contains both a field label and one of its aliases 
(code=duplicate_label, schema=LegacyUserFields, field='name', 
row=1, column=2, value='full name'). 
Hint: Use either the canonical label or one alias, not both in the same table.
# --8<-- [end:duplicate-alias-output]

# --8<-- [start:unknown-field]
UserFields.parse(
    [
        ["username", "team"],
        ["alice", "payments"],
    ]
)
# --8<-- [end:unknown-field]

# --8<-- [start:unknown-field-output]
Unknown field label 
(code=unknown_field, schema=UserFields, field='team', 
row=1, column=2, value='team'). 
Hint: Use one of the schema field labels or aliases.
# --8<-- [end:unknown-field-output]

# --8<-- [start:unknown-policy-error]
class InvalidTable(RowTable):
    unknown_fields = "ignore"
    value = field("value")
# --8<-- [end:unknown-policy-error]

# --8<-- [start:unknown-policy-output]
unknown_fields must be 'forbid' (schema=InvalidTable)
# --8<-- [end:unknown-policy-output]

# --8<-- [start:empty-policies-contract]
def parse_blank(value, context):
    return "<blank>" if value == "" else value


class EmptyPolicyFields(RowTable):
    raw_value = field("raw value", empty="raw")
    parsed_value = field("parsed value", parser=parse_blank, empty="parse")
    none_value = field("none value", empty="none")
    strict_value = field("strict value", empty="error")
# --8<-- [end:empty-policies-contract]

# --8<-- [start:empty-policies-parse]
record = EmptyPolicyFields.parse(
    [
        ["raw value", "parsed value", "none value"],
        ["", "", ""],
    ]
)[0]

assert record.raw_value == ""
assert record.parsed_value == "<blank>"
assert record.none_value is None
# --8<-- [end:empty-policies-parse]

# --8<-- [start:empty-policies-output]
>> record.as_dict()
{'raw_value': '', 'parsed_value': '<blank>', 'none_value': None, 'strict_value': None}
# --8<-- [end:empty-policies-output]

# --8<-- [start:empty-strict]
EmptyPolicyFields.parse(
    [
        ["strict value"],
        [""],
    ]
)
# --8<-- [end:empty-strict]

# --8<-- [start:empty-strict-output]
Optional field has an empty value 
(code=empty_optional, schema=EmptyPolicyFields, field='strict value', 
row=2, column=1, value=''). 
Hint: Fill the cell, omit the field, or choose a different empty-cell policy for this schema field.
# --8<-- [end:empty-strict-output]

# --8<-- [start:id-contract]
from talika import id_field


class IdentifiedUserFields(RowTable):
    user_id = id_field("user id")
    name = field("name", required=True)
    role = field("role", default="viewer")
# --8<-- [end:id-contract]

# --8<-- [start:id-error]
IdentifiedUserFields.parse(
    [
        ["user id", "name"],
        ["U-1", ""],
    ]
)
# --8<-- [end:id-error]

# --8<-- [start:id-error-output]
Required field has an empty value 
(code=empty_required, schema=IdentifiedUserFields, field='name', 
row=2, column=2, item_id='U-1', value=''). 
Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.
# --8<-- [end:id-error-output]

# --8<-- [start:literal-label]
class ArticleFields(RowTable):
    headline = field("Headline*", required=True)
# --8<-- [end:literal-label]

# --8<-- [start:case-sensitivity-error]
class CaseSensitiveTable(RowTable):
    username = field("username", required=True)
# --8<-- [end:case-sensitivity-error]
