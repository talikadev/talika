from decimal import Decimal

import pytest

from talika import (
    RowTable,
    TableError,
    boolean,
    choice,
    compose,
    decimal,
    each,
    field,
    floating,
    integer,
    map_value,
    optional,
    split,
    string,
)


def parse_one(parser, value):
    class ValueTable(RowTable):
        result = field("value", parser=parser)

    return ValueTable.parse([["value"], [value]])[0].result


def test_scalar_parsers_convert_common_values():
    assert parse_one(string(strip=True, upper=True), "  hello ") == "HELLO"
    assert parse_one(integer(), "42") == 42
    assert parse_one(integer(base=16), "ff") == 255
    assert parse_one(floating(), "2.5") == 2.5
    assert parse_one(decimal(), "12.30") == Decimal("12.30")
    assert parse_one(boolean(), "YES") is True
    assert parse_one(boolean(), "off") is False


def test_choice_and_mapping_return_canonical_values():
    parser = choice("Draft", "Published", case_sensitive=False)

    assert parse_one(parser, "draft") == "Draft"
    assert parse_one(map_value({"high": 3, "low": 1}), "high") == 3


def test_split_and_composition_build_typed_lists():
    parser = compose(split(","), each(compose(string(strip=True), integer())))

    assert parse_one(parser, "1, 2, 3") == [1, 2, 3]


def test_optional_parser_handles_empty_and_null_values():
    parser = optional(integer())

    assert parse_one(parser, "") is None
    assert parse_one(parser, "NULL") is None
    assert parse_one(parser, "7") == 7


def test_parser_failures_keep_existing_location_diagnostics():
    with pytest.raises(TableError, match="Expected one of") as error:
        parse_one(boolean(), "maybe")

    assert error.value.row == 2
    assert error.value.column == 1
    assert error.value.value == "maybe"


def test_parser_configuration_errors_are_explicit():
    with pytest.raises(ValueError, match="both lower and upper"):
        string(lower=True, upper=True)
    with pytest.raises(ValueError, match="overlap"):
        boolean(true_values=("yes",), false_values=("YES",))
    with pytest.raises(ValueError, match="at least one"):
        choice()
    with pytest.raises(ValueError, match="cannot be empty"):
        split("")
    with pytest.raises(ValueError, match="at least one parser"):
        compose()


def test_each_rejects_non_iterable_and_string_results():
    with pytest.raises(TableError, match="non-string iterable"):
        parse_one(each(integer()), "123")
