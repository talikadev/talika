from datetime import date as Date
from datetime import datetime as DateTime
from datetime import timedelta, timezone
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
from talika import (
    date as date_parser,
)
from talika import (
    datetime as datetime_parser,
)


def parse_one(parser, value):
    class ValueTable(RowTable):
        result = field("value", parser=parser, empty="parse")

    return ValueTable.parse([["value"], [value]])[0].result


def test_scalar_parsers_convert_common_values():
    assert parse_one(string(strip=True, upper=True), "  hello ") == "HELLO"
    assert parse_one(integer(), "42") == 42
    assert parse_one(integer(base=16), "ff") == 255
    assert parse_one(floating(), "2.5") == 2.5
    assert parse_one(decimal(), "12.30") == Decimal("12.30")
    assert parse_one(boolean(), "TRUE") is True
    assert parse_one(boolean(), "False") is False


def test_temporal_parsers_use_strict_default_formats():
    assert parse_one(date_parser(), "2026-07-18") == Date(2026, 7, 18)
    assert parse_one(date_parser(), "2024-02-29") == Date(2024, 2, 29)
    assert parse_one(datetime_parser(), "2026-07-18T14:30:45") == DateTime(
        2026, 7, 18, 14, 30, 45
    )


def test_temporal_parsers_support_one_custom_format():
    assert parse_one(date_parser(format="%d/%m/%Y"), "18/07/2026") == Date(2026, 7, 18)
    assert parse_one(
        datetime_parser(format="%d/%m/%Y %H:%M"),
        "18/07/2026 14:30",
    ) == DateTime(2026, 7, 18, 14, 30)
    assert parse_one(
        datetime_parser(format="%Y-%m-%dT%H:%M:%S.%f"),
        "2026-07-18T14:30:45.123456",
    ) == DateTime(2026, 7, 18, 14, 30, 45, 123456)
    assert parse_one(
        datetime_parser(format="%Y-%m-%dT%H:%M:%S%z"),
        "2026-07-18T14:30:45+0530",
    ) == DateTime(
        2026,
        7,
        18,
        14,
        30,
        45,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )


@pytest.mark.parametrize(
    ("parser", "value"),
    [
        (date_parser(), "2025-02-29"),
        (datetime_parser(), "2026-07-18 14:30:45"),
        (datetime_parser(), "2026-07-18T14:30"),
        (datetime_parser(), "2026-07-18T25:30:45"),
    ],
)
def test_temporal_parser_failures_keep_source_diagnostics(parser, value):
    with pytest.raises(TableError) as error:
        parse_one(parser, value)

    assert error.value.code == "parser_failed"
    assert error.value.row == 2
    assert error.value.column == 1
    assert error.value.value == value
    assert isinstance(error.value.diagnostic.cause, ValueError)


def test_temporal_parsers_do_not_strip_whitespace_implicitly():
    with pytest.raises(TableError):
        parse_one(date_parser(), " 2026-07-18 ")

    parser = compose(string(strip=True), date_parser())
    assert parse_one(parser, " 2026-07-18 ") == Date(2026, 7, 18)


@pytest.mark.parametrize("value", ["yes", "no", "1", "0", "on", "off"])
def test_boolean_default_rejects_undeclared_convenience_tokens(value):
    with pytest.raises(TableError, match=r"Expected one of \['false', 'true'\]"):
        parse_one(boolean(), value)


def test_boolean_supports_an_explicit_domain_vocabulary():
    parser = boolean(
        true_values=("yes", "1", "on"),
        false_values=("no", "0", "off"),
    )

    assert parse_one(parser, "YES") is True
    assert parse_one(parser, "off") is False


def test_boolean_does_not_strip_whitespace_implicitly():
    with pytest.raises(TableError, match="Expected one of"):
        parse_one(boolean(), " true ")

    parser = compose(string(strip=True), boolean())
    assert parse_one(parser, " true ") is True


def test_boolean_case_sensitivity_is_explicit():
    parser = boolean(
        true_values=("YES",),
        false_values=("NO",),
        case_sensitive=True,
    )

    assert parse_one(parser, "YES") is True
    with pytest.raises(TableError, match="Expected one of"):
        parse_one(parser, "yes")


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
    with pytest.raises(TypeError, match="non-string iterable"):
        boolean(true_values="yes")
    with pytest.raises(TypeError, match="contain only strings"):
        boolean(false_values=(False,))
    with pytest.raises(TypeError, match="must be a boolean"):
        boolean(case_sensitive="false")
    with pytest.raises(ValueError, match="at least one"):
        choice()
    with pytest.raises(ValueError, match="cannot be empty"):
        split("")
    with pytest.raises(ValueError, match="at least one parser"):
        compose()
    with pytest.raises(ValueError, match="date format cannot be empty"):
        date_parser(format="")
    with pytest.raises(TypeError, match="date format must be a string"):
        date_parser(format=None)
    with pytest.raises(ValueError, match="datetime format cannot be empty"):
        datetime_parser(format="")
    with pytest.raises(TypeError, match="datetime format must be a string"):
        datetime_parser(format=123)


def test_each_rejects_non_iterable_and_string_results():
    with pytest.raises(TableError, match="non-string iterable"):
        parse_one(each(integer()), "123")
