---
icon: lucide/binary
tags:
  - Type annotations
  - Type conversion
  - Schemas
  - Parsing
---

# Type Annotations

Type annotations let a Talika schema say two things at once:

- this is the Python shape I expect after parsing
- this common field parser can be inferred for me

They are useful when the table value has an obvious conversion, such as
`int`, `bool`, `Decimal`, an enum, or a small string `Literal`. They are not a
replacement for field parsers. When the cell syntax is project-specific, the
parser still needs to be explicit.

```gherkin title="A table with typed values"
--8<-- "docs_src/guides/basic/type-annotations.py:feature-basic"
```

Every value in that table is authored as text. The annotations on the schema
decide which fields should be converted into Python values.

!!! tip "Use annotations for obvious conversions"
    Reach for annotation inference when the Python type has one clear table
    meaning. If a human could reasonably ask "how is this cell written?", use
    an explicit parser instead.

## Define an Annotated Schema

Annotate the Python attribute and declare the field in the same line.

```python title="users_table.py"
--8<-- "docs_src/guides/basic/type-annotations.py:contract-basic"
```

Talika reads these annotations when the schema class is created. If the
annotation is supported and the field does not already have a parser, Talika
attaches the matching parser to the field.

Resolution is isolated per field and follows inherited annotations back to
the nearest class that declared them. If one postponed annotation cannot be
resolved, only that field stays as raw text; supported annotations on other
fields continue to infer their parsers. An explicit parser takes precedence
without requiring its annotation to resolve.

The important phrase is "matching parser." Annotation inference is not runtime
type checking. It is a small convenience layer over the same parser mechanism
used by `field(parser=...)`.

```python title="Parse annotated values"
--8<-- "docs_src/guides/basic/type-annotations.py:parse-basic"
```

```bash { .talika-terminal title="Parsed annotated record" .speed-3}
--8<-- "docs_src/guides/basic/type-annotations.py:parsed-output"
```

After parsing, the record contains normal Python values. `age` is an `int`,
`balance` is a `Decimal`, and `status` is an enum member.

!!! note "Annotations belong on schema attributes"
    Talika only infers from attributes that are declared as fields. Annotating
    a random class variable does not make it part of the table contract.

## Supported Scalar Annotations

Talika intentionally supports a small set of annotations where conversion has
clear local meaning:

- `int`
- `float`
- `bool`
- `Decimal`
- `Enum` subclasses
- string `Literal[...]`
- simple optional unions such as `int | None` or `Optional[int]`

```python title="Scalar annotation inference"
--8<-- "docs_src/guides/basic/type-annotations.py:scalar-contract"
```

```python title="Parsing scalar values"
--8<-- "docs_src/guides/basic/type-annotations.py:scalar-parse"
```

The inferred parsers behave like the corresponding parser factories. For
example, `int` uses integer conversion, `Decimal` uses decimal conversion, and
`bool` accepts only the case-insensitive default tokens `true` and `false`.

If a value cannot be converted, the error still points to the authored cell:

```python title="A boolean value outside the accepted vocabulary"
--8<-- "docs_src/guides/basic/type-annotations.py:bool-error"
```

```text title="Inferred boolean parser failure"
--8<-- "docs_src/guides/basic/type-annotations.py:bool-error-output"
```

!!! warning "Boolean inference is strict"
    A `bool` annotation does not use Python truthiness. Values such as
    `"maybe"`, `"yes"`, or `"disabled"` fail unless you provide an explicit
    `boolean(true_values=..., false_values=...)` parser with that vocabulary.

## Enums and Literal Values

Enums are useful when a table value should become a real domain value in test
code.

```python title="Enum and Literal annotations"
--8<-- "docs_src/guides/basic/type-annotations.py:enum-contract"
```

For enum annotations, Talika accepts either the enum value or the enum member
name. That lets feature files use readable domain text while tests can still
compare against enum members.

Under the hood, Talika's inferred enum parser operates as follows:

1. Converts the table cell value into a string (`raw = str(value)`).
2. Iterates through the enum members and checks if `str(member.value)` matches `raw`, or if the member name `member.name` matches `raw`.
3. Returns the matching enum member when found.
4. If no member matches, it raises a `ValueError` containing a list of the expected enum values.

```python title="Parsing enum values"
--8<-- "docs_src/guides/basic/type-annotations.py:enum-parse"
```

`Literal[...]` is narrower. It validates that the cell is exactly one of the
declared strings and returns the string itself.

```python title="A Literal value outside the allowed set"
--8<-- "docs_src/guides/basic/type-annotations.py:literal-error"
```

```text title="Literal parser failure"
--8<-- "docs_src/guides/basic/type-annotations.py:literal-error-output"
```

!!! note "Literal matching is exact"
    `Literal["basic", "staff"]` does not strip whitespace, change case, or map
    synonyms. If authors may write `Staff`, `employee`, or `staff member`, use
    an explicit parser that describes that vocabulary.

