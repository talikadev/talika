<p align="center">
  <a href="https://talikadev.github.io/talika/">
    <img src="https://raw.githubusercontent.com/talikadev/talika/master/docs/assets/images/logotalpha_400.png" alt="Talika" width="400">
  </a>
</p>

<p align="center">
  <em>Talika — Hindi for tables.</em><br>
  Declarative schemas for typed, validated Gherkin data tables.
</p>

<p align="center">
  <a href="https://github.com/talikadev/talika/actions/workflows/ci.yml"><img src="https://github.com/talikadev/talika/actions/workflows/ci.yml/badge.svg?branch=master" alt="CI"></a>
  <a href="https://pypi.org/project/talika/"><img src="https://img.shields.io/pypi/v/talika?color=%2334D058&label=PyPI" alt="PyPI version"></a>
  <a href="https://pypi.org/project/talika/"><img src="https://img.shields.io/pypi/pyversions/talika.svg?color=%2334D058" alt="Supported Python versions"></a>
  <a href="https://github.com/talikadev/talika/blob/master/LICENSE"><img src="https://img.shields.io/pypi/l/talika?color=%2334D058" alt="License"></a>
  <a href="https://talikadev.github.io/talika/"><img src="https://img.shields.io/badge/docs-online-ef1266" alt="Documentation"></a>
</p>

---

Gherkin data tables are wonderfully easy to read. The raw `list[list[str]]` that
arrives in Python is less wonderful to maintain.

As a test suite grows, step definitions accumulate the same invisible work:
matching labels, converting strings, applying defaults, rejecting typos, and
explaining which cell was wrong. Talika moves that work into a small, reusable
table contract.

Define the shape once. Talika parses the table, converts its cells into real
Python values, validates the result, and keeps errors connected to the original
`.feature` file.

<p align="center">
  <strong><a href="https://talikadev.github.io/talika/start/quickstart/">Quickstart</a></strong>
  ·
  <strong><a href="https://talikadev.github.io/talika/start/why/">Why Talika?</a></strong>
  ·
  <strong><a href="https://talikadev.github.io/talika/reference/">API reference</a></strong>
</p>

## What you get

- **Declarative table contracts** — describe labels, required fields, aliases,
  defaults, and parsing rules in one Python class.
- **Typed records** — turn cells into `int`, `bool`, `Decimal`, enums, lists,
  and your own domain values.
- **Both natural table shapes** — use row-oriented tables for lists and
  column-oriented tables for detailed items.
- **Errors where the data lives** — report stable error codes with the field,
  row, column, item ID, and original value.
- **Your team's vocabulary** — build readable cell conventions such as
  `random`, `today`, or `20 words` with tokens and full-match patterns.
- **Room for real test suites** — model variants, references, table transforms,
  cross-record validation, and dataclass or Pydantic output.
- **Checks before test execution** — validate Gherkin tables in CI with the
  optional `talika check` CLI.
- **A zero-dependency core** — install integrations only when you need them.

## Installation

Talika supports Python 3.10 and newer.

```bash
pip install talika
```

Or with `uv`:

```bash
uv add talika
```

Optional extras keep the core package small:

```bash
pip install "talika[cli]"       # Static checks for .feature files
pip install "talika[pydantic]"  # Pydantic v2 output models
```

