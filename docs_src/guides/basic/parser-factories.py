# --8<-- [start:feature-scalar]
Given the users exist
  | username | age | mask | rating | balance |
  | Alice    | 34  | ff   | 4.5    | 12.30   |
# --8<-- [end:feature-scalar]

# --8<-- [start:scalar-contract]
from decimal import Decimal

from talika import RowTable, decimal, field, floating, integer, string


class ScalarParsers(RowTable):
    username = field("username", parser=string(strip=True, lower=True))
    age = field("age", parser=integer())
    mask = field("mask", parser=integer(base=16))
    rating = field("rating", parser=floating())
    balance = field("balance", parser=decimal())
# --8<-- [end:scalar-contract]

# --8<-- [start:scalar-parse]
user = ScalarParsers.parse(
    [
        ["username", "age", "mask", "rating", "balance"],
        [" Alice ", "34", "ff", "4.5", "12.30"],
    ]
)[0]

assert user.username == "alice"
assert user.age == 34
assert user.mask == 255
assert user.rating == 4.5
assert user.balance == Decimal("12.30")
# --8<-- [end:scalar-parse]

# --8<-- [start:scalar-output]
>> user
ScalarParsers(username='alice', age=34, mask=255, rating=4.5, balance=Decimal('12.30'))

>> user.as_dict()
{'username': 'alice', 'age': 34, 'mask': 255, 'rating': 4.5, 'balance': Decimal('12.30')}
# --8<-- [end:scalar-output]

# --8<-- [start:feature-boolean]
Given the account states exist
  | default active | lifecycle active | strict active |
  | true           | enabled          | YES           |
  | false          | inactive         | NO            |
# --8<-- [end:feature-boolean]

# --8<-- [start:boolean-contract]
from talika import boolean, compose


class BooleanParsers(RowTable):
    default_active = field("default active", parser=boolean())
    lifecycle_active = field(
        "lifecycle active",
        parser=boolean(
            true_values=("enabled", "active", "y"),
            false_values=("disabled", "inactive", "n"),
        ),
    )
    strict_active = field(
        "strict active",
        parser=boolean(
            true_values=("YES",),
            false_values=("NO",),
            case_sensitive=True,
        ),
    )
# --8<-- [end:boolean-contract]

# --8<-- [start:boolean-parse]
enabled, disabled = BooleanParsers.parse(
    [
        ["default active", "lifecycle active", "strict active"],
        ["true", "enabled", "YES"],
        ["false", "inactive", "NO"],
    ]
)

assert enabled.default_active is True
assert enabled.lifecycle_active is True
assert enabled.strict_active is True

assert disabled.default_active is False
assert disabled.lifecycle_active is False
assert disabled.strict_active is False
# --8<-- [end:boolean-parse]

# --8<-- [start:boolean-output]
>> enabled.as_dict()
{'default_active': True, 'lifecycle_active': True, 'strict_active': True}

>> disabled.as_dict()
{'default_active': False, 'lifecycle_active': False, 'strict_active': False}
# --8<-- [end:boolean-output]

# --8<-- [start:boolean-error]
BooleanParsers.parse(
    [
        ["default active"],
        ["maybe"],
    ]
)
# --8<-- [end:boolean-error]

# --8<-- [start:boolean-error-output]
Field parser failed: Expected one of ['false', 'true']
(code=parser_failed, schema=BooleanParsers, field='default active', 
row=2, column=1, value='maybe'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:boolean-error-output]

# --8<-- [start:boolean-whitespace]
class PaddedBoolean(RowTable):
    active = field(
        "active",
        parser=compose(string(strip=True), boolean()),
    )


record = PaddedBoolean.parse([["active"], [" true "]])[0]

assert record.active is True
# --8<-- [end:boolean-whitespace]

# --8<-- [start:boolean-description]
default_contract = BooleanParsers.describe().fields[0].parser
lifecycle_contract = BooleanParsers.describe().fields[1].parser

assert default_contract == (
    "boolean(true_values=('true',), false_values=('false',), "
    "case_sensitive=False)"
)
assert lifecycle_contract == (
    "boolean(true_values=('active', 'enabled', 'y'), "
    "false_values=('disabled', 'inactive', 'n'), case_sensitive=False)"
)
# --8<-- [end:boolean-description]

# --8<-- [start:vocabulary-contract]
from talika import choice, map_value


class VocabularyParsers(RowTable):
    role = field("role", parser=choice("admin", "editor", case_sensitive=False))
    status = field("status", parser=choice("Draft", "Published", case_sensitive=False))
    priority = field("priority", parser=map_value({"low": 1, "medium": 3, "high": 5}))
# --8<-- [end:vocabulary-contract]

# --8<-- [start:vocabulary-parse]
user = VocabularyParsers.parse(
    [
        ["role", "status", "priority"],
        ["Admin", "published", "high"],
    ]
)[0]

assert user.role == "admin"
assert user.status == "Published"
assert user.priority == 5
# --8<-- [end:vocabulary-parse]

# --8<-- [start:vocabulary-output]
>> user.as_dict()
{'role': 'admin', 'status': 'Published', 'priority': 5}
# --8<-- [end:vocabulary-output]

# --8<-- [start:choice-error]
VocabularyParsers.parse(
    [
        ["status"],
        ["Archived"],
    ]
)
# --8<-- [end:choice-error]

