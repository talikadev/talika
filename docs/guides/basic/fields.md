---
icon: lucide/sliders-horizontal
---

# Fields

A field is the smallest promise in a Talika table contract.

It says: when the authored table uses this label, store the value on this
Python attribute, require it or allow it to be absent, optionally convert the
cell text, and decide how strict the table should be when the value is blank.

```gherkin title="A user table with field labels"
--8<-- "docs_src/guides/basic/fields.py:feature-users"
```

The table author sees `username`, `email`, `role`, and `active`. Your test code
should not have to keep re-reading those header strings by hand. A field
declaration is the bridge between the table vocabulary and the Python value you
want to use in setup code.

!!! tip "Think label first, then value"
    Start by asking what the label means to a feature-file author. After that,
    decide whether the value is required, whether it needs a parser, and what
    should happen when the field is absent or empty.

## Define a Field Contract

Field declarations live on a `RowTable` or `ColumnTable` schema class. The
class attribute name is the Python name. The string passed to `field(...)` is
the table label.

```python title="users_table.py"
--8<-- "docs_src/guides/basic/fields.py:contract-basic"
```

This contract makes four separate decisions:

- `username` maps the table label `username` to `user.username`.
- `email` maps the table label `email` to `user.email`.
- `role` is optional and receives `"viewer"` when the whole `role` field is absent.
- `active` is optional, but when present it is parsed with `boolean()`.

The table label and the Python attribute can be the same, but they do not have
to be. In real projects, feature tables often use labels such as `Full name`,
`Account status`, or `Can publish?`, while Python code uses `name`, `status`,
and `can_publish`.

!!! note "Fields are declared once"
    The point of a field declaration is to stop every test step from
    rediscovering the same table rules. Once the schema says what `active`
    means, every test that parses through that schema gets the same conversion
    and validation.

## Parse Field Values

When Talika parses a table, each field becomes an attribute on the parsed
record.

```python title="Parse users through the field contract"
--8<-- "docs_src/guides/basic/fields.py:parse-basic"
```

```bash { .talika-terminal title="Parsed field values" .speed-3}
--8<-- "docs_src/guides/basic/fields.py:parsed-output"
```

Notice the second record: `role` is an empty string, not `"viewer"`. That is
intentional. The `role` label exists in the table, and the author left that
specific cell blank. Defaults are for absent fields, not for visible blank
cells.

!!! warning "Do not use defaults as blank-cell cleanup"
    A default answers the question "what should happen if this field is not in
    the table?" It does not silently replace a cell the author wrote as empty.
    If blank cells need special behavior, choose an explicit empty-cell policy.

## Required Fields

Use `required=True` when the table is not meaningful without the value.

For row tables, a required field must appear in the header row, and each record
must provide a non-empty cell. For column tables, the same idea applies to the
field row and each item column.

If the table omits the required label, Talika reports a missing field:

```python title="Missing required label"
--8<-- "docs_src/guides/basic/fields.py:missing-required"
```

```text title="Missing required label error"
--8<-- "docs_src/guides/basic/fields.py:missing-required-output"
```

If the label is present but the value is blank, Talika reports the exact cell:

```python title="Empty required cell"
--8<-- "docs_src/guides/basic/fields.py:empty-required"
```

```text title="Empty required cell error"
--8<-- "docs_src/guides/basic/fields.py:empty-required-output"
```

These two errors are intentionally different. A missing label means the table
shape is wrong. An empty required cell means one record has incomplete data.

!!! tip "Make the important fields required"
    Required fields are not only about type safety. They also document which
    pieces of the scenario are essential. If a test would become vague or
    misleading without the value, make the field required.

## Optional Fields and Defaults

By default, a field is optional. If an optional field is absent from the table,
Talika returns `None`.

You can provide a static `default` when the fallback is always the same, or a
`default_factory` when the fallback depends on context.

```python title="Defaults for absent fields"
--8<-- "docs_src/guides/basic/fields.py:defaults-contract"
```

Here the table only provides `username`. The missing `role` and `team` fields
are filled by the schema:

```python title="Parse with defaults"
--8<-- "docs_src/guides/basic/fields.py:defaults-parse"
```

The factory receives a context object. That makes it useful for project data
passed to `parse(..., context={...})`, or for item-aware defaults in tables
that declare an `id_field(...)`.

Now compare that with an explicit blank:

```python title="An empty cell is still a present field"
--8<-- "docs_src/guides/basic/fields.py:defaults-empty"
```

The `role` field is present, so Talika does not apply the default. It preserves
the blank as a real authored value.

!!! note "Required fields cannot declare defaults"
    A field cannot be both required and defaulted. If Talika supplied a value
    for a missing required field, the table would appear valid even though the
    scenario author did not provide the required data.

## Parsers on Fields

Every cell starts as text. A parser gives a field permission to turn that text
into something else.

```python title="Field-level parsers"
--8<-- "docs_src/guides/basic/fields.py:parser-contract"
```

```python title="Parsing converted values"
--8<-- "docs_src/guides/basic/fields.py:parser-parse"
```

The parser belongs to the field, not to the individual test step. That keeps
the meaning of `age` and `active` stable wherever the schema is used.

If a parser fails, the diagnostic points back to the authored cell:

```python title="A value the parser cannot convert"
--8<-- "docs_src/guides/basic/fields.py:parser-error"
```

```text title="Parser failure"
--8<-- "docs_src/guides/basic/fields.py:parser-error-output"
```

!!! warning "Python-looking values are still text"
    `34`, `yes`, `false`, and `draft` are table text until a field parser gives
    them meaning. Avoid relying on what a value looks like to a human reader.

