# --8<-- [start:feature-basic]
Given imported users exist
  | user id | username |
  | U-1     | Alice    |
# --8<-- [end:feature-basic]

# --8<-- [start:parser-signature]
def parse_value(value, context):
    ...
# --8<-- [end:parser-signature]

# --8<-- [start:basic-contract]
from talika import RowTable, field, id_field


seen_context = []


def parse_username(value, context):
    seen_context.append(
        {
            "schema": context.schema.__name__,
            "field_name": context.field_name,
            "field_label": context.field_label,
            "row": context.row,
            "column": context.column,
            "item_id": context.item_id,
            "source_value": context.source_value,
        }
    )
    prefix = context.user_data["prefix"]
    return f"{prefix}-{context.item_id}-{value.strip().lower()}"


class ImportUsers(RowTable):
    user_id = id_field("user id")
    username = field("username", parser=parse_username)
# --8<-- [end:basic-contract]

# --8<-- [start:basic-parse]
users = ImportUsers.parse(
    [
        ["user id", "username"],
        ["U-1", " Alice "],
    ],
    context={"prefix": "import"},
)

assert users[0].username == "import-U-1-alice"
assert seen_context[0]["item_id"] == "U-1"
assert seen_context[0]["source_value"] == " Alice "
# --8<-- [end:basic-parse]

# --8<-- [start:basic-output]
>> users[0]
ImportUsers(user_id='U-1', username='import-U-1-alice')

>> seen_context[0]
{'schema': 'ImportUsers', 'field_name': 'username', 'field_label': 'username', 'row': 2, 'column': 2, 'item_id': 'U-1', 'source_value': ' Alice '}
# --8<-- [end:basic-output]

# --8<-- [start:role-contract]
def parse_role(value, context):
    aliases = context.user_data.get("role_aliases", {})
    allowed_roles = context.user_data["allowed_roles"]
    normalized = str(value).strip().lower()
    role = aliases.get(normalized, normalized)
    if role not in allowed_roles:
        raise ValueError(f"{role!r} is not allowed for {context.field_label}")
    return role


class RoleImport(RowTable):
    email = field("email", required=True)
    role = field("role", parser=parse_role, required=True)
# --8<-- [end:role-contract]

# --8<-- [start:role-parse]
records = RoleImport.parse(
    [
        ["email", "role"],
        ["a@example.com", "Administrator"],
    ],
    context={
        "allowed_roles": {"admin", "editor", "viewer"},
        "role_aliases": {"administrator": "admin"},
    },
)

assert records[0].role == "admin"
# --8<-- [end:role-parse]

# --8<-- [start:role-output]
>> records[0].as_dict()
{'email': 'a@example.com', 'role': 'admin'}
# --8<-- [end:role-output]

# --8<-- [start:role-error]
RoleImport.parse(
    [
        ["email", "role"],
        ["a@example.com", "owner"],
    ],
    context={
        "allowed_roles": {"admin", "editor", "viewer"},
        "role_aliases": {"administrator": "admin"},
    },
)
# --8<-- [end:role-error]

# --8<-- [start:role-error-output]
Field parser failed: 'owner' is not allowed for role 
(code=parser_failed, schema=RoleImport, field='role', 
row=2, column=2, value='owner'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:role-error-output]

# --8<-- [start:percent-contract]
def parse_percent(value, context):
    text = str(value).strip()
    if not text.endswith("%"):
        raise ValueError("expected a percent value such as '95%'")
    number = int(text[:-1])
    if not 0 <= number <= 100:
        raise ValueError("percent must be between 0 and 100")
    return number / 100


class Metrics(RowTable):
    success_rate = field("success rate", parser=parse_percent)
# --8<-- [end:percent-contract]

# --8<-- [start:percent-parse]
metric = Metrics.parse(
    [
        ["success rate"],
        ["95%"],
    ]
)[0]

assert metric.success_rate == 0.95
# --8<-- [end:percent-parse]

# --8<-- [start:percent-output]
>> metric.as_dict()
{'success_rate': 0.95}
# --8<-- [end:percent-output]

# --8<-- [start:percent-error]
Metrics.parse(
    [
        ["success rate"],
        ["110%"],
    ]
)
# --8<-- [end:percent-error]

# --8<-- [start:percent-error-output]
Field parser failed: percent must be between 0 and 100 
(code=parser_failed, schema=Metrics, field='success rate', 
row=2, column=1, value='110%'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:percent-error-output]

# --8<-- [start:empty-contract]
def parse_blank(value, context):
    return "<blank>" if value == "" else value


class EmptyAware(RowTable):
    normal = field("normal", parser=parse_blank)
    parsed_empty = field("parsed empty", parser=parse_blank, empty="parse")
# --8<-- [end:empty-contract]

# --8<-- [start:empty-parse]
record = EmptyAware.parse(
    [
        ["normal", "parsed empty"],
        ["", ""],
    ]
)[0]

assert record.normal == ""
assert record.parsed_empty == "<blank>"
# --8<-- [end:empty-parse]

# --8<-- [start:empty-output]
>> record.as_dict()
{'normal': '', 'parsed_empty': '<blank>'}
# --8<-- [end:empty-output]

# --8<-- [start:bad-signature]
def bad_parser(value):
    return value


class BadSignature(RowTable):
    value = field("value", parser=bad_parser)


BadSignature.parse(
    [
        ["value"],
        ["x"],
    ]
)
# --8<-- [end:bad-signature]

# --8<-- [start:bad-signature-output]
Field parser failed: bad_parser() takes 1 positional argument but 2 were given 
(code=parser_failed, schema=BadSignature, field='value', 
row=2, column=1, value='x'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:bad-signature-output]

# --8<-- [start:source-value]
def require_poll(value, context):
    if value != "Poll":
        raise ValueError(
            f"expected Poll after transformation; original cell was {context.source_value!r}"
        )
    return value
# --8<-- [end:source-value]
