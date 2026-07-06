import pytest

from talika import RowTable, TableError, field


def test_validate_records_receives_all_records_and_context():
    seen = {}

    class UserTable(RowTable):
        email = field("email")

        @classmethod
        def validate_records(cls, records, context):
            seen["emails"] = [record.email for record in records]
            seen["domain"] = context.user_data["domain"]

    UserTable.parse(
        [["email"], ["a@example.com"], ["b@example.com"]],
        context={"domain": "example.com"},
    )

    assert seen == {
        "emails": ["a@example.com", "b@example.com"],
        "domain": "example.com",
    }


def test_table_validator_can_raise_source_aware_error():
    class UserTable(RowTable):
        email = field("email")

        @classmethod
        def validate_records(cls, records, context):
            seen = {}
            for record in records:
                if record.email in seen:
                    raise TableError.from_cell(
                        "Duplicate email",
                        record.source_for("email"),
                        schema=cls,
                    )
                seen[record.email] = record

    with pytest.raises(TableError, match="Duplicate email") as error:
        UserTable.parse([["email"], ["a@example.com"], ["a@example.com"]])

    assert error.value.row == 3
    assert error.value.column == 1


def test_plain_table_validation_errors_are_wrapped():
    class UserTable(RowTable):
        email = field("email")

        @classmethod
        def validate_records(cls, records, context):
            raise ValueError("At least one primary user is required")

    with pytest.raises(TableError, match="Table validation failed") as error:
        UserTable.parse([["email"], ["a@example.com"]])

    assert "At least one primary user" in str(error.value)
