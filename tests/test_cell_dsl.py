import pytest

from talika import CellDSL, RowTable, TableError, field


def test_exact_token_uses_cell_context():
    dsl = CellDSL()

    @dsl.token("random")
    def random_value(context):
        return f"generated-for-{context.field_name}"

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    item = ContentTable.parse([["headline"], ["random"]])[0]

    assert item.headline == "generated-for-headline"


def test_pattern_uses_full_match_and_named_groups():
    dsl = CellDSL()

    @dsl.pattern(r"(?P<count>\d+):word")
    def words(match, context):
        return [context.field_name] * int(match["count"])

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    items = ContentTable.parse(
        [["headline"], ["3:word"], ["prefix-3:word"], ["3:word-suffix"]]
    )

    assert items[0].headline == ["headline", "headline", "headline"]
    assert items[1].headline == "prefix-3:word"
    assert items[2].headline == "3:word-suffix"


def test_exact_token_has_precedence_over_patterns():
    dsl = CellDSL()

    @dsl.pattern(r".*")
    def catch_all(match, context):
        return "pattern"

    @dsl.token("random")
    def random_value(context):
        return "token"

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    assert ContentTable.parse([["headline"], ["random"]])[0].headline == "token"


def test_first_registered_pattern_wins():
    dsl = CellDSL()

    @dsl.pattern(r"\d+:word")
    def specific(match, context):
        return "first"

    @dsl.pattern(r".*")
    def catch_all(match, context):
        return "second"

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    assert ContentTable.parse([["headline"], ["2:word"]])[0].headline == "first"


def test_unmatched_value_passes_through_by_default():
    dsl = CellDSL()

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    item = ContentTable.parse([["headline"], ["A literal headline"]])[0]

    assert item.headline == "A literal headline"


def test_fallback_can_replace_default_pass_through():
    dsl = CellDSL()

    @dsl.fallback
    def normalize(value, context):
        return value.upper()

    class ContentTable(RowTable):
        category = field("category", parser=dsl)

    assert ContentTable.parse([["category"], ["markets"]])[0].category == "MARKETS"


def test_duplicate_registration_is_rejected():
    dsl = CellDSL()

    @dsl.token("random")
    def first_token(context):
        return "first"

    with pytest.raises(ValueError, match="already registered"):

        @dsl.token("random")
        def second_token(context):
            return "second"

    @dsl.pattern(r"\d+:word")
    def first_pattern(match, context):
        return "first"

    with pytest.raises(ValueError, match="already registered"):

        @dsl.pattern(r"\d+:word")
        def second_pattern(match, context):
            return "second"


def test_empty_tokens_and_duplicate_fallbacks_are_rejected():
    dsl = CellDSL()

    with pytest.raises(ValueError, match="cannot be empty"):
        dsl.token("")

    @dsl.fallback
    def first_fallback(value, context):
        return value

    with pytest.raises(ValueError, match="already registered"):

        @dsl.fallback
        def second_fallback(value, context):
            return value


def test_handler_failure_keeps_table_location_details():
    dsl = CellDSL()

    @dsl.token("broken")
    def broken(context):
        raise RuntimeError("generator unavailable")

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)

    with pytest.raises(TableError, match="generator unavailable") as error:
        ContentTable.parse([["headline"], ["broken"]])

    message = str(error.value)
    assert "field='headline'" in message
    assert "row=2" in message
    assert "column=1" in message
    assert "value='broken'" in message
