# talika

`talika` adds small, dataclass-style schemas to BDD data tables. It parses
the raw list-of-lists supplied by tools such as `pytest-bdd`, validates the
table shape, converts cells with project-defined parsers, and returns typed
schema records.

It does not prescribe a table DSL or perform business actions. Projects may
select reusable syntax rules, provide their own rule objects, or implement a
fully custom table transformation.

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
pip install "talika[test]"      # project test and runnable example dependencies
```

The command-line tool is available as both `talika` and
`python -m talika`.

## Row-oriented tables

```python
from talika import RowTable, field


def parse_bool(value, context):
    return value.lower() == "true"


class UserTable(RowTable):
    name = field("name", required=True)
    role = field("role", required=True)
    active = field("active", parser=parse_bool, default=True)


users = UserTable.parse([
    ["name", "role", "active"],
    ["Alice", "admin", "true"],
])

assert users[0].name == "Alice"
assert users[0].active is True
```

## Column-oriented tables

```python
from talika import ColumnTable, field, id_field


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)
    headline = field("Headline*", required=True)
    category = field("Category")


items = ContentTable.parse([
    ["IDs", "1", "2"],
    ["Type*", "Article", "Poll"],
    ["Headline*", "Hello", "QA Poll"],
])

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

If your codebase prefers explicit parser functions, use the functional
equivalent:

```python
from talika import parse_table, parse_table_records

items = parse_table(ContentTable, datatable)
records = parse_table_records(ContentTable, datatable)
```

These helpers delegate to the schema methods. They exist for API style, not as
a second parsing lifecycle.

## Discriminated record variants

Use variants when one BDD table contains several related record shapes. The
base schema declares fields shared by every item and one discriminator used to
select the applicable fields and behavior.

The concise form maps values to reusable `TableFields` components:

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

Components may contain field declarations, annotations, custom parsers,
`validate_record()` methods, references, and `output_model` configuration. A
selected record is an instance of both the base table and its field component.
`ContentTable.variant_for("Article")` returns its generated concrete schema
class.

The explicit form remains available when projects want to name and define the
variant schema classes directly:

```python
from talika import ColumnTable, discriminator_field, field, id_field, split


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = discriminator_field("Type*")
    headline = field("Headline*", required=True)


@ContentTable.variant("Article")
class ArticleContent(ContentTable):
    body = field("Body*", required=True)


@ContentTable.variant("Poll")
class PollContent(ContentTable):
    options: list[str] = field("Options*", required=True, parser=split(","))
```

The table may include the union of the variant fields:

```gherkin
| IDs       | 1            | 2         |
| Type*     | Article      | Poll      |
| Headline* | Market news  | Choose?   |
| Body*     | Article body |           |
| Options*  |              | Yes, No   |
```

Required fields are checked against the selected variant. Empty cells for a
different variant are ignored, while non-empty inapplicable cells are rejected
with their source location. Returned schema records are instances of the
selected subclasses, so each variant can define its own parsers,
`validate_record()` implementation, references, and `output_model`.

The discriminator parser runs before variant lookup. Register parsed values
such as enum members when the discriminator uses a custom or inferred parser.
See [`examples/content_variants`](examples/content_variants) for
column-oriented validation and
[`examples/payment_variants`](examples/payment_variants) for row-oriented
dataclass outputs. The
[`examples/complete_content_variants`](examples/complete_content_variants)
folder combines declarative variants with group expansion, a custom cell DSL,
annotation conversion, context validation, references, source metadata, and
variant-specific output models.

Custom parsers receive the raw value and a `CellContext`. Project data passed
to `parse(..., context={...})` is available through `context.user_data`.

```python
def parse_headline(value, context):
    if value == "random":
        return context.user_data["faker"].headline()
    return value
```

After table transformation, the parser's `value` argument is the current
logical value while `context.source_value` contains the original feature text.
For an expanded `3:Article` cell, these may be `Article` and `3:Article`.

## Defaults, aliases, and additional fields

Missing optional fields can use project-aware factories:

```python
headline = field(
    "Headline",
    default_factory=lambda context: (
        context.user_data["generator"].headline(context.item_id)
    ),
)
```

Factories run only when the entire field is absent. Explicit empty cells stay
empty. Aliases support intentional wording changes:

