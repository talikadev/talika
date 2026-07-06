# --8<-- [start:feature-basic]
Given the users exist
  | age | rating | balance | active | status    | tier  | reviewer |
  | 34  | 1.5    | 12.30   | yes    | published | staff |          |
# --8<-- [end:feature-basic]

# --8<-- [start:contract-basic]
from decimal import Decimal
from enum import Enum
from typing import Literal

from talika import RowTable, field


class Status(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class UserAnnotations(RowTable):
    age: int = field("age")
    rating: float = field("rating")
    balance: Decimal = field("balance")
    active: bool = field("active")
    status: Status = field("status")
    tier: Literal["basic", "staff"] = field("tier")
    reviewer: int | None = field("reviewer")
# --8<-- [end:contract-basic]

# --8<-- [start:parse-basic]
users = UserAnnotations.parse(
    [
        ["age", "rating", "balance", "active", "status", "tier", "reviewer"],
        ["34", "1.5", "12.30", "yes", "published", "staff", ""],
    ]
)

user = users[0]

assert user.age == 34
assert user.rating == 1.5
assert user.balance == Decimal("12.30")
assert user.active is True
assert user.status is Status.PUBLISHED
assert user.tier == "staff"
assert user.reviewer is None
# --8<-- [end:parse-basic]

# --8<-- [start:parsed-output]
>> user
UserAnnotations(age=34, rating=1.5, balance=Decimal('12.30'), active=True, status=<Status.PUBLISHED: 'published'>, tier='staff', reviewer=None)

>> type(user.age), type(user.balance), type(user.status)
(<class 'int'>, <class 'decimal.Decimal'>, <enum 'Status'>)
# --8<-- [end:parsed-output]

# --8<-- [start:scalar-contract]
class ProductAnnotations(RowTable):
    quantity: int = field("quantity")
    weight: float = field("weight")
    price: Decimal = field("price")
    available: bool = field("available")
# --8<-- [end:scalar-contract]

# --8<-- [start:scalar-parse]
product = ProductAnnotations.parse(
    [
        ["quantity", "weight", "price", "available"],
        ["3", "1.25", "19.99", "on"],
    ]
)[0]

assert product.quantity == 3
assert product.weight == 1.25
assert product.price == Decimal("19.99")
assert product.available is True
# --8<-- [end:scalar-parse]

# --8<-- [start:bool-error]
ProductAnnotations.parse(
    [
        ["available"],
        ["maybe"],
    ]
)
# --8<-- [end:bool-error]

# --8<-- [start:bool-error-output]
Field parser failed: Expected one of ['0', '1', 'false', 'no', 'off', 'on', 'true', 'yes'] 
(code=parser_failed, schema=ProductAnnotations, field='available', 
row=2, column=1, value='maybe'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:bool-error-output]

# --8<-- [start:enum-contract]
class ArticleStatus(Enum):
    DRAFT = "draft"
    PUBLISHED = "published"


class ArticleAnnotations(RowTable):
    status: ArticleStatus = field("status")
    tier: Literal["basic", "staff"] = field("tier")
# --8<-- [end:enum-contract]

# --8<-- [start:enum-parse]
articles = ArticleAnnotations.parse(
    [
        ["status", "tier"],
        ["published", "staff"],
        ["DRAFT", "basic"],
    ]
)

assert articles[0].status is ArticleStatus.PUBLISHED
assert articles[1].status is ArticleStatus.DRAFT
# --8<-- [end:enum-parse]

# --8<-- [start:literal-error]
ArticleAnnotations.parse(
    [
        ["tier"],
        ["premium"],
    ]
)
# --8<-- [end:literal-error]

# --8<-- [start:literal-error-output]
Field parser failed: Expected one of ['basic', 'staff'] 
(code=parser_failed, schema=ArticleAnnotations, field='tier', 
row=2, column=1, value='premium'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:literal-error-output]

# --8<-- [start:optional-contract]
class ReviewAnnotations(RowTable):
    reviewer_id: int | None = field("reviewer id")
    backup_owner: str | None = field("backup owner")
# --8<-- [end:optional-contract]

# --8<-- [start:optional-parse]
reviews = ReviewAnnotations.parse(
    [
        ["reviewer id", "backup owner"],
        ["", "none"],
        ["42", "Priya"],
    ]
)

assert reviews[0].reviewer_id is None
assert reviews[0].backup_owner is None
assert reviews[1].reviewer_id == 42
assert reviews[1].backup_owner == "Priya"
# --8<-- [end:optional-parse]

# --8<-- [start:optional-output]
>> reviews[0].as_dict()
{'reviewer_id': None, 'backup_owner': None}

>> reviews[1].as_dict()
{'reviewer_id': 42, 'backup_owner': 'Priya'}
# --8<-- [end:optional-output]

# --8<-- [start:list-raw-contract]
class TagAnnotations(RowTable):
    tags: list[str] = field("tags")
    scores: list[int] = field("scores")
# --8<-- [end:list-raw-contract]

# --8<-- [start:list-raw-parse]
record = TagAnnotations.parse(
    [
        ["tags", "scores"],
        ["qa, docs", "1, 2"],
    ]
)[0]

assert record.tags == "qa, docs"
assert record.scores == "1, 2"
# --8<-- [end:list-raw-parse]

# --8<-- [start:list-raw-output]
>> record.as_dict()
{'tags': 'qa, docs', 'scores': '1, 2'}

>> type(record.tags), type(record.scores)
(<class 'str'>, <class 'str'>)
# --8<-- [end:list-raw-output]

# --8<-- [start:list-explicit-contract]
from talika import compose, each, integer, split


class ExplicitListAnnotations(RowTable):
    tags: list[str] = field("tags", parser=split(","))
    scores: list[int] = field("scores", parser=compose(split(","), each(integer())))
# --8<-- [end:list-explicit-contract]

# --8<-- [start:list-explicit-parse]
record = ExplicitListAnnotations.parse(
    [
        ["tags", "scores"],
        ["qa, docs", "1, 2"],
    ]
)[0]

assert record.tags == ["qa", "docs"]
assert record.scores == [1, 2]
# --8<-- [end:list-explicit-parse]

# --8<-- [start:list-explicit-output]
>> record.as_dict()
{'tags': ['qa', 'docs'], 'scores': [1, 2]}
# --8<-- [end:list-explicit-output]

# --8<-- [start:explicit-parser-contract]
from talika import string


class OverrideAnnotations(RowTable):
    code: int = field("code", parser=string(upper=True))
# --8<-- [end:explicit-parser-contract]

# --8<-- [start:explicit-parser-parse]
record = OverrideAnnotations.parse(
    [
        ["code"],
        ["many"],
    ]
)[0]

assert record.code == "MANY"
# --8<-- [end:explicit-parser-parse]

# --8<-- [start:unsupported-contract]
class InternalId:
    pass


class UnsupportedAnnotations(RowTable):
    value: InternalId = field("value")
    mixed: int | float = field("mixed")
# --8<-- [end:unsupported-contract]

# --8<-- [start:unsupported-parse]
record = UnsupportedAnnotations.parse(
    [
        ["value", "mixed"],
        ["raw-id", "12.5"],
    ]
)[0]

assert record.value == "raw-id"
assert record.mixed == "12.5"
# --8<-- [end:unsupported-parse]

# --8<-- [start:int-error]
UserAnnotations.parse(
    [
        ["age"],
        ["many"],
    ]
)
# --8<-- [end:int-error]

# --8<-- [start:int-error-output]
Field parser failed: invalid literal for int() with base 10: 'many' 
(code=parser_failed, schema=UserAnnotations, field='age', 
row=2, column=1, value='many'). 
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:int-error-output]
