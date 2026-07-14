# --8<-- [start:feature-basic]
Given the user roster exists
  | email         | role   | primary |
  | a@example.com | admin  | true    |
  | b@example.com | viewer | false   |
# --8<-- [end:feature-basic]

# --8<-- [start:basic-contract]
from talika import RowTable, TableError, boolean, field


class UserRoster(RowTable):
    email = field("email", required=True)
    role = field("role", default="viewer")
    primary = field("primary", parser=boolean(), default=False)

    @classmethod
    def validate_records(cls, records, context):
        seen = {}
        for record in records:
            if record.email in seen:
                raise TableError.from_cell(
                    "Duplicate email",
                    record.source_for("email"),
                    schema=cls,
                    field="email",
                    hint="Each user row must use a unique email address.",
                )
            seen[record.email] = record

        if not any(record.primary for record in records):
            raise ValueError("At least one primary user is required")

        domain = context.user_data["email_domain"]
        for record in records:
            if not record.email.endswith(f"@{domain}"):
                raise TableError.from_cell(
                    f"Email must belong to {domain}",
                    record.source_for("email"),
                    schema=cls,
                    field="email",
                )
# --8<-- [end:basic-contract]

# --8<-- [start:basic-parse]
users = UserRoster.parse(
    [
        ["email", "role", "primary"],
        ["a@example.com", "admin", "true"],
        ["b@example.com", "viewer", "false"],
    ],
    context={"email_domain": "example.com"},
)

assert users[0].primary is True
assert users[1].primary is False
# --8<-- [end:basic-parse]

# --8<-- [start:basic-output]
>> [user.as_dict() for user in users]
[
  {'email': 'a@example.com', 'role': 'admin', 'primary': True},
  {'email': 'b@example.com', 'role': 'viewer', 'primary': False},
]
# --8<-- [end:basic-output]

# --8<-- [start:duplicate-error]
UserRoster.parse(
    [
        ["email", "primary"],
        ["a@example.com", "true"],
        ["a@example.com", "false"],
    ],
    context={"email_domain": "example.com"},
)
# --8<-- [end:duplicate-error]

# --8<-- [start:duplicate-error-output]
Duplicate email 
(code=table_error, schema=UserRoster, field='email', 
row=3, column=1, value='a@example.com'). 
Hint: Each user row must use a unique email address.
# --8<-- [end:duplicate-error-output]

# --8<-- [start:primary-error]
UserRoster.parse(
    [
        ["email", "primary"],
        ["a@example.com", "false"],
        ["b@example.com", "false"],
    ],
    context={"email_domain": "example.com"},
)
# --8<-- [end:primary-error]

# --8<-- [start:primary-error-output]
Table validation failed: At least one primary user is required 
(code=table_validation_failed, schema=UserRoster)
# --8<-- [end:primary-error-output]

# --8<-- [start:domain-error]
UserRoster.parse(
    [
        ["email", "primary"],
        ["a@other.test", "true"],
    ],
    context={"email_domain": "example.com"},
)
# --8<-- [end:domain-error]

# --8<-- [start:domain-error-output]
Email must belong to example.com 
(code=table_error, schema=UserRoster, field='email', 
row=2, column=1, value='a@other.test')
# --8<-- [end:domain-error-output]

# --8<-- [start:context-contract]
class SeenContext(RowTable):
    email = field("email")
    seen = None

    @classmethod
    def validate_records(cls, records, context):
        cls.seen = {
            "emails": [record.email for record in records],
            "domain": context.user_data["domain"],
        }
# --8<-- [end:context-contract]

# --8<-- [start:context-parse]
SeenContext.parse(
    [
        ["email"],
        ["a@example.com"],
        ["b@example.com"],
    ],
    context={"domain": "example.com"},
)

assert SeenContext.seen == {
    "emails": ["a@example.com", "b@example.com"],
    "domain": "example.com",
}
# --8<-- [end:context-parse]

# --8<-- [start:context-output]
>> SeenContext.seen
{'emails': ['a@example.com', 'b@example.com'], 'domain': 'example.com'}
# --8<-- [end:context-output]

# --8<-- [start:plain-error]
class PlainTableValidation(RowTable):
    email = field("email")

    @classmethod
    def validate_records(cls, records, context):
        raise ValueError("table policy unavailable")


PlainTableValidation.parse(
    [
        ["email"],
        ["a@example.com"],
    ]
)
# --8<-- [end:plain-error]

# --8<-- [start:plain-error-output]
Table validation failed: table policy unavailable 
(code=table_validation_failed, schema=PlainTableValidation)
# --8<-- [end:plain-error-output]

# --8<-- [start:column-feature]
Given the content schedule exists
  | IDs     | A-1     | P-1  |
  | Type    | Article | Poll |
  | Publish | true    | true |
# --8<-- [end:column-feature]

# --8<-- [start:column-contract]
from talika import ColumnTable, id_field


class ContentSchedule(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type")
    publish = field("Publish", parser=boolean(), default=False)

    @classmethod
    def validate_records(cls, records, context):
        published = [record for record in records if record.publish]
        limit = context.user_data["publish_limit"]
        if len(published) > limit:
            extra = published[limit]
            raise TableError.from_cell(
                f"Only {limit} item may be published in this scenario",
                extra.source_for("publish"),
                schema=cls,
                field="Publish",
                item_id=extra.id,
            )
# --8<-- [end:column-contract]

# --8<-- [start:column-error]
ContentSchedule.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article", "Poll"],
        ["Publish", "true", "true"],
    ],
    context={"publish_limit": 1},
)
# --8<-- [end:column-error]

# --8<-- [start:column-error-output]
Only 1 item may be published in this scenario 
(code=table_error, schema=ContentSchedule, field='Publish', 
row=3, column=3, item_id='P-1', value='true')
# --8<-- [end:column-error-output]

# --8<-- [start:reference-contract]
class OrgChart(RowTable):
    user_id = id_field("user id")
    manager_id = field("manager id", default="")

    @classmethod
    def validate_records(cls, records, context):
        all_ids = {r.user_id for r in records}
        for r in records:
            if r.manager_id and r.manager_id not in all_ids:
                raise TableError.from_cell(
                    f"Manager {r.manager_id} not found in org chart",
                    r.source_for("manager_id"),
                    schema=cls,
                    field="manager id",
                    item_id=r.user_id,
                )
# --8<-- [end:reference-contract]

# --8<-- [start:reference-error]
try:
    OrgChart.parse(
        [
            ["user id", "manager id"],
            ["U-1", ""],
            ["U-2", "U-999"],
        ]
    )
except TableError as exc:
    print(exc)
# --8<-- [end:reference-error]

# --8<-- [start:reference-error-output]
Manager U-999 not found in org chart 
(code=table_error, schema=OrgChart, field='manager id', 
row=3, column=2, item_id='U-2', value='U-999')
# --8<-- [end:reference-error-output]