```python
headline = field("Headline", aliases=("Title", "Name"))
```

Unknown fields default to `"forbid"`; set `unknown_fields` to `"ignore"` or
`"preserve"`. Preserved values are exposed through `record.table_extras`.
Discriminated schemas provide the equivalent `inapplicable_fields` policy. See
[`examples/defaults_aliases_policies`](examples/defaults_aliases_policies).

## Reusable custom cell DSLs

`CellDSL` groups exact tokens and full-match regular-expression rules into a
reusable field parser. The package owns dispatch; your project owns every
meaning.

```python
from talika import CellDSL

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
See [`examples/custom_cell_dsl`](examples/custom_cell_dsl) for a complete
pytest-bdd example with deterministic generated values and assertions.

Rules may be scoped by schema attribute name and several DSLs may be chained:

```python
@content_cells.token("random", fields={"headline"})
def random_headline(context):
    return context.user_data["generator"].headline()


parser = compose_cell_dsls(shared_cells, content_cells)
```

`CellDSL.when()` supports predicate matching after tokens and patterns. See
[`examples/composable_dsl`](examples/composable_dsl).

## Reusable field parsers

Common field conversion does not require custom functions:

```python
class ProductTable(RowTable):
    price = field("price", parser=decimal())
    active = field("active", parser=boolean())
    tags = field(
        "tags",
        parser=compose(split(","), each(string(strip=True))),
    )
```

The package provides `string`, `integer`, `floating`, `decimal`, `boolean`,
`choice`, `split`, `map_value`, and `optional`. `compose` creates a left-to-right
pipeline and `each` applies one parser to every iterable member. See
[`examples/field_parsers`](examples/field_parsers).

## Annotation-driven conversion

Supported annotations infer a parser when the field has no explicit parser:

```python
class UserTable(RowTable):
    name: str = field("name")
    age: int | None = field("age")
    active: bool = field("active")
    reviewer: int | None = field("reviewer")
```

Inference supports `str`, `int`, `float`, `bool`, `Decimal`, enums, string
`Literal` values, and simple optionals. Collection annotations such as
`list[str]` do not imply a cell syntax; use an explicit parser such as
`split(",")` when one cell should become several values. Explicit parsers take
precedence, and unsupported annotations leave raw values unchanged. See
[`examples/annotated_schema`](examples/annotated_schema).

## Reusable field components

`TableFields` shares declarations without creating another parser lifecycle:

```python
class AuditFields(TableFields):
    created_by = field("created_by")
    trace_id = field("trace_id")


class ArticleTable(RowTable, AuditFields):
    headline = field("headline")
```

See [`examples/field_components`](examples/field_components).

## Record validation

Override `validate_record()` to check rules involving multiple parsed fields.
The hook runs after field parsing and defaults have completed.

```python
class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)
    headline = field("Headline*", required=True)

    def validate_record(self, context):
        if self.content_type == "Poll" and not self.headline.endswith("?"):
            raise ValueError("Poll headlines must end with a question mark")
```

Validation can also use dependencies supplied for the parse operation:

```python
def validate_record(self, context):
    allowed_roles = context.user_data["allowed_roles"]
    if self.role not in allowed_roles:
        raise ValueError(f"Unsupported role: {self.role}")
```

Failures become `TableError` instances with the source row, or the item
column and ID for column-oriented tables. See
[`examples/record_validation`](examples/record_validation) and
[`examples/context_validation`](examples/context_validation) for separate,
complete pytest-bdd examples.

## Record source metadata

Schema records expose their original table locations:

```python
record.table_source.row
record.table_source.column
record.table_source.item_id
record.source_for("headline")
```

The metadata is immutable and uses schema attribute names for field lookup.
It enables project validators to raise precise `TableError.from_cell()`
errors. See [`examples/record_sources`](examples/record_sources).

## Whole-table validation

Use `validate_records()` for relationships involving several records:

```python
@classmethod
def validate_records(cls, records, context):
    emails = [record.email for record in records]
    if len(emails) != len(set(emails)):
        raise ValueError("Emails must be unique")
