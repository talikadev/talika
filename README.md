# talika

`talika` adds small, dataclass-style schemas to BDD data tables. It parses the
raw list-of-lists supplied by tools such as `pytest-bdd`, validates the table
shape, converts cells with project-defined parsers, and returns typed schema
records.

It does not prescribe a table DSL or perform business actions. Projects define
their own readable table vocabulary while `talika` handles the repeatable
parts: shape validation, conversion, source-aware diagnostics, and optional
static checks for `.feature` files.

## Links

- Documentation: <https://talikadev.github.io/talika/>
- Source: <https://github.com/talikadev/talika>
- Issues: <https://github.com/talikadev/talika/issues>
- PyPI: <https://pypi.org/project/talika/>

## Installation

`talika` supports Python 3.10 and newer. The core package has no runtime
dependencies:

```bash
pip install talika
```

Install optional extras only for integrations you use:

```bash
pip install "talika[cli]"       # static Gherkin feature-file checks
pip install "talika[pydantic]"  # Pydantic output models
pip install "talika[test]"      # test/integration dependencies
```

The command-line tool is available as both `talika` and `python -m talika`.

## Quick Start

```python
from talika import RowTable, field


def parse_bool(value, context):
    return value.lower() == "true"


class UserTable(RowTable):
    name = field("name", required=True)
    role = field("role", required=True)
    active = field("active", parser=parse_bool, default=True)


users = UserTable.parse(
    [
        ["name", "role", "active"],
        ["Alice", "admin", "true"],
    ]
)

assert users[0].name == "Alice"
assert users[0].active is True
```

## Table Shapes

Row-oriented tables use the first row as labels and every following row as one
record:

```python
from talika import RowTable, field


class ProductTable(RowTable):
    sku = field("sku", required=True)
    name = field("name", required=True)
```

Column-oriented tables use the first column as labels and every following
column as one record:

```python
from talika import ColumnTable, field, id_field


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)
    headline = field("Headline*", required=True)
    category = field("Category")


items = ContentTable.parse(
    [
        ["IDs", "1", "2"],
        ["Type*", "Article", "Poll"],
        ["Headline*", "Hello", "QA Poll"],
    ]
)

assert items[0].id == "1"
assert items[1].content_type == "Poll"
assert items[0].category is None
```

Use `parse_records()` when you specifically want schema instances for static
typing or when a schema has an `output_model` but a test needs the intermediate
validated record:

```python
records: list[ContentTable] = ContentTable.parse_records(datatable)
```

Functional helpers are also available:

```python
from talika import parse_table, parse_table_records

items = parse_table(ContentTable, datatable)
records = parse_table_records(ContentTable, datatable)
```

## Conversion

Common field conversion does not require custom functions:

```python
from talika import RowTable, boolean, compose, decimal, each, field, split, string


class ProductTable(RowTable):
    price = field("price", parser=decimal())
    active = field("active", parser=boolean())
    tags = field("tags", parser=compose(split(","), each(string(strip=True))))
```

The package provides `string`, `integer`, `floating`, `decimal`, `boolean`,
`choice`, `split`, `map_value`, `optional`, `compose`, and `each`.

Supported annotations infer a parser when the field has no explicit parser:

```python
class UserTable(RowTable):
    name: str = field("name")
    age: int | None = field("age")
    active: bool = field("active")
```

Inference supports `str`, `int`, `float`, `bool`, `Decimal`, enums, string
`Literal` values, and simple optionals. Collection annotations such as
`list[str]` do not imply a cell syntax; use an explicit parser such as
`split(",")` when one cell should become several values.

## Defaults, Aliases, And Policies

Missing optional fields can use static defaults or context-aware factories:

```python
headline = field(
    "Headline",
    default_factory=lambda context: (
        context.user_data["generator"].headline(context.item_id)
    ),
)
```

Aliases support intentional wording changes:

```python
headline = field("Headline", aliases=("Title", "Name"))
```

Unknown fields currently accept only the default `unknown_fields = "forbid"`
policy. Discriminated schemas also support `inapplicable_fields = "forbid"`
and `inapplicable_fields = "preserve"` for variant-specific values.

## Variants

Variants let one BDD table contain several related record shapes. The base
schema declares shared fields and a discriminator used to select the applicable
fields and behavior.

```python
from talika import ColumnTable, TableFields, discriminator, field, id_field, split


class ArticleFields(TableFields):
    body = field("Body*", required=True)


class PollFields(TableFields):
    options: list[str] = field("Options*", required=True, parser=split(","))


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = discriminator(
        "Type*",
        variants={
            "Article": ArticleFields,
            "Poll": PollFields,
        },
    )
    headline = field("Headline*", required=True)
```

