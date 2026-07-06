# --8<-- [start:feature-content]
Feature: CMS content relationships

  Scenario: Build linked content from one table
    Given the content items:
      | IDs      | ROOT      | A-1          | P-1         |
      | Headline | Home      | Launch story | Reader poll |
      | Parent   |           | ROOT         | ROOT        |
      | Related  | A-1, P-1 | P-1          |             |
    Then parent and related content references resolve
# --8<-- [end:feature-content]

# --8<-- [start:content-schema]
from talika import (
    ColumnTable,
    RowTable,
    TableError,
    field,
    id_field,
    integer,
    reference,
)


class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline", required=True)
    parent = reference("Parent")
    related = reference("Related", many=True)
# --8<-- [end:content-schema]

# --8<-- [start:content-table]
content_table = [
    ["IDs", "ROOT", "A-1", "P-1"],
    ["Headline", "Home", "Launch story", "Reader poll"],
    ["Parent", "", "ROOT", "ROOT"],
    ["Related", "A-1, P-1", "P-1", ""],
]
# --8<-- [end:content-table]

# --8<-- [start:single-reference]
root, article, poll = ContentTable.parse(content_table)

assert root.parent is None
assert article.parent is root
assert poll.parent is root
assert article.parent.headline == "Home"
# --8<-- [end:single-reference]

# --8<-- [start:single-reference-output]
>> article.id
'A-1'

>> article.parent.id
'ROOT'

>> article.parent.headline
'Home'
# --8<-- [end:single-reference-output]

# --8<-- [start:many-reference]
root, article, poll = ContentTable.parse(content_table)

assert root.related == [article, poll]
assert article.related == [poll]
assert poll.related == []
# --8<-- [end:many-reference]

# --8<-- [start:many-reference-output]
>> [item.id for item in root.related]
['A-1', 'P-1']

>> [item.id for item in article.related]
['P-1']

>> poll.related
[]
# --8<-- [end:many-reference-output]

# --8<-- [start:typed-schema]
class TypedContentTable(ColumnTable):
    id = id_field("IDs", parser=integer())
    headline = field("Headline")
    parent = reference("Parent")
# --8<-- [end:typed-schema]

# --8<-- [start:typed-parse]
parent, child = TypedContentTable.parse(
    [
        ["IDs", "101", "102"],
        ["Headline", "Root", "Child"],
        ["Parent", "", "101"],
    ]
)
# --8<-- [end:typed-parse]

# --8<-- [start:typed-output]
>> parent.id
101

>> type(parent.id).__name__
'int'

>> child.parent is parent
True
# --8<-- [end:typed-output]

# --8<-- [start:target-schema]
class SlugContentTable(ColumnTable):
    id = id_field("IDs")
    slug = field("Slug", required=True)
    parent = reference("Parent slug", target="slug")
# --8<-- [end:target-schema]

# --8<-- [start:target-parse]
home, child = SlugContentTable.parse(
    [
        ["IDs", "1", "2"],
        ["Slug", "home", "child"],
        ["Parent slug", "", "home"],
    ]
)

assert child.parent is home
assert child.parent.id == "1"
# --8<-- [end:target-parse]

# --8<-- [start:validation-schema]
class ValidatedContentTable(ColumnTable):
    id = id_field("IDs")
    parent = reference("Parent")

    def validate_record(self, context):
        if self.parent is self:
            raise TableError.from_cell(
                "Content cannot reference itself",
                self.source_for("parent"),
                schema=type(self),
            )
# --8<-- [end:validation-schema]

# --8<-- [start:validation-call]
ValidatedContentTable.parse(
    [
        ["IDs", "ROOT"],
        ["Parent", "ROOT"],
    ]
)
# --8<-- [end:validation-call]

# --8<-- [start:validation-output]
Content cannot reference itself (code=table_error, schema=ValidatedContentTable, row=2, column=2, value='ROOT')
# --8<-- [end:validation-output]

# --8<-- [start:missing-reference]
ContentTable.parse(
    [
        ["IDs", "ROOT", "A-1"],
        ["Headline", "Home", "Article"],
        ["Parent", "", "MISSING"],
        ["Related", "", ""],
    ]
)
# --8<-- [end:missing-reference]

# --8<-- [start:missing-reference-output]
Reference target 'MISSING' was not found (code=reference_failed, schema=ContentTable, field='Parent', row=3, column=3, item_id='A-1', value='MISSING')
# --8<-- [end:missing-reference-output]

# --8<-- [start:duplicate-target-schema]
class DuplicateSlugTable(ColumnTable):
    id = id_field("IDs")
    slug = field("Slug")
    parent = reference("Parent slug", target="slug")
# --8<-- [end:duplicate-target-schema]

# --8<-- [start:duplicate-target-call]
DuplicateSlugTable.parse(
    [
        ["IDs", "1", "2", "3"],
        ["Slug", "same", "same", "child"],
        ["Parent slug", "", "", "same"],
    ]
)
# --8<-- [end:duplicate-target-call]

# --8<-- [start:duplicate-target-output]
Reference target 'same' is not unique (code=reference_failed, schema=DuplicateSlugTable, field='Slug', row=2, column=3, value='same')
# --8<-- [end:duplicate-target-output]

# --8<-- [start:conversion-error]
TypedContentTable.parse(
    [
        ["IDs", "101", "102"],
        ["Headline", "Root", "Child"],
        ["Parent", "", "abc"],
    ]
)
# --8<-- [end:conversion-error]

# --8<-- [start:conversion-error-output]
Reference key conversion failed: invalid literal for int() with base 10: 'abc' (code=reference_failed, schema=TypedContentTable, field='Parent', row=3, column=3, item_id=102, value='abc')
# --8<-- [end:conversion-error-output]

# --8<-- [start:row-schema]
class TaskTable(RowTable):
    key = id_field("key")
    title = field("title")
    depends_on = reference("depends on", target="key")
# --8<-- [end:row-schema]

# --8<-- [start:row-parse]
setup, login = TaskTable.parse(
    [
        ["key", "title", "depends on"],
        ["setup", "Create account", ""],
        ["login", "Sign in", "setup"],
    ]
)

assert setup.depends_on is None
assert login.depends_on is setup
# --8<-- [end:row-parse]