```

It runs after references resolve and after every record exists. Validators can
use `record.source_for(...)` to report a precise offending cell. See
[`examples/table_validation`](examples/table_validation).

## Output models

Set `output_model` to return project objects after schema and table validation:

```python
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
dependency. Pydantic v2 uses the same contract through the optional
`talika[pydantic]` extra. See [`examples/output_models`](examples/output_models)
and [`examples/pydantic_output`](examples/pydantic_output).

Override `build_output(record, context)` when construction needs a custom
signature, selected fields, source metadata, or project services. See
[`examples/output_factory`](examples/output_factory).

## Collected diagnostics

Parsing is fail-fast by default. Authoring tools can collect independent
errors from several cells or records:

```python
try:
    ContentTable.parse(datatable, error_mode="collect")
except TableErrors as errors:
    for error in errors:
        print(error.code, error.row, error.column, error.message)
```

Every `TableError` has a stable string `code`. Collection stops before
dependent reference or table validation when earlier failures make those
stages unreliable. See [`examples/collected_errors`](examples/collected_errors).

## Schema introspection

`ContentTable.describe()` returns an immutable `TableContract` containing its
orientation, fields, aliases, defaults, parser names, policies, references,
variants, transformer, and output configuration. `as_dict()` supports project
documentation and editor tooling. See
[`examples/schema_introspection`](examples/schema_introspection).

## Local record references

Resolve scenario-local IDs to other records in the same table:

```python
class ContentTable(ColumnTable):
    id = id_field("IDs")
    parent = reference("Parent")
    related = reference("Related", many=True)
```

References resolve before validation, allowing rules involving linked records.
Missing targets point to the original reference cell. See
[`examples/record_references`](examples/record_references).

## Source-aware tables

Raw pytest-bdd rows are converted to `TableData` before parsing. Each
`TableCell` carries its current value together with the original feature-file
row, column, and source value.

```python
table = TableData.from_rows(datatable)
cell = table.cell(row=2, column=3)

assert cell.value == "Article"
assert cell.source_row == 2
assert cell.source_column == 3
```

Most schemas can continue accepting raw datatables directly. Projects use the
source-aware API when implementing table-level syntax. See
[`examples/table_data`](examples/table_data) for the focused model example.

## Custom table transformations

### Declarative grouped columns

For the common convention where one source column describes one item or a
group of items, configure `ColumnGroupExpander` with explicit range and repeat
rules:

```python
from talika import (
    ColumnGroupExpander,
    NumericRange,
    PrefixRepeat,
)


class ContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange(separator=".."),
        repeat_rule=PrefixRepeat(separator=":"),
    )

    id = id_field("IDs")
    content_type = field("Type*", required=True)
```

This interprets `1..3` as an inclusive numeric range and `3:Article` as a
prefix repeat. Alternative reusable rules include:

```python
ColumnGroupExpander(
    key_row="Keys",
    range_rule=AlphabeticRange(separator="-"),
    repeat_rule=SuffixRepeat(separator=" x"),
)
```

That configuration supports `A-C` and `Article x3`.

The rule names communicate semantics; separators only configure their surface
syntax. A separator alone is not expected to explain whether `A-C` is an
alphabetic range, numeric range, date range, or literal text.

Projects can implement `RangeRule` and `RepeatRule` compatible objects for
new grammars while reusing the group mechanics. See
[`examples/custom_group_rules`](examples/custom_group_rules) for `R1~R3` and
`[3]Article`.

Several reusable transformers can run left to right:

```python
table_transformer = compose_transformers(
    NormalizeLabels(),
    ColumnGroupExpander(...),
)
```

Each stage must return `TableData` and preserves original source coordinates.
See [`examples/transformer_pipeline`](examples/transformer_pipeline).

### Full transformation hook

Override `transform_table()` to replace compact project syntax with the
logical table that normal schema parsing should consume. Use this lower-level
hook when the table is not a grouped-column shape or requires substantially
different mechanics:

```python
class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type*", required=True)

    @classmethod
    def transform_table(cls, table, context):
        # Interpret the project's own range and repeat conventions.
        return TableData.from_cells(transformed_rows)
```

The hook must return `TableData`. Changed cells should be created with
`source_cell.with_value(new_value)` so parsing and validation errors still
point to the compact source cell.

The parsing lifecycle is:

