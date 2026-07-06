# --8<-- [start:feature-basic]
Given the account users exist
  | username | age | role   |
  | alice    | 34  | admin  |
  | bob      | 21  | viewer |
# --8<-- [end:feature-basic]

# --8<-- [start:basic-contract]
from talika import RowTable, field, integer


class AccountRows(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    role = field("role", default="viewer")

    def validate_record(self, context):
        if self.age < 18:
            raise ValueError(f"{self.username} must be at least 18")
        if self.role not in context.user_data["allowed_roles"]:
            raise ValueError(f"role {self.role!r} is not allowed")
# --8<-- [end:basic-contract]

# --8<-- [start:basic-parse]
users = AccountRows.parse(
    [
        ["username", "age", "role"],
        ["alice", "34", "admin"],
        ["bob", "21", "viewer"],
    ],
    context={"allowed_roles": {"admin", "editor", "viewer"}},
)

assert users[0].age == 34
assert users[0].role == "admin"
assert users[1].role == "viewer"
# --8<-- [end:basic-parse]

# --8<-- [start:basic-output]
>> [user.as_dict() for user in users]
[
  {'username': 'alice', 'age': 34, 'role': 'admin'},
  {'username': 'bob', 'age': 21, 'role': 'viewer'},
]
# --8<-- [end:basic-output]

# --8<-- [start:age-error]
AccountRows.parse(
    [
        ["username", "age", "role"],
        ["kai", "16", "viewer"],
    ],
    context={"allowed_roles": {"admin", "editor", "viewer"}},
)
# --8<-- [end:age-error]

# --8<-- [start:age-error-output]
Record validation failed: kai must be at least 18 
(code=record_validation_failed, schema=AccountRows, row=2)
# --8<-- [end:age-error-output]

# --8<-- [start:role-error]
AccountRows.parse(
    [
        ["username", "age", "role"],
        ["maya", "25", "owner"],
    ],
    context={"allowed_roles": {"admin", "editor", "viewer"}},
)
# --8<-- [end:role-error]

# --8<-- [start:role-error-output]
Record validation failed: role 'owner' is not allowed 
(code=record_validation_failed, schema=AccountRows, row=2)
# --8<-- [end:role-error-output]

# --8<-- [start:order-contract]
class ValidationOrder(RowTable):
    score = field("score", parser=integer())
    enabled = field("enabled", default=True)

    def validate_record(self, context):
        if self.enabled and self.score < context.user_data["minimum"]:
            raise ValueError(f"score must be at least {context.user_data['minimum']}")
# --8<-- [end:order-contract]

# --8<-- [start:order-parse]
record = ValidationOrder.parse(
    [
        ["score"],
        ["12"],
    ],
    context={"minimum": 10},
)[0]

assert record.score == 12
assert record.enabled is True
# --8<-- [end:order-parse]

# --8<-- [start:order-output]
>> record.as_dict()
{'score': 12, 'enabled': True}
# --8<-- [end:order-output]

# --8<-- [start:order-error]
ValidationOrder.parse(
    [
        ["score"],
        ["7"],
    ],
    context={"minimum": 10},
)
# --8<-- [end:order-error]

# --8<-- [start:order-error-output]
Record validation failed: score must be at least 10 
(code=record_validation_failed, schema=ValidationOrder, row=2)
# --8<-- [end:order-error-output]

# --8<-- [start:source-aware-contract]
from talika import TableError


class SourceAwareAccounts(RowTable):
    username = field("username", required=True)
    age = field("age", parser=integer())
    email = field("email", required=True)

    def validate_record(self, context):
        if "@" not in self.email:
            raise TableError.from_cell(
                "Email must contain @",
                self.source_for("email"),
                schema=type(self),
                field="email",
                hint="Use a complete email address in the table.",
            )
# --8<-- [end:source-aware-contract]

# --8<-- [start:source-aware-error]
SourceAwareAccounts.parse(
    [
        ["username", "age", "email"],
        ["alice", "34", "not-an-email"],
    ]
)
# --8<-- [end:source-aware-error]

# --8<-- [start:source-aware-error-output]
Email must contain @ 
(code=table_error, schema=SourceAwareAccounts, field='email', 
row=2, column=3, value='not-an-email'). 
Hint: Use a complete email address in the table.
# --8<-- [end:source-aware-error-output]

# --8<-- [start:column-feature]
Given the content exists
  | IDs      | A-1          | P-1        |
  | Type     | Article      | Poll       |
  | Headline | Market brief | Choose one |
# --8<-- [end:column-feature]

# --8<-- [start:column-contract]
from talika import ColumnTable, id_field


class ContentColumns(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type")
    headline = field("Headline")

    def validate_record(self, context):
        if self.content_type == "Poll" and not self.headline.endswith("?"):
            raise ValueError("Poll headline must end with a question mark")
# --8<-- [end:column-contract]

# --8<-- [start:column-error]
ContentColumns.parse(
    [
        ["IDs", "A-1", "P-1"],
        ["Type", "Article", "Poll"],
        ["Headline", "Market brief", "Choose one"],
    ]
)
# --8<-- [end:column-error]

# --8<-- [start:column-error-output]
Record validation failed: Poll headline must end with a question mark 
(code=record_validation_failed, schema=ContentColumns, column=3, item_id='P-1')
# --8<-- [end:column-error-output]

# --8<-- [start:default-source-warning]
class DefaultEmail(RowTable):
    name = field("name")
    email = field("email", default="unknown")

    def validate_record(self, context):
        if self.email == "unknown":
            self.source_for("email")


DefaultEmail.parse(
    [
        ["name"],
        ["Alice"],
    ]
)
# --8<-- [end:default-source-warning]

# --8<-- [start:default-source-warning-output]
Record validation failed: "No source cell is available for field 'email'" 
(code=record_validation_failed, schema=DefaultEmail, row=2)
# --8<-- [end:default-source-warning-output]

# --8<-- [start:conditional-contract]
class ArticlePublishSchema(RowTable):
    status = field("status", required=True)
    pub_date = field("publication date", default="")

    def validate_record(self, context):
        if self.status.lower() == "published" and not self.pub_date:
            raise TableError.from_cell(
                "Publication date is required when status is Published",
                self.source_for("pub_date"),
                schema=self.__class__,
                field="publication date",
            )
# --8<-- [end:conditional-contract]

# --8<-- [start:conditional-parse]
# This raises TableError because pub_date is blank but status is published
try:
    ArticlePublishSchema.parse(
        [
            ["status", "publication date"],
            ["published", ""],
        ]
    )
except TableError as exc:
    # Diagnostic output shown below
    print(exc)
# --8<-- [end:conditional-parse]

# --8<-- [start:conditional-output]
Publication date is required when status is Published 
(code=table_error, schema=ArticlePublishSchema, field='publication date', 
row=2, column=2, value='')
# --8<-- [end:conditional-output]

