import pytest

from talika import (
    ColumnTable,
    ParseContext,
    RowTable,
    TableError,
    field,
    id_field,
)


def test_validation_runs_after_parsers_and_defaults():
    seen = {}

    def parse_number(value, context):
        return int(value)

    class ScoreTable(RowTable):
        score = field("score", parser=parse_number)
        enabled = field("enabled", default=True)

        def validate_record(self, context):
            seen["score"] = self.score
            seen["enabled"] = self.enabled

    records = ScoreTable.parse([["score"], ["7"]])

    assert records[0].score == 7
    assert seen == {"score": 7, "enabled": True}


def test_validation_receives_parse_context():
    seen = {}

    class ContextTable(RowTable):
        value = field("value")

        def validate_record(self, context):
            seen["context"] = context
            seen["limit"] = context.user_data["limit"]

    ContextTable.parse([["value"], ["one"]], context={"limit": 3})

    assert isinstance(seen["context"], ParseContext)
    assert seen["limit"] == 3


def test_row_validation_failure_has_source_row():
    class UserTable(RowTable):
        name = field("name")
        role = field("role")

        def validate_record(self, context):
            if self.role not in {"admin", "editor"}:
                raise ValueError(f"Unsupported role: {self.role}")

    with pytest.raises(TableError, match="Unsupported role: owner") as error:
        UserTable.parse(
            [
                ["name", "role"],
                ["Alice", "admin"],
                ["Bob", "owner"],
            ]
        )

    message = str(error.value)
    assert "schema=UserTable" in message
    assert "row=3" in message
    assert "column=" not in message
    assert isinstance(error.value.__cause__, ValueError)


def test_column_validation_failure_has_item_id_and_source_column():
    class ContentTable(ColumnTable):
        id = id_field("IDs")
        content_type = field("Type")
        headline = field("Headline")

        def validate_record(self, context):
            if self.content_type == "Poll" and not self.headline.endswith("?"):
                raise ValueError("Poll headline must end with a question mark")

    with pytest.raises(TableError, match="Poll headline") as error:
        ContentTable.parse(
            [
                ["IDs", "1", "2"],
                ["Type", "Article", "Poll"],
                ["Headline", "News", "Choose one"],
            ]
        )

    message = str(error.value)
    assert "item_id='2'" in message
    assert "column=3" in message
    assert "row=" not in message


def test_validation_can_use_context_policy():
    class UserTable(RowTable):
        role = field("role")

        def validate_record(self, context):
            if self.role not in context.user_data["allowed_roles"]:
                raise ValueError(f"Role {self.role!r} is not allowed")

    records = UserTable.parse(
        [["role"], ["editor"]],
        context={"allowed_roles": {"admin", "editor"}},
    )

    assert records[0].role == "editor"


def test_default_validation_hook_does_nothing():
    class PlainTable(RowTable):
        value = field("value")

    assert PlainTable.parse([["value"], ["one"]])[0].value == "one"