# --8<-- [start:choice-error-output]
Field parser failed: Expected one of ['Draft', 'Published'] 
(code=parser_failed, schema=VocabularyParsers, field='status', 
row=2, column=1, value='Archived'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:choice-error-output]

# --8<-- [start:map-error]
VocabularyParsers.parse(
    [
        ["priority"],
        ["urgent"],
    ]
)
# --8<-- [end:map-error]

# --8<-- [start:map-error-output]
Field parser failed: No mapped value for 'urgent' 
(code=parser_failed, schema=VocabularyParsers, field='priority', 
row=2, column=1, value='urgent'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:map-error-output]

# --8<-- [start:feature-list]
Given the user metadata exists
  | tags              | scores | reviewer |
  | qa, docs          | 1;2;3  | none     |
  | smoke, regression | 4;5    | 42       |
# --8<-- [end:feature-list]

# --8<-- [start:list-contract]
from talika import compose, each, optional, split


class ListParsers(RowTable):
    tags = field("tags", parser=split(","))
    scores = field("scores", parser=compose(split(";"), each(integer())))
    reviewer = field(
        "reviewer",
        parser=optional(integer(), none_values=("none", "n/a", "null")),
        empty="parse",
    )
# --8<-- [end:list-contract]

# --8<-- [start:list-parse]
reviewed, assigned = ListParsers.parse(
    [
        ["tags", "scores", "reviewer"],
        ["qa, docs", "1;2;3", "none"],
        ["smoke, regression", "4;5", "42"],
    ]
)

assert reviewed.tags == ["qa", "docs"]
assert reviewed.scores == [1, 2, 3]
assert reviewed.reviewer is None

assert assigned.tags == ["smoke", "regression"]
assert assigned.scores == [4, 5]
assert assigned.reviewer == 42
# --8<-- [end:list-parse]

# --8<-- [start:list-output]
>> reviewed.as_dict()
{'tags': ['qa', 'docs'], 'scores': [1, 2, 3], 'reviewer': None}

>> assigned.as_dict()
{'tags': ['smoke', 'regression'], 'scores': [4, 5], 'reviewer': 42}
# --8<-- [end:list-output]

# --8<-- [start:list-error]
ListParsers.parse(
    [
        ["scores"],
        ["1;two;3"],
    ]
)
# --8<-- [end:list-error]

# --8<-- [start:list-error-output]
Field parser failed: invalid literal for int() with base 10: 'two' 
(code=parser_failed, schema=ListParsers, field='scores', 
row=2, column=1, value='1;two;3'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:list-error-output]

# --8<-- [start:wrong-order]
class WrongOrder(RowTable):
    scores = field("scores", parser=each(integer()))


WrongOrder.parse(
    [
        ["scores"],
        ["1;2;3"],
    ]
)
# --8<-- [end:wrong-order]

# --8<-- [start:wrong-order-output]
Field parser failed: each parser expects a non-string iterable 
(code=parser_failed, schema=WrongOrder, field='scores', 
row=2, column=1, value='1;2;3'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:wrong-order-output]

# --8<-- [start:optional-contract]
class OptionalParsers(RowTable):
    reviewer = field(
        "reviewer",
        parser=optional(integer(), none_values=("none", "n/a", "null")),
    )
# --8<-- [end:optional-contract]

# --8<-- [start:optional-parse]
records = OptionalParsers.parse(
    [
        ["reviewer"],
        [""],
        ["NULL"],
        ["none"],
        ["n/a"],
        ["7"],
    ]
)

assert [record.reviewer for record in records] == [None, None, None, None, 7]
# --8<-- [end:optional-parse]

# --8<-- [start:optional-output]
>> [record.reviewer for record in records]
[None, None, None, None, 7]
# --8<-- [end:optional-output]

# --8<-- [start:optional-replace-error]
class ReplacedNullTokens(RowTable):
    reviewer = field(
        "reviewer",
        parser=optional(integer(), none_values=("n/a",)),
        empty="parse",
    )


ReplacedNullTokens.parse(
    [
        ["reviewer"],
        ["none"],
    ]
)
# --8<-- [end:optional-replace-error]

# --8<-- [start:optional-replace-error-output]
Field parser failed: invalid literal for int() with base 10: 'none' 
(code=parser_failed, schema=ReplacedNullTokens, field='reviewer', 
row=2, column=1, value='none'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:optional-replace-error-output]

# --8<-- [start:configuration-errors]
string(lower=True, upper=True)
boolean(true_values=("yes",), false_values=("YES",))
boolean(true_values="yes")
choice()
split("")
compose()
# --8<-- [end:configuration-errors]

# --8<-- [start:configuration-errors-output]
ValueError: string parser cannot enable both lower and upper
ValueError: Boolean true and false values overlap: ['yes']
TypeError: true_values must be a non-string iterable of strings
ValueError: choice parser requires at least one allowed value
ValueError: split separator cannot be empty
ValueError: compose requires at least one parser
# --8<-- [end:configuration-errors-output]

# --8<-- [start:pipeline-contract]
class PipelineSchema(RowTable):
    categories = field(
        "categories",
        parser=compose(
            split(";"),
            each(choice("A", "B", "C", case_sensitive=False))
        )
    )
# --8<-- [end:pipeline-contract]

# --8<-- [start:pipeline-parse]
records = PipelineSchema.parse(
    [
        ["categories"],
        ["a;B"],
    ]
)
assert records[0].categories == ["A", "B"]
# --8<-- [end:pipeline-parse]

