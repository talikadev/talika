from talika import (
    CellDSL,
    ParseContext,
    RowTable,
    TableData,
    compose_cell_dsls,
    compose_transformers,
    field,
)


def test_field_scoped_token_does_not_affect_other_fields():
    dsl = CellDSL()

    @dsl.token("random", fields={"headline"})
    def random_headline(context):
        return "Generated headline"

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)
        category = field("category", parser=dsl)

    record = ContentTable.parse([["headline", "category"], ["random", "random"]])[0]

    assert record.headline == "Generated headline"
    assert record.category == "random"


def test_scoped_token_takes_precedence_over_global_token():
    dsl = CellDSL()

    @dsl.token("random")
    def global_random(context):
        return "global"

    @dsl.token("random", fields={"headline"})
    def headline_random(context):
        return "headline"

    class ContentTable(RowTable):
        headline = field("headline", parser=dsl)
        category = field("category", parser=dsl)

    item = ContentTable.parse([["headline", "category"], ["random", "random"]])[0]
    assert item.headline == "headline"
    assert item.category == "global"


def test_predicate_rules_run_after_patterns():
    dsl = CellDSL()

    @dsl.pattern(r"\d+")
    def number(match, context):
        return int(match[0])

    @dsl.when(lambda value, context: value.startswith("QA-"))
    def qa_value(value, context):
        return value.removeprefix("QA-")

    class ValueTable(RowTable):
        value = field("value", parser=dsl)

    records = ValueTable.parse([["value"], ["12"], ["QA-News"]])
    assert [record.value for record in records] == [12, "News"]


def test_cell_dsl_composition_uses_first_matching_dsl():
    shared = CellDSL()
    project = CellDSL()

    @shared.token("none")
    def none_value(context):
        return None

    @project.pattern(r"fake:(.+)")
    def fake_value(match, context):
        return f"generated-{match[1]}"

    parser = compose_cell_dsls(shared, project)

    class ValueTable(RowTable):
        value = field("value", parser=parser)

    records = ValueTable.parse([["value"], ["none"], ["fake:title"], ["literal"]])
    assert [record.value for record in records] == [None, "generated-title", "literal"]


def test_transformer_pipeline_runs_left_to_right_and_preserves_sources(tmp_path):
    class Uppercase:
        def transform(self, table, context, *, schema=None):
            rows = [list(row) for row in table.rows]
            rows[1][0] = rows[1][0].with_value(rows[1][0].value.upper())
            return TableData.from_cells(rows)

    class Prefix:
        def transform(self, table, context, *, schema=None):
            rows = [list(row) for row in table.rows]
            rows[1][0] = rows[1][0].with_value("QA-" + rows[1][0].value)
            return TableData.from_cells(rows)

    pipeline = compose_transformers(Uppercase(), Prefix())
    source = tmp_path / "values.feature"
    transformed = pipeline.transform(
        TableData.from_rows([["value"], ["news"]], source=source), ParseContext()
    )

    assert transformed.to_rows() == [["value"], ["QA-NEWS"]]
    assert transformed.cell(2, 1).source_value == "news"
    assert transformed.source_uri == source.resolve().as_uri()
    assert transformed.cell(2, 1).source_uri == source.resolve().as_uri()


def test_schema_can_use_transformer_pipeline():
    class Uppercase:
        def transform(self, table, context, *, schema=None):
            rows = [list(row) for row in table.rows]
            rows[1][0] = rows[1][0].with_value(rows[1][0].value.upper())
            return TableData.from_cells(rows)

    class ValueTable(RowTable):
        table_transformer = compose_transformers(Uppercase())
        value = field("value")

    assert ValueTable.parse([["value"], ["news"]])[0].value == "NEWS"
