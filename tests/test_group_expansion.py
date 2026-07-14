import pytest

from talika import (
    AlphabeticRange,
    ColumnGroupExpander,
    ColumnTable,
    NumericRange,
    ParseContext,
    PrefixRepeat,
    SuffixRepeat,
    TableCell,
    TableData,
    TableError,
    field,
    id_field,
)


def source_cell(value="value", row=1, column=1):
    return TableCell.from_value(value, row=row, column=column)


@pytest.mark.parametrize(
    ("rule", "value", "expected"),
    [
        (NumericRange(".."), "1..3", ["1", "2", "3"]),
        (NumericRange("-"), "7-9", ["7", "8", "9"]),
        (NumericRange(".."), "single", ["single"]),
        (AlphabeticRange("-"), "A-C", ["A", "B", "C"]),
        (AlphabeticRange(".."), "a..c", ["a", "b", "c"]),
        (AlphabeticRange("-"), "single", ["single"]),
    ],
)
def test_range_rules_expand_configured_syntax(rule, value, expected):
    cells = rule.expand(source_cell(value), ParseContext())

    assert [cell.value for cell in cells] == expected
    assert all(cell.source_value == value for cell in cells)


@pytest.mark.parametrize(
    ("rule", "value", "message"),
    [
        (NumericRange(".."), "3..1", "must be ascending"),
        (NumericRange(".."), "one..three", "Invalid numeric range"),
        (NumericRange(".."), "1..2..3", "Invalid numeric range"),
        (AlphabeticRange("-"), "C-A", "must be ascending"),
        (AlphabeticRange("-"), "A-c", "Invalid alphabetic range"),
        (AlphabeticRange("-"), "AA-BB", "Invalid alphabetic range"),
    ],
)
def test_range_rules_reject_invalid_recognized_syntax(rule, value, message):
    with pytest.raises(ValueError, match=message):
        rule.expand(source_cell(value), ParseContext())


@pytest.mark.parametrize(
    ("rule", "value", "count", "expected"),
    [
        (PrefixRepeat(":"), "3:Article", 3, ["Article"] * 3),
        (PrefixRepeat("=>"), "2=>Poll", 2, ["Poll"] * 2),
        (PrefixRepeat(":"), "News: Europe", 2, ["News: Europe"] * 2),
        (SuffixRepeat(" x"), "Article x3", 3, ["Article"] * 3),
        (SuffixRepeat("*"), "Poll*2", 2, ["Poll"] * 2),
        (SuffixRepeat(" x"), "Version xnext", 2, ["Version xnext"] * 2),
    ],
)
def test_repeat_rules_expand_or_copy_values(rule, value, count, expected):
    cells = rule.expand(source_cell(value), count, ParseContext())

    assert [cell.value for cell in cells] == expected
    assert all(cell.source_value == value for cell in cells)


@pytest.mark.parametrize(
    ("rule", "value", "count", "message"),
    [
        (PrefixRepeat(":"), "2:Article", 3, "does not match"),
        (PrefixRepeat(":"), "3:", 3, "cannot be empty"),
        (SuffixRepeat(" x"), "Article x2", 3, "does not match"),
        (SuffixRepeat(" x"), " x3", 3, "cannot be empty"),
    ],
)
def test_repeat_rules_reject_invalid_recognized_syntax(rule, value, count, message):
    with pytest.raises(ValueError, match=message):
        rule.expand(source_cell(value), count, ParseContext())


def test_empty_separator_errors_are_clear():
    for rule_type in (NumericRange, AlphabeticRange, PrefixRepeat, SuffixRepeat):
        with pytest.raises(ValueError, match="separator cannot be empty"):
            rule_type("")


def test_column_group_expander_handles_group_mechanics():
    expander = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(".."),
        repeat_rule=PrefixRepeat(":"),
    )
    table = TableData.from_rows(
        [
            ["IDs", "1..3", "4"],
            ["Type", "3:Article", "Poll"],
            ["Headline", "Shared", "Vote?"],
        ]
    )

    expanded = expander.transform(table, ParseContext(), schema="ContentTable")

    assert expanded.to_rows() == [
        ["IDs", "1", "2", "3", "4"],
        ["Type", "Article", "Article", "Article", "Poll"],
        ["Headline", "Shared", "Shared", "Shared", "Vote?"],
    ]
    assert expanded.cell(2, 4).source_value == "3:Article"
    assert expanded.cell(3, 3).source_value == "Shared"


