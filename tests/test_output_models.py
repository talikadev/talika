from dataclasses import dataclass

import pytest

from talika import (
    ColumnTable,
    RowTable,
    TableError,
    discriminator_field,
    field,
    id_field,
    integer,
)


@dataclass(frozen=True)
class User:
    name: str
    age: int


def test_dataclass_output_model_receives_parsed_values():
    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

    users = UserTable.parse_as([["name", "age"], ["Alice", "30"]])

    assert users == [User(name="Alice", age=30)]


def test_parse_returns_records_even_with_an_output_model():
    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

    users = UserTable.parse([["name", "age"], ["Alice", "30"]])

    assert isinstance(users[0], UserTable)
    assert users[0].name == "Alice"
    assert users[0].age == 30


def test_column_parse_returns_records_even_with_an_output_model():
    @dataclass(frozen=True)
    class Item:
        id: str
        name: str

    class ItemTable(ColumnTable):
        output_model = Item
        id = id_field("IDs")
        name = field(required=True)

    records = ItemTable.parse([["IDs", "one"], ["name", "First"]])
    items = ItemTable.parse_as([["IDs", "one"], ["name", "First"]])

    assert isinstance(records[0], ItemTable)
    assert items == [Item(id="one", name="First")]


def test_validation_runs_on_schema_records_before_model_conversion():
    seen = {}

    class UserTable(RowTable):
        output_model = User

        name = field("name")
        age = field("age", parser=integer())

        def validate_record(self, context):
            seen["source"] = self.source_for("age").source_value
            if self.age < 18:
                raise ValueError("User must be an adult")

    with pytest.raises(TableError, match="must be an adult"):
        UserTable.parse([["name", "age"], ["Alice", "16"]])

    assert seen["source"] == "16"


def test_output_model_errors_include_record_location():
    @dataclass
    class StrictUser:
        name: str

        def __post_init__(self):
            raise ValueError("model rejected user")

    class UserTable(RowTable):
        output_model = StrictUser
        name = field("name")

    with pytest.raises(TableError, match="model rejected user") as error:
        UserTable.parse_as([["name"], ["Alice"]])

    assert error.value.row == 2


def test_explicit_output_model_overrides_configured_builders():
    calls = []

    class UserTable(RowTable):
        name = field("name")

        @classmethod
        def build_output(cls, record, context):
            calls.append(record.name)
            return {"configured": record.name}

    users = UserTable.parse_as(
        [["name"], ["Alice"]],
        lambda **values: User(**values, age=0),
    )

    assert users == [User(name="Alice", age=0)]
    assert calls == []


def test_falsy_callable_is_still_an_explicit_output_target():
    class FalsyTarget:
        def __bool__(self):
            return False

        def __call__(self, **values):
            return values["name"].upper()

    class UserTable(RowTable):
        output_model = lambda **values: "configured"  # noqa: E731
        name = field("name")

    assert UserTable.parse_as([["name"], ["Alice"]], FalsyTarget()) == ["ALICE"]


def test_parse_as_rejects_missing_and_invalid_targets_before_parsing():
    class UserTable(RowTable):
        name = field("name")

    with pytest.raises(ValueError, match="requires an output model"):
        UserTable.parse_as([["name"], ["Alice"]])

    with pytest.raises(TypeError, match="must be callable"):
        UserTable.parse_as("not a table", object())  # type: ignore[arg-type]


def test_variant_without_configured_output_reports_its_source_record():
    @dataclass(frozen=True)
    class Article:
        kind: str
        body: str

    class ContentTable(RowTable):
        kind = discriminator_field("kind")

    @ContentTable.variant("article")
    class ArticleContent(ContentTable):
        output_model = Article
        body = field("body", required=True)

    @ContentTable.variant("poll")
    class PollContent(ContentTable):
        question = field("question", required=True)

    with pytest.raises(TableError) as captured:
        ContentTable.parse_as(
            [
                ["kind", "body", "question"],
                ["article", "News", ""],
                ["poll", "", "Ready?"],
            ]
        )

    assert captured.value.code == "output_failed"
    assert captured.value.schema == "PollContent"
    assert captured.value.row == 3
