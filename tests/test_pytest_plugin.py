from types import SimpleNamespace

from talika import RowTable, field
from talika.pytest_plugin import (
    TalikaParser,
    pytest_bdd_after_step,
    pytest_bdd_before_step_call,
)

pytest_plugins = ("pytester",)


class UserTable(RowTable):
    name = field("name", required=True)


def test_talika_fixture_parses_with_schema(talika):
    users = talika.parse([["name"], ["Alice"]], schema=UserTable)

    assert users[0].name == "Alice"


def test_talika_fixture_can_return_schema_records(talika):
    users = talika.parse_records([["name"], ["Alice"]], schema=UserTable)

    assert isinstance(users[0], UserTable)
    assert users[0].name == "Alice"


def test_talika_fixture_can_validate_without_raising(talika):
    result = talika.validate([["name"], [""]], schema=UserTable)

    assert not result.valid
    assert result.records == ()
    assert result.errors[0].code == "empty_required"


def test_pytest_bdd_hook_binds_absolute_source_coordinates(tmp_path):
    raw = [["name"], [""]]
    feature_path = tmp_path / "users.feature"
    feature = SimpleNamespace(filename=str(feature_path))
    step = SimpleNamespace(
        datatable=SimpleNamespace(
            rows=[
                SimpleNamespace(
                    cells=[
                        SimpleNamespace(
                            value="name",
                            location=SimpleNamespace(line=5, column=9),
                        )
                    ]
                ),
                SimpleNamespace(
                    cells=[
                        SimpleNamespace(
                            value="",
                            location=SimpleNamespace(line=6, column=9),
                        )
                    ]
                ),
            ]
        )
    )
    parser = TalikaParser()
    args = {"datatable": raw, "talika": parser}

    pytest_bdd_before_step_call(feature=feature, step=step, step_func_args=args)
    result = parser.validate(raw, schema=UserTable)

    assert result.errors[0].source_uri == feature_path.resolve().as_uri()
    assert result.errors[0].row == 6
    assert result.errors[0].column == 9

    pytest_bdd_after_step(step_func_args=args)
    unbound = parser.validate(raw, schema=UserTable)
    assert unbound.errors[0].source_uri is None


def test_pytest_bdd_fixture_provides_feature_provenance_end_to_end(pytester):
    feature = pytester.makefile(
        ".feature",
        users="""
Feature: Users

  Scenario: Invalid user
    Given the following users:
      | name |
      |      |

  Scenario Outline: Invalid ages
    Given the following ages:
      | age   |
      | <age> |
    Examples:
      | age |
      | old |
      | bad |
""",
    )
    pytester.makepyfile(
        """
from pathlib import Path

from pytest_bdd import given, scenario

from talika import RowTable, field, integer


class Users(RowTable):
    name = field("name", required=True)


class Ages(RowTable):
    age = field("age", parser=integer())


@scenario("users.feature", "Invalid user")
def test_invalid_user():
    pass


@scenario("users.feature", "Invalid ages")
def test_invalid_ages():
    pass


@given("the following users:")
def invalid_users(datatable, talika):
    result = talika.validate(datatable, schema=Users)
    diagnostic = result.errors[0]
    assert diagnostic.source_uri == Path("users.feature").resolve().as_uri()
    assert diagnostic.row == 6
    assert diagnostic.column == 14


@given("the following ages:")
def invalid_ages(datatable, talika):
    result = talika.validate(datatable, schema=Ages)
    diagnostic = result.errors[0]
    assert diagnostic.source_uri == Path("users.feature").resolve().as_uri()
    assert diagnostic.row == 11
    assert diagnostic.column == 9
"""
    )

    result = pytester.runpytest("-p", "no:cacheprovider", "-q")

    result.assert_outcomes(passed=3)
    assert feature.exists()
