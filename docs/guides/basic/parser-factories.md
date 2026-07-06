---
icon: lucide/square-function
---

# Parser Factories

Parser factories create the callables you pass to `field(parser=...)`.

A table cell starts as text. A parser decides what that text means for one
field: maybe it becomes an integer, a boolean, a decimal, a normalized string,
a domain value, a list, or `None`.

The factories in Talika are deliberately small. Each one does one clear job,
and the composition helpers let you build larger parsing rules without hiding
the table vocabulary inside a long custom function.

```gherkin title="A table with scalar values"
--8<-- "docs_src/guides/basic/parser-factories.py:feature-scalar"
```

!!! tip "Read parsers as table vocabulary"
    A parser is not just a Python conversion. It is part of the contract for
    what authors are allowed to write in the table. If a cell says `ff`, the
    parser is the rule that explains why that means `255`.

A parser factory returns a parser callable. Talika calls that parser with the
cell value and source-aware context while parsing the field. Most built-in
parsers do not need the context, but they accept it so they can be composed
with custom parsers that do.

## Start with Scalar Parsers

Use scalar parsers when one cell should become one ordinary Python value.

```python title="Scalar parser fields"
--8<-- "docs_src/guides/basic/parser-factories.py:scalar-contract"
```

This schema uses:

- `string(strip=True, lower=True)` to normalize authored text.
- `integer()` to parse base-10 whole numbers.
- `integer(base=16)` to parse hexadecimal text.
- `floating()` to parse Python floats.
- `decimal()` to parse exact decimal values.

```python title="Parsing scalar values"
--8<-- "docs_src/guides/basic/parser-factories.py:scalar-parse"
```

```bash { .talika-terminal title="Scalar parser result" .speed-3}
--8<-- "docs_src/guides/basic/parser-factories.py:scalar-output"
```

Use `decimal()` for values such as money, balances, and exact quantities where
binary floating-point behavior would make assertions harder to read.

!!! note "String parsing is still parsing"
    `string(...)` is useful even though the input is already text. It gives
    your schema a declared normalization rule, so every parsed record sees the
    same stripped or cased value.

## Parse Boolean Vocabulary

Boolean values are common in feature tables, but the words are rarely universal.
One team may write `yes` and `no`; another may write `enabled` and `disabled`;
another may require exact uppercase tokens from an external system.

```gherkin title="Different boolean vocabularies"
--8<-- "docs_src/guides/basic/parser-factories.py:feature-boolean"
```

```python title="Boolean parser fields"
--8<-- "docs_src/guides/basic/parser-factories.py:boolean-contract"
```

The default `boolean()` parser accepts common values such as `true`, `false`,
`yes`, `no`, `1`, `0`, `on`, and `off`. You can replace that vocabulary with
project-specific true and false tokens. Set `case_sensitive=True` when the
table must match exact casing.

```python title="Parsing boolean values"
--8<-- "docs_src/guides/basic/parser-factories.py:boolean-parse"
```

```bash { .talika-terminal title="Boolean parser result" .speed-3}
--8<-- "docs_src/guides/basic/parser-factories.py:boolean-output"
```

Boolean parsing is strict. Unknown values fail instead of falling back to
Python truthiness:

```python title="Unknown boolean token"
--8<-- "docs_src/guides/basic/parser-factories.py:boolean-error"
```

```text title="Boolean parser failure"
--8<-- "docs_src/guides/basic/parser-factories.py:boolean-error-output"
```

!!! warning "Do not rely on Python truthiness"
    In plain Python, many non-empty strings are truthy. In a feature table,
    `"false"` should not accidentally become true. Talika's boolean parser only
    accepts the configured tokens.

## Choose Between Choice and Mapping

Use `choice(...)` when the table should contain one of a known set of strings.
Use `map_value(...)` when the table text should become a different Python
value.

```python title="Vocabulary parser fields"
--8<-- "docs_src/guides/basic/parser-factories.py:vocabulary-contract"
```

`choice("Draft", "Published", case_sensitive=False)` accepts case-insensitive
input but returns the canonical configured spelling. `map_value(...)` returns
whatever Python value is stored in the mapping.

```python title="Parsing vocabulary values"
--8<-- "docs_src/guides/basic/parser-factories.py:vocabulary-parse"
```

```bash { .talika-terminal title="Vocabulary parser result" .speed-3}
--8<-- "docs_src/guides/basic/parser-factories.py:vocabulary-output"
```

These two parsers solve different problems. `choice()` is about validation and
canonical spelling. `map_value()` is about translating table vocabulary into a
domain value, such as `"high"` becoming `5`.

```python title="Unknown choice value"
--8<-- "docs_src/guides/basic/parser-factories.py:choice-error"
```

```text title="Choice parser failure"
--8<-- "docs_src/guides/basic/parser-factories.py:choice-error-output"
```

```python title="Unknown mapped value"
--8<-- "docs_src/guides/basic/parser-factories.py:map-error"
```

```text title="Mapping parser failure"
--8<-- "docs_src/guides/basic/parser-factories.py:map-error-output"
```

!!! tip "Use mapping when the test needs another type"
    If the test should receive `"Published"`, use `choice()`. If the test
    should receive an enum member, integer weight, sentinel object, or domain
    value, use `map_value()` or a custom parser.

## Build Lists with Split, Compose, and Each