See the [installation guide](https://talikadev.github.io/talika/start/install/)
for environment setup and all available extras.

## A table contract in a few lines

Start with a table that stays readable for everyone working on the scenario:

```gherkin
Given the users exist
  | name  | age | roles              | active |
  | Akash | 27  | Developer, Manager | true   |
  | Badal | 25  | Tester             | false  |
```

Describe what those cells mean:

```python
from talika import RowTable, boolean, field, split


class UserTable(RowTable):
    name = field(required=True)
    age: int = field("age", required=True)
    roles = field("roles", parser=split(","))
    active = field("active", parser=boolean(), default=True)
```

Then parse at the boundary of your step:

```python
from pytest_bdd import given


@given("the users exist", target_fixture="users")
def users(datatable):
    return UserTable.parse(datatable)
```

Your test now receives useful Python values instead of table-shaped strings:

```python
assert users[0].name == "Akash"
assert users[0].age == 27
assert users[0].roles == ["Developer", "Manager"]
assert users[0].active is True
```

`parse()` always returns `UserTable` records. When a boundary needs a
dataclass, Pydantic model, or another callable output type, use
`UserTable.parse_as(datatable, User)` instead. Omitting the target uses a
configured `output_model` or `build_output()` hook.

Bad input fails at the table boundary with source-aware diagnostics:

```text
Field parser failed: invalid literal for int() with base 10: 'old'
(code=parser_failed, schema=UserTable, field='age', row=2, column=2, value='old').
```

The [quickstart](https://talikadev.github.io/talika/start/quickstart/) walks
through defaults, collected errors, source metadata, and the `pytest-bdd`
fixture.

## Tables can have different shapes

`RowTable` treats the first row as labels and each following row as one record:

```gherkin
| name  | role  |
| Akash | admin |
| Badal | user  |
```

`ColumnTable` treats the first column as labels and each following column as
one record—useful when each item has many attributes:

```gherkin
| IDs       | 1       | 2       |
| Type      | Article | Poll    |
| Headline  | Hello   | Vote?   |
| Published | true    | false   |
```

Both shapes use the same field declarations, parsers, validation hooks,
`parse_as()` output conversion, and source-aware errors. Read
[choosing a table shape](https://talikadev.github.io/talika/learn/choosing-table-shape/)
for the trade-offs.

## Make tables speak your domain

Talika does not impose a universal table DSL. It gives your project safe hooks
to own its vocabulary:

```python
from talika import CellDSL


cells = CellDSL()


@cells.token("random", fields=("headline",))
def random_headline(context):
    return context.user_data["faker"].headline()


@cells.pattern(r"(?P<count>\d+) words", fields=("body",))
def generated_words(match, context):
    return context.user_data["faker"].words(int(match["count"]))
```

Feature authors can write compact intent such as `random` or `20 words`, while
the project decides exactly what those phrases mean. Explore
[tokens](https://talikadev.github.io/talika/guides/advanced/cell-dsl-tokens/),
[patterns](https://talikadev.github.io/talika/guides/advanced/cell-dsl-patterns/),
and [composition](https://talikadev.github.io/talika/guides/advanced/cell-dsl-composition/).

## Check feature files without running scenarios

Install the CLI extra and validate tables during local development or CI:

```bash
pip install "talika[cli]"
talika check features/users.feature --schema tests.tables:UserTable --step "the users exist"
```

The checker uses the official Gherkin parser and can emit JSON diagnostics for
editor and CI integrations. See the
[static checking guide](https://talikadev.github.io/talika/guides/advanced/static-checking/)
for discovery, context factories, and exit codes.

## Where Talika fits

Talika is deliberately focused. It is not a test runner, fixture factory,
business workflow engine, or general model-validation library.

`pytest-bdd` still runs scenarios. Pydantic can still validate final models.
Factories can still build database objects. Talika owns the boundary between a
human-authored data table and the Python objects your test code wants to use.

## Learn more

- [Why Talika?](https://talikadev.github.io/talika/start/why/) — the problem it
  solves and how it compares with adjacent tools.
- [Quickstart](https://talikadev.github.io/talika/start/quickstart/) — build and
  use your first schema.
- [Guides](https://talikadev.github.io/talika/guides/basic/row-tables/) — fields,
  parsers, validation, variants, references, transforms, and more.
- [API reference](https://talikadev.github.io/talika/reference/) — the complete
  public interface.
- [Changelog](https://github.com/talikadev/talika/blob/master/CHANGELOG.md) —
  releases and notable changes.

## Contributing

Contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for the local
development workflow and project checks.

## License

Talika is released under the [MIT License](LICENSE).