1. Convert raw rows to `TableData`.
2. Run `transform_table()`.
3. Validate table shape and the union of declared variant fields.
4. Parse a discriminator and select a variant when variants are registered.
5. Run the selected schema's field and `CellDSL` parsers.
6. Build source-aware schema records.
7. Resolve local record references.
8. Run the selected schema's `validate_record()` for each record.
9. Run the base schema's `validate_records()` for the complete table.
10. Construct the selected schema's optional output model.

The following examples show both reusable and fully replaceable conventions:

- [`examples/numeric_table_transform`](examples/numeric_table_transform):
  `1..3` and `3:Article`.
- [`examples/alphabetic_table_transform`](examples/alphabetic_table_transform):
  `A-C` and `Article x3`.
- [`examples/custom_group_rules`](examples/custom_group_rules): custom
  `R1~R3` and `[3]Article` rule objects.

## pytest fixture

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
records:

```python
def content_exists(datatable, talika):
    records = talika.parse_records(datatable, schema=ContentTable)
    assert records[0].headline
```

Most users should start with `Schema.parse()`. Use `parse_table()` when a
functional parser call reads better. Use the `talika` fixture when pytest
dependency injection keeps a step definition cleaner.

## Static feature checking

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
Scenario-outline substitutions are not expanded. See
[`examples/static_feature_checking`](examples/static_feature_checking).

## Executable examples

Every feature is demonstrated by runnable pytest or pytest-bdd code under
`examples/`:

- [`basic_users`](examples/basic_users): row-oriented schema parsing.
- [`content_table`](examples/content_table): column-oriented schema parsing.
- [`custom_cell_dsl`](examples/custom_cell_dsl): exact tokens and regex cell
  patterns.
- [`record_validation`](examples/record_validation): relationships between
  fields on one parsed record.
- [`context_validation`](examples/context_validation): validation using
  project policy supplied through parse context.
- [`table_data`](examples/table_data): source-aware `TableData` and
  `TableCell` behavior.
- [`numeric_table_transform`](examples/numeric_table_transform): project-owned
  `1..3` and `3:Article` syntax.
- [`alphabetic_table_transform`](examples/alphabetic_table_transform): an
  unrelated `A-C` and `Article x3` convention.
- [`custom_group_rules`](examples/custom_group_rules): project-defined range
  and repeat objects using `R1~R3` and `[3]Article`.
- [`field_parsers`](examples/field_parsers): reusable conversion and parser
  composition.
- [`record_sources`](examples/record_sources): record and field source
  metadata.
- [`table_validation`](examples/table_validation): validation across records.
- [`output_models`](examples/output_models): dataclass domain objects.
- [`pydantic_output`](examples/pydantic_output): optional Pydantic models.
- [`annotated_schema`](examples/annotated_schema): parser inference from types.
- [`field_components`](examples/field_components): reusable field groups.
- [`functional_api`](examples/functional_api): schema method, functional, and
  pytest fixture parsing styles.
- [`record_references`](examples/record_references): local links between
  records.
- [`content_variants`](examples/content_variants): discriminated,
  column-oriented content shapes with variant-specific validation.
- [`payment_variants`](examples/payment_variants): row-oriented variants with
  different dataclass output models.
- [`complete_content_variants`](examples/complete_content_variants): the full
  declarative variant API combined with table expansion, cell syntax,
  validation, references, source metadata, and output models.
- [`defaults_aliases_policies`](examples/defaults_aliases_policies): generated
  defaults, historical labels, and preserved additional fields.
- [`collected_errors`](examples/collected_errors): several structured,
  source-aware diagnostics from one parse.
- [`composable_dsl`](examples/composable_dsl): scoped tokens, predicate rules,
  and first-match DSL composition.
- [`transformer_pipeline`](examples/transformer_pipeline): ordered,
  source-preserving table transformations.
- [`schema_introspection`](examples/schema_introspection): machine-readable
  table contracts.
- [`output_factory`](examples/output_factory): context-aware result building.
- [`static_feature_checking`](examples/static_feature_checking): checking a
  Gherkin table without scenario execution.
- [`cli_tools`](examples/cli_tools): JSON diagnostics and schema description
  from the command line.

Run every example together with the unit tests:

```powershell
uv run pytest -p no:cacheprovider
```