Tables often store compact lists in one cell. Talika does not guess a list
syntax from a type annotation, so the parser should describe how the cell is
written.

```gherkin title="A table with compact list cells"
--8<-- "docs_src/guides/basic/parser-factories.py:feature-list"
```

```python title="List parser fields"
--8<-- "docs_src/guides/basic/parser-factories.py:list-contract"
```

This schema uses three parser helpers together:

- `split(",")` turns one text cell into a list of strings.
- `compose(a, b)` runs parser `a`, then sends its result to parser `b`.
- `each(integer())` applies `integer()` to every item in a non-string iterable.

```python title="Parsing list values"
--8<-- "docs_src/guides/basic/parser-factories.py:list-parse"
```

```bash { .talika-terminal title="List parser result" .speed-3}
--8<-- "docs_src/guides/basic/parser-factories.py:list-output"
```

Parser order matters. `each(integer())` expects an iterable that is already a
list-like value. It should usually come after `split(...)`, not before it.

```python title="A list item that cannot be parsed"
--8<-- "docs_src/guides/basic/parser-factories.py:list-error"
```

```text title="List parser failure"
--8<-- "docs_src/guides/basic/parser-factories.py:list-error-output"
```

In this diagnostic, the bad item is `two`, but the source value is still the
original cell `1;two;3`. That is useful because the feature author fixes the
whole authored cell, not an intermediate parser value.

```python title="Using each before split"
--8<-- "docs_src/guides/basic/parser-factories.py:wrong-order"
```

```text title="Parser order failure"
--8<-- "docs_src/guides/basic/parser-factories.py:wrong-order-output"
```

!!! warning "Composition is left to right"
    Read `compose(split(";"), each(integer()))` as: first split the cell on
    semicolons, then parse each split item as an integer. If you reverse that
    order, `each()` receives the original string and rejects it.

## Composing Custom Pipelines

Because built-in parser factories are small, you can compose them using
`compose(...)` to create a parser pipeline for a project-specific cell shape.

This is useful when the authored cell has several steps of meaning. A category
cell might first need to be split on semicolons, then each item needs whitespace
handling, then each item must belong to a vocabulary. None of those steps is
large enough to deserve a custom parser by itself, but together they describe a
real table rule.

```python title="Composition pipeline"
--8<-- "docs_src/guides/basic/parser-factories.py:pipeline-contract"
```

```python title="Parsing through a composed pipeline"
--8<-- "docs_src/guides/basic/parser-factories.py:pipeline-parse"
```

This pipeline approach keeps the intent visible in the field declaration. The
reader can see that the cell is split first, then every item is checked. A
custom parser can still be the right choice for domain-heavy logic, but parser
factories are easier to reuse when the behavior is mostly mechanical.

!!! tip "Use composition for boring rules"
    If the logic is split, trim, convert, choose, or validate each item, compose
    factories. If the logic needs domain decisions, service data, or several
    named branches, write a custom parser.

## Handle Empty and Null-Like Values

Use `optional(parser)` when an empty cell or a null-like token should become
`None`, while non-null values should still be parsed.

```python title="Optional parser field"
--8<-- "docs_src/guides/basic/parser-factories.py:optional-contract"
```

```python title="Parsing optional values"
--8<-- "docs_src/guides/basic/parser-factories.py:optional-parse"
```

```bash { .talika-terminal title="Optional parser result" .speed-3}
--8<-- "docs_src/guides/basic/parser-factories.py:optional-output"
```

By default, `optional(...)` treats blank cells, `none`, and `null` as `None`.
When you pass `none_values=...`, you are replacing the configured null-like
tokens. Include every token your table should accept.

```python title="Replacing null-like tokens"
--8<-- "docs_src/guides/basic/parser-factories.py:optional-replace-error"
```

```text title="Optional parser failure"
--8<-- "docs_src/guides/basic/parser-factories.py:optional-replace-error-output"
```

Here `none_values=("n/a",)` means `none` is no longer a null-like token. The
parser tries to parse `none` as an integer and fails.

!!! note "Optional parser and optional field are different"
    An optional field may be absent from the table. `optional(parser)` handles
    values that are present but intentionally blank or null-like. Both ideas
    are useful, but they solve different cases.

## Understand Parser Failures

Parser failures are wrapped in `TableError` during table parsing. The wrapper
keeps the original source location, schema name, field label, and authored
value.

That wrapping is why failures from `boolean()`, `choice()`, `integer()`, or a
composed parser still point to the table cell instead of only showing a Python
stack trace. The underlying exception remains useful, but the table diagnostic
tells the feature author where to look.

Configuration errors are different. If a parser factory is called with an
impossible configuration, it raises immediately while the schema is being
defined. Each line below is a separate invalid parser declaration:

```python title="Invalid parser configurations"
--8<-- "docs_src/guides/basic/parser-factories.py:configuration-errors"
```

```text title="Configuration errors"
--8<-- "docs_src/guides/basic/parser-factories.py:configuration-errors-output"
```

These errors are not table data errors. They mean the parser declaration itself
is contradictory or incomplete.

!!! tip "Keep parser declarations close to the field"
    When a parser is short, place it directly in `field(parser=...)`. When the
    parser starts to express project vocabulary, assign it to a named variable
    or move it into a small helper so the table contract remains readable.