## Optional Annotations

Use an optional annotation when a present blank or null-like token should become
`None`.

```python title="Optional annotation inference"
--8<-- "docs_src/guides/basic/type-annotations.py:optional-contract"
```

```python title="Parsing optional values"
--8<-- "docs_src/guides/basic/type-annotations.py:optional-parse"
```

```bash { .talika-terminal title="Optional annotation results" .speed-3}
--8<-- "docs_src/guides/basic/type-annotations.py:optional-output"
```

For `int | None`, a non-empty value is parsed as an integer. A blank cell,
`none`, or `null` becomes `None`. For `str | None`, non-null values remain
strings while the same blank and null-like tokens become `None`.

This is different from a plain optional field with no annotation. A plain field
can be absent and return `None`, but an explicit blank cell normally remains
`""` unless the field parser or empty-cell policy says otherwise.

!!! tip "Optional annotations are about authored blanks too"
    `age: int | None` does more than document that your Python code accepts
    `None`. It also gives Talika a parser that knows how to turn a blank cell
    into `None`.

## Lists Need Explicit Parsers

Talika does not infer list syntax from `list[str]` or `list[int]`.

```python title="List annotations without parsers"
--8<-- "docs_src/guides/basic/type-annotations.py:list-raw-contract"
```

The reason is practical: a table cell can describe a list in many ways. It
might use commas, pipes, semicolons, one value per line, JSON text, or
project-specific tokens. Talika should not guess that language from the Python
annotation alone.

```python title="Parsing list annotations without parsers"
--8<-- "docs_src/guides/basic/type-annotations.py:list-raw-parse"
```

```bash { .talika-terminal title="List annotations stay as text" .speed-3}
--8<-- "docs_src/guides/basic/type-annotations.py:list-raw-output"
```

If a cell should become a list, say how to split and parse it:

```python title="List annotations with explicit parsers"
--8<-- "docs_src/guides/basic/type-annotations.py:list-explicit-contract"
```

```python title="Parsing explicit list syntax"
--8<-- "docs_src/guides/basic/type-annotations.py:list-explicit-parse"
```

```bash { .talika-terminal title="Parsed list values" .speed-3}
--8<-- "docs_src/guides/basic/type-annotations.py:list-explicit-output"
```

Here the annotation documents the result, while the parser describes the cell
syntax. Both are useful, but they answer different questions.

!!! warning "Do not expect containers to parse themselves"
    `list[str]` tells Python readers what the field should become. It does not
    tell Talika whether `qa, docs`, `qa|docs`, or `["qa", "docs"]` is the
    intended authored syntax.

## Explicit Parsers Win

If a field declares `parser=...`, Talika uses that parser and ignores annotation
inference for that field.

```python title="Explicit parser overrides annotation inference"
--8<-- "docs_src/guides/basic/type-annotations.py:explicit-parser-contract"
```

```python title="The parser decides the result"
--8<-- "docs_src/guides/basic/type-annotations.py:explicit-parser-parse"
```

The field is annotated as `int`, but the explicit parser returns `"MANY"`.
Talika does not add another integer conversion after your parser runs.

This is useful when the annotation describes the eventual domain expectation,
but the authored table uses a vocabulary that needs custom normalization.

!!! note "Annotation inference is not enforcement after parsing"
    Talika does not check that an explicit parser returns the annotated type.
    If you write a parser that returns a string from a field annotated as
    `int`, the parser result is what the record receives.

## Unsupported Annotations Stay as Text

When Talika does not know how to infer a safe parser, it leaves the value as the
cell text.

```python title="Unsupported annotations"
--8<-- "docs_src/guides/basic/type-annotations.py:unsupported-contract"
```

```python title="Parsing unsupported annotations"
--8<-- "docs_src/guides/basic/type-annotations.py:unsupported-parse"
```

This includes custom classes and ambiguous unions such as `int | float`. Both
types could plausibly parse the same value, and choosing one would be a hidden
policy decision. Use `field(parser=...)` when the project needs that conversion.

!!! example "A useful rule of thumb"
    If an annotation names a domain concept, Talika probably cannot know how to
    construct it from one table cell. Keep the annotation if it helps readers,
    and add an explicit parser when the schema should build that value.

## Errors from Inferred Parsers

Inferred parsers fail the same way explicit parsers fail: Talika wraps the
parser exception in a table-aware diagnostic.

```python title="An integer annotation parsing bad text"
--8<-- "docs_src/guides/basic/type-annotations.py:int-error"
```

```text title="Inferred integer parser failure"
--8<-- "docs_src/guides/basic/type-annotations.py:int-error-output"
```

The diagnostic names the schema, field, row, column, and original value. That
keeps annotation inference from hiding where the authored table needs to be
fixed.

Type annotations are best when they make a schema quieter without making table
syntax mysterious. Let them remove repeated parser declarations for common
types, and stay explicit whenever the table language belongs to your project.
