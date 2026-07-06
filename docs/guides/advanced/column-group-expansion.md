---
icon: lucide/repeat
---

# Column Group Expansion

Column group expansion is for column-shaped tables where one authored column
stands for several logical records.

That sounds abstract, but the table shape is common in feature files. Authors
often want to say "IDs 1 through 3 are articles with the same headline" without
copying the same values three times.

```gherkin title="A compact grouped content table"
--8<-- "docs_src/guides/advanced/column-group-expansion.py:feature"
```

Talika can expand that compact authoring shape before the `ColumnTable` schema
parses it. After expansion, the schema sees a normal column table with one
logical item column per ID.

!!! tip "Think in source groups"
    The first row contains the group key. Each following row contains one value
    for that source group. The range rule expands the key cell, and the repeat
    rule expands the aligned value cells to the same length.

## Configure the Expander

Attach `ColumnGroupExpander` as a table transformer on a `ColumnTable`.

```python title="A grouped content schema"
--8<-- "docs_src/guides/advanced/column-group-expansion.py:schema"
```

`key_row="IDs"` tells the expander which row is allowed to define groups.
`NumericRange("..")` turns `1..3` into `1`, `2`, and `3`. `PrefixRepeat(":")`
turns `3:Article` into three `Article` cells.

```bash { .talika-terminal title="Records produced from grouped columns" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:records-output"
```

The expanded table is the logical shape the schema parses:

```bash { .talika-terminal title="Expanded logical table" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:expanded-table-output"
```

!!! note "Expansion happens before field parsing"
    Field labels, required fields, parsers, defaults, validators, and output
    conversion run after the grouped table has become a normal logical table.

## Source Cells Stay Useful

Expanded cells still point back to the compact cell that created them.

```bash { .talika-terminal title="Source metadata after expansion" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:source-output"
```

The third content record gets `Article` from the original `3:Article` cell.
Both `Shared` headlines for IDs `1`, `2`, and `3` point back to the single
`Shared` cell.

This is why group expansion can be used in real test suites without making
diagnostics vague. The test gets simple records, while the failure still points
to the authored compact table.

## Use Built-In Range and Repeat Rules

Range rules work on the key row:

- `NumericRange("..")` supports values such as `1..3`
- `AlphabeticRange("-")` supports values such as `A-C`

Repeat rules work on the value rows:

- `PrefixRepeat(":")` supports values such as `3:Article`
- `SuffixRepeat(" x")` supports values such as `Article x3`

Values that do not use the configured syntax are treated as literals. For
example, `4` is one ID, and `Poll` is copied once because it belongs to a
single-key group.

```python title="Alphabetic keys with suffix repeats"
--8<-- "docs_src/guides/advanced/column-group-expansion.py:alphabetic-suffix"
```

```bash { .talika-terminal title="Alphabetic expansion result" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:alphabetic-suffix-output"
```

!!! warning "Recognized range syntax must be valid"
    For range rules, a value that contains the configured separator is treated
    as range syntax. `3..1` is not a literal; it is a descending numeric range,
    so it fails. Repeat rules are a little more forgiving: a value such as
    `News: Europe` stays literal with `PrefixRepeat(":")` because the prefix is
    not a repeat count.

## Write Custom Rules

Use custom rules when your project has its own group language. Range rules
implement `expand(cell, context)` and return key cells. Repeat rules implement
`expand(cell, expected_count, context)` and return exactly that many value
cells.

Those two shapes are the public `RangeRule` and `RepeatRule` protocols. They
are structural protocols, so custom rule classes do not need to inherit from a
Talika base class. The important part is the method signature and returning
`TableCell` objects.

```python title="Custom group syntax with parse context"
--8<-- "docs_src/guides/advanced/column-group-expansion.py:custom-rules"
```

```bash { .talika-terminal title="Custom rule output" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:custom-rules-output"
```

Custom rules should return `TableCell` objects, usually by calling
`cell.with_value(...)`. Returning plain strings would lose source coordinates,
so Talika rejects it.

!!! tip "Keep rule objects small"
    Let the expander own the table mechanics. Let each rule own one syntax:
    how a key group is named, or how a value is spread across that group.

## Understand Expansion Errors

When a repeat count does not match the key range, the error points to the value
cell with the incorrect count:

```python title="A repeat count that does not match its key group"
--8<-- "docs_src/guides/advanced/column-group-expansion.py:repeat-error"
```

```bash { .talika-terminal title="Repeat count diagnostic" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:repeat-error-output"
```

If the key row is wrong, the error points to the first cell:

```bash { .talika-terminal title="Wrong key row diagnostic" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:key-error-output"
```

If a range is recognized but invalid, the error points to the key cell:

```bash { .talika-terminal title="Invalid range diagnostic" .speed-2}
--8<-- "docs_src/guides/advanced/column-group-expansion.py:range-error-output"
```

!!! example "A practical rule of thumb"
    Use group expansion when compact authoring would remove noisy repetition
    from a column table. If the compact syntax makes the feature harder to
    review, prefer writing the ordinary expanded table directly.
