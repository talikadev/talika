from talika import RowTable, field


class UserTable(RowTable):
    name = field("name", required=True)


def test_talika_fixture_parses_with_schema(talika):
    users = talika.parse([["name"], ["Alice"]], schema=UserTable)

    assert users[0].name == "Alice"


def test_talika_fixture_can_return_schema_records(talika):
    users = talika.parse_records([["name"], ["Alice"]], schema=UserTable)

    assert isinstance(users[0], UserTable)
    assert users[0].name == "Alice"