The explicit decorator form is also available with `discriminator_field()` and
`@ContentTable.variant(...)`.

## Custom Cell Syntax

`CellDSL` groups exact tokens and full-match regular-expression rules into a
reusable field parser. The package owns dispatch; your project owns the
meaning.

```python
from talika import CellDSL, ColumnTable, field, id_field

content_cells = CellDSL()


@content_cells.token("random")
def random_value(context):
    return context.user_data["generator"].random_for(context.field_name)


@content_cells.pattern(r"(?P<count>\d+):word")
def generated_words(match, context):
    count = int(match["count"])
    return context.user_data["generator"].words(count)


class ContentTable(ColumnTable):
    id = id_field("IDs")
    headline = field("Headline*", required=True, parser=content_cells)
```

Exact tokens run before patterns. Patterns are tried in registration order and
must match the whole cell. Values that match no rule pass through unchanged.
Rules may be scoped by schema attribute name, and several DSLs may be composed
with `compose_cell_dsls(...)`.

## Validation And Diagnostics

Override `validate_record()` to check rules involving one parsed record:

```python
class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)
    headline = field("Headline*", required=True)

    def validate_record(self, context):
        if self.content_type == "Poll" and not self.headline.endswith("?"):
            raise ValueError("Poll headlines must end with a question mark")
```

Use `validate_records()` for relationships involving several records. Failures
become `TableError` instances with stable error codes and source coordinates.
In collect mode, independent diagnostics are grouped into `TableErrors`:

```python
from talika import TableErrors

try:
    ContentTable.parse(datatable, error_mode="collect")
except TableErrors as errors:
    for error in errors:
        print(error.code, error.row, error.column, error.message)
```

Schema records expose immutable source metadata:

```python
record.table_source.row
record.table_source.column
record.table_source.item_id
record.source_for("headline")
```

## Output Models

Set `output_model` to return project objects after schema and table validation:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    name: str
    age: int


class UserTable(RowTable):
    output_model = User

    name = field("name")
    age: int = field("age")
```

Dataclasses and other keyword-constructed classes need no integration
dependency. Pydantic v2 works through the optional `talika[pydantic]` extra.
Override `build_output(record, context)` when construction needs a custom
signature, selected fields, source metadata, or project services.

## Table Transformations

`ColumnGroupExpander` handles a common compact table convention where one
source column describes one item or a group of items:

```python
from talika import ColumnGroupExpander, NumericRange, PrefixRepeat


class ContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(separator=".."),
        repeat_rule=PrefixRepeat(separator=":"),
    )

    id = id_field("IDs")
    content_type = field("Type*", required=True)
```

Projects can also implement compatible `RangeRule` and `RepeatRule` objects or
override `transform_table()` for table syntax that does not fit the reusable
grouped-column shape.

## pytest Integration

Installing the package registers a `talika` fixture:

```python
def content_exists(datatable, talika, faker):
    return talika.parse(
        datatable,
        schema=ContentTable,
        context={"faker": faker},
    )
```

The fixture also exposes `parse_records()` for type-checker-friendly schema
records.

## Static Feature Checking

Install the optional CLI extra to validate feature tables without executing
pytest scenarios:

```powershell
pip install "talika[cli]"
talika check features/content.feature `
  --schema tests/support/content_schema.py:ContentTable `
  --step "the following content exists:"
```

Machine-readable diagnostics are available for CI and editor integrations:

```powershell
talika check features/content.feature `
  --schema tests/support/content_schema.py:ContentTable `
  --step "the following content exists:" `
  --format json
```

Use `describe` to inspect a schema without parsing a feature file:

```powershell
talika describe tests/support/content_schema.py:ContentTable
talika describe tests/support/content_schema.py:ContentTable --format json
```

The checker uses the official Gherkin parser and reports exact feature-file
coordinates. Importable `module:Schema` references are also supported. Use
`--context-factory module:function` for deterministic parser dependencies.
Scenario-outline substitutions are not expanded.

## Development

```powershell
uv sync --all-extras --dev
uv run pytest -p no:cacheprovider
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests/typing/public_api.py
uv build
```

The documentation site is built with Zensical:

```powershell
uv run --group docs zensical build --strict
```

GitHub Pages is configured for <https://talikadev.github.io/talika/> through
the `Docs` workflow in `.github/workflows/docs.yml`.
