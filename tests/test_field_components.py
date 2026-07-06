from talika import RowTable, TableFields, field


class AuditFields(TableFields):
    created_by = field("created_by")
    trace_id = field("trace_id")


def test_component_fields_are_collected_by_concrete_schema():
    class ArticleTable(RowTable, AuditFields):
        headline = field("headline")

    article = ArticleTable.parse(
        [
            ["headline", "created_by", "trace_id"],
            ["News", "Alice", "trace-1"],
        ]
    )[0]

    assert article.headline == "News"
    assert article.created_by == "Alice"
    assert article.trace_id == "trace-1"


def test_component_fields_are_cloned_per_schema():
    class FirstTable(RowTable, AuditFields):
        value = field("value")

    class SecondTable(RowTable, AuditFields):
        value = field("value")

    first = FirstTable.__fields__["created_by"]
    second = SecondTable.__fields__["created_by"]

    assert first is not second