## Aliases

Aliases let old and new table vocabulary coexist while your feature files
evolve.

```python title="A field with accepted old labels"
--8<-- "docs_src/guides/basic/fields.py:aliases-contract"
```

The canonical label is `name`, but the schema also accepts `full name` and
`display name`:

```python title="Parsing through an alias"
--8<-- "docs_src/guides/basic/fields.py:aliases-parse"
```

Aliases are useful when a team renames a label across many feature files. You
can accept the older wording while gradually moving tables toward the preferred
label.

Talika still rejects a table that uses both the canonical label and an alias
for the same field:

```python title="Conflicting labels"
--8<-- "docs_src/guides/basic/fields.py:duplicate-alias"
```

```text title="Duplicate label diagnostic"
--8<-- "docs_src/guides/basic/fields.py:duplicate-alias-output"
```

That rejection prevents a confusing question: if both cells are present, which
one should become `user.name`?

## Unknown Field Labels

Talika also checks the other side of the contract: the table should not invent
labels the schema does not know. If a feature file adds a new column before the
schema is updated, Talika treats that as a table-shape error instead of quietly
dropping the value.

```python title="An undeclared label"
--8<-- "docs_src/guides/basic/fields.py:unknown-field"
```

```text title="Unknown field diagnostic"
--8<-- "docs_src/guides/basic/fields.py:unknown-field-output"
```

This strictness matters because unknown labels are often spelling mistakes,
half-finished schema changes, or values that a test author expected the setup
code to use. Silent ignore would make the scenario look complete while the
Python test is missing part of the authored intent.

The current schema policy for unknown labels is deliberately narrow:

```python title="Unsupported unknown-field policy"
--8<-- "docs_src/guides/basic/fields.py:unknown-policy-error"
```

```text title="Unsupported policy error"
--8<-- "docs_src/guides/basic/fields.py:unknown-policy-output"
```

`unknown_fields` only accepts `"forbid"` in this version. If a label should be
accepted, declare it as a field or as an alias for an existing field.

!!! warning "Unknown is different from inapplicable"
    An unknown label is not part of the schema vocabulary at all. A variant
    field can be known to the table family but inapplicable to one selected
    record. Those are different situations, and Talika handles them with
    different policies.

## Label Matching and Case Sensitivity

By default, Talika's label matching is strict, exact, and case-sensitive. The string passed to `field(...)` or defined as an alias must match the table cell exactly, including casing and spacing:

- `field("username")` will **not** match a table header cell containing `Username` (capital U) or `username ` (with trailing whitespace).
- Talika uses the cell text it receives. If a Gherkin parser or test framework trims visual table padding before passing the datatable to Talika, that happens outside Talika. Once the value reaches Talika, label matching is exact.

```python title="Case sensitive label matching"
--8<-- "docs_src/guides/basic/fields.py:case-sensitivity-error"
```

!!! tip "Keep one preferred label"
    Treat aliases as compatibility vocabulary, not as equal alternatives
    forever. The first argument to `field(...)` should be the label you want new
    tables to use.

## Empty-Cell Policies

Optional fields can choose how to handle an explicit blank cell.

```python title="Different policies for blank optional cells"
--8<-- "docs_src/guides/basic/fields.py:empty-policies-contract"
```

The available policies are:

- `empty="raw"` preserves the blank as `""`.
- `empty="parse"` sends the blank string to the parser.
- `empty="none"` returns `None`.
- `empty="error"` rejects the blank cell.

```python title="Parsing blank cells with policies"
--8<-- "docs_src/guides/basic/fields.py:empty-policies-parse"
```

```bash { .talika-terminal title="Blank-cell results" .speed-3}
--8<-- "docs_src/guides/basic/fields.py:empty-policies-output"
```

Use `empty="error"` when a field may be omitted, but must not be written as a
blank value when the label is present.

```python title="A strict optional field rejects blanks"
--8<-- "docs_src/guides/basic/fields.py:empty-strict"
```

```text title="Strict blank-cell diagnostic"
--8<-- "docs_src/guides/basic/fields.py:empty-strict-output"
```

!!! example "Optional does not mean careless"
    `optional` means the whole field can be absent. It does not automatically
    mean a blank cell is acceptable. If blank cells have a project meaning,
    write that meaning into the field declaration.

## ID Fields

`id_field(...)` is a specialized required field for item identity.

```python title="A row table with an ID field"
--8<-- "docs_src/guides/basic/fields.py:id-contract"
```

A row table may declare an ID field when diagnostics, parsers, defaults, or
later validation should know which authored item is being parsed. A column
table must declare one because each item column needs a stable ID.

When an ID is present, diagnostics can include `item_id`:

```python title="An error on an identified row"
--8<-- "docs_src/guides/basic/fields.py:id-error"
```

```text title="Diagnostic with item_id"
--8<-- "docs_src/guides/basic/fields.py:id-error-output"
```

That extra identity is helpful when a table is long, sorted by a helper, or
displayed in CI output where row numbers alone are not enough.

## Literal Labels

Talika does not infer meaning from punctuation in labels.

```python title="A literal label"
--8<-- "docs_src/guides/basic/fields.py:literal-label"
```

In this example, `Headline*` is the exact table label. The `*` does not make the
field required. The field is required because the declaration says
`required=True`.

This small rule keeps table vocabulary predictable. Labels belong to your
project language; field options define parser behavior.

!!! note "Invalid declarations fail before parsing"
    If a schema declaration itself is invalid, Talika raises
    `SchemaDefinitionError` while the schema class is being created or imported.
    That is different from `TableError`, which belongs to a specific authored
    table value.