def test_schema_uses_declarative_table_transformer():
    class ContentTable(ColumnTable):
        table_transformer = ColumnGroupExpander(
            key_row="IDs",
            range_rule=NumericRange(".."),
            repeat_rule=PrefixRepeat(":"),
        )

        id = id_field("IDs")
        content_type = field("Type")

    items = ContentTable.parse(
        [
            ["IDs", "1..2"],
            ["Type", "2:Article"],
        ]
    )

    assert [item.id for item in items] == ["1", "2"]
    assert [item.content_type for item in items] == ["Article", "Article"]


def test_custom_transform_override_remains_available():
    class ContentTable(ColumnTable):
        table_transformer = ColumnGroupExpander(
            key_row="IDs",
            range_rule=NumericRange(".."),
            repeat_rule=PrefixRepeat(":"),
        )

        id = id_field("IDs")
        content_type = field("Type")

        @classmethod
        def transform_table(cls, table, context):
            rows = [list(row) for row in table.rows]
            rows[1][1] = rows[1][1].with_value("Custom")
            return TableData.from_cells(rows)

    item = ContentTable.parse([["IDs", "1"], ["Type", "Article"]])[0]

    assert item.content_type == "Custom"


def test_repeat_error_points_to_original_cell_and_schema():
    class ContentTable(ColumnTable):
        table_transformer = ColumnGroupExpander(
            key_row="IDs",
            range_rule=NumericRange(".."),
            repeat_rule=PrefixRepeat(":"),
        )

        id = id_field("IDs")
        content_type = field("Type")

    with pytest.raises(TableError, match="does not match") as error:
        ContentTable.parse(
            [
                ["IDs", "1..3"],
                ["Type", "2:Article"],
            ]
        )

    assert error.value.schema == "ContentTable"
    assert error.value.row == 2
    assert error.value.column == 2
    assert error.value.value == "2:Article"


def test_key_row_and_rectangular_shape_are_validated():
    expander = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(".."),
        repeat_rule=PrefixRepeat(":"),
    )

    with pytest.raises(TableError, match="Expected key row"):
        expander.transform(
            TableData.from_rows([["Keys", "1"]]),
            ParseContext(),
            schema="ContentTable",
        )

    with pytest.raises(TableError, match="rectangular"):
        expander.transform(
            TableData.from_rows([["IDs", "1"], ["Type"]]),
            ParseContext(),
            schema="ContentTable",
        )


def test_custom_rules_receive_context_and_can_define_new_syntax():
    seen = {}

    class CustomRange:
        def expand(self, cell, context):
            seen["range_mode"] = context.user_data["mode"]
            return [cell.with_value("left"), cell.with_value("right")]

    class CustomRepeat:
        def expand(self, cell, expected_count, context):
            seen["repeat_mode"] = context.user_data["mode"]
            return [cell.with_value(f"{cell.value}-{index}") for index in range(2)]

    expander = ColumnGroupExpander(
        key_row="Keys",
        range_rule=CustomRange(),
        repeat_rule=CustomRepeat(),
    )
    context = ParseContext.from_value({"mode": "custom"})

    result = expander.transform(
        TableData.from_rows([["Keys", "pair"], ["Value", "item"]]),
        context,
    )

    assert result.to_rows() == [
        ["Keys", "left", "right"],
        ["Value", "item-0", "item-1"],
    ]
    assert seen == {"range_mode": "custom", "repeat_mode": "custom"}


def test_custom_rules_must_return_cells_and_correct_counts():
    class BadRange:
        def expand(self, cell, context):
            return ["not-a-cell"]

    class ShortRepeat:
        def expand(self, cell, expected_count, context):
            return [cell]

    with pytest.raises(TableError, match="must return TableCell"):
        ColumnGroupExpander(
            key_row="Keys",
            range_rule=BadRange(),
            repeat_rule=PrefixRepeat(":"),
        ).transform(
            TableData.from_rows([["Keys", "pair"]]),
            ParseContext(),
        )

    with pytest.raises(TableError, match="produced 1 values"):
        ColumnGroupExpander(
            key_row="Keys",
            range_rule=NumericRange(".."),
            repeat_rule=ShortRepeat(),
        ).transform(
            TableData.from_rows([["Keys", "1..2"], ["Value", "item"]]),
            ParseContext(),
        )


def test_numeric_range_allows_ten_thousand_keys():
    cells = NumericRange().expand(source_cell("1..10000"), ParseContext())

    assert len(cells) == 10_000
    assert cells[-1].value == "10000"


def test_numeric_range_limit_is_source_aware_through_the_expander():
    expander = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(),
        repeat_rule=PrefixRepeat(),
    )

    with pytest.raises(TableError) as captured:
        expander.transform(
            TableData.from_rows([["IDs", "1..10001"]]),
            ParseContext(),
            schema="ContentTable",
        )

    assert captured.value.code == "expansion_limit"
    assert captured.value.row == 1
    assert captured.value.column == 2
    assert captured.value.value == "1..10001"
