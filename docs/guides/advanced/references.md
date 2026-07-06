---
icon: lucide/link
---

# References

Use `reference()` when one record in a table points to another record from the
same parsed table.

This is common in BDD setup data. CMS pages have parents, articles mention
related content, tasks depend on earlier tasks, accounts may have managers, and
orders may refer to existing rows in the same authored example. In plain table
text those relationships are written as IDs. In test code, it is more useful
when those IDs have been resolved to the actual parsed records.

```gherkin title="A content table with local relationships"
--8<-- "docs_src/guides/advanced/references.py:feature-content"
```

Talika references are deliberately local. They do not look in a database, a
global registry, another scenario, or a previously parsed table. They only
resolve against the records produced by the current parse call.

!!! tip "Think local graph, not external lookup"
    A reference cell contains a key. Talika resolves that key to another record
    from the same parsed result, then replaces the reference field with the
    resolved record object.

## Declare an ID and a Reference

References need a target field. In a `ColumnTable`, that usually starts with
an `id_field(...)` because each item column needs a stable identity.

```python title="A content schema with references"
--8<-- "docs_src/guides/advanced/references.py:content-schema"
```

This schema declares two reference fields:

- `parent` is a single reference to one content item
- `related` is a many-reference field containing several content IDs

Both references use the default target, `id`, because the schema has an
attribute named `id`. The table cells still contain text such as `ROOT` or
`A-1`; the parsed records receive object references.

```python title="The authored content table"
--8<-- "docs_src/guides/advanced/references.py:content-table"
```

Reference resolution happens after all records have been parsed and before
record validation runs. That timing matters because every target record must
exist before links can be connected.

!!! note "Reference labels are ordinary fields"
    `reference("Parent")` still declares a field. It can be required, can have
    aliases, and participates in source-aware diagnostics. The difference is
    that the final value becomes a record object instead of the raw key.

## Resolve One Reference

For a single reference, the authored cell contains one key.

```python title="Resolving parent content"
--8<-- "docs_src/guides/advanced/references.py:single-reference"
```

```bash { .talika-terminal title="Single reference result" .speed-3}
--8<-- "docs_src/guides/advanced/references.py:single-reference-output"
```

The root item has an empty `Parent` cell, so `root.parent` becomes `None`.
The article and poll both point to `ROOT`, so their `parent` fields become the
same `ContentTable` record object as `root`.

This is usually what test setup wants. The table author writes small readable
keys, while the test code can navigate records directly.

!!! warning "Empty optional references become None"
    An empty single-reference cell means "no linked record" unless the field is
    declared with `required=True`. It does not try to resolve an empty string as
    an ID.

## Resolve Many References

Set `many=True` when a cell can contain several keys.

```python title="Resolving related content"
--8<-- "docs_src/guides/advanced/references.py:many-reference"
```

```bash { .talika-terminal title="Many reference result" .speed-3}
--8<-- "docs_src/guides/advanced/references.py:many-reference-output"
```

By default, many references split the cell on commas and trim whitespace around
each key. The authored value `A-1, P-1` becomes two lookup keys: `A-1` and
`P-1`.

An empty many-reference cell becomes an empty list. That lets the caller
iterate over `record.related` without checking for `None`.

!!! note "Use a separator that cannot appear in IDs"
    The default separator is `","`. If your IDs can contain commas, choose a
    different separator when declaring the reference. An empty separator is not
    allowed.

## Use Typed IDs

Reference keys are parsed with the target field's parser before lookup.

That means a table can use typed IDs without making the reference field repeat
the parser. The target `id_field(...)` owns the key type, and references follow
that contract.

```python title="A table with integer IDs"
--8<-- "docs_src/guides/advanced/references.py:typed-schema"
```

```python title="Parsing typed references"
--8<-- "docs_src/guides/advanced/references.py:typed-parse"
```

```bash { .talika-terminal title="Typed reference result" .speed-3}
--8<-- "docs_src/guides/advanced/references.py:typed-output"
```

The child table cell contains `"101"`, but the target ID is parsed as the
integer `101`. Talika converts the reference key with the same target parser
before looking it up.

!!! tip "Put key parsing on the target field"
    If every record ID should be an integer, parse the `id_field`. References
    to that ID will use the same conversion automatically.

## Reference Another Target Field

The default reference target is `"id"`. Use `target=...` when the authored
table should link by another unique field.

```python title="Referencing by slug"
--8<-- "docs_src/guides/advanced/references.py:target-schema"
```

```python title="Resolving by a non-ID target"
--8<-- "docs_src/guides/advanced/references.py:target-parse"
```

Here the `Parent slug` cell contains `home`, so Talika looks for a record whose
parsed `slug` attribute is `"home"`. The resolved value is still the full
record object, not the slug string.

This is useful when the table author should read or write meaningful labels,
but the parsed record still has a separate technical ID.

!!! warning "The target must be unique"
    A reference target is an index. If two records have the same target value,
    Talika cannot know which record the authored key means, so parsing fails.

## Validate After References Resolve

Record validation runs after references are resolved. Validators can inspect
linked records directly.

```python title="A validator that uses a resolved reference"
--8<-- "docs_src/guides/advanced/references.py:validation-schema"
```

In this example, the parser first resolves `parent`. The validator then checks
whether the resolved parent is the same object as the current record.

```python title="A self-reference"
--8<-- "docs_src/guides/advanced/references.py:validation-call"
```

```text title="Validation diagnostic"
--8<-- "docs_src/guides/advanced/references.py:validation-output"
```

The validator uses `self.source_for("parent")` because the fix belongs to the
`Parent` cell. That gives the table author a precise source location instead
of a vague record-level failure.

!!! tip "Validate relationships after resolution"
    If a rule needs to compare records, let `reference()` resolve the link
    first. The validator can then work with objects instead of raw ID strings.

## Diagnose Missing References

When a key cannot be found, Talika points at the reference cell where the bad
key was written.

```python title="A reference to a missing ID"
--8<-- "docs_src/guides/advanced/references.py:missing-reference"
```

```text title="Missing reference diagnostic"
--8<-- "docs_src/guides/advanced/references.py:missing-reference-output"
```

The diagnostic includes:

- `code=reference_failed`
- the schema and reference field
- the source row and column of the bad key
- the current item ID, when known
- the authored key value

This is more helpful than reporting the target row, because the target row does
not exist. The table author needs to fix the cell that contains `MISSING`.

!!! note "Reference failures stop validation"
    Validators depend on links being trustworthy. If references cannot be
    resolved, Talika reports the reference problem before running dependent
    validation logic.

## Diagnose Ambiguous Targets

The target field must identify one record. If the target values are duplicated,
Talika reports the duplicate target cell.

```python title="A schema that references slugs"
--8<-- "docs_src/guides/advanced/references.py:duplicate-target-schema"
```

```python title="Two records with the same slug"
--8<-- "docs_src/guides/advanced/references.py:duplicate-target-call"
```

```text title="Duplicate target diagnostic"
--8<-- "docs_src/guides/advanced/references.py:duplicate-target-output"
```

The bad reference cell is not the main issue here. The table cannot build a
reliable slug index because two records both claim `same`. Talika points at
the duplicate target value so the author can make the target field unique.

!!! warning "Do not reference non-unique vocabulary"
    If a field is useful for display but not guaranteed unique, do not use it
    as a reference target. Add a stable ID or a unique slug field instead.

## Diagnose Bad Typed Keys

When a target field has a parser, the reference key must be valid for that
parser.

```python title="A reference key that cannot become an integer"
--8<-- "docs_src/guides/advanced/references.py:conversion-error"
```

```text title="Reference key conversion diagnostic"
--8<-- "docs_src/guides/advanced/references.py:conversion-error-output"
```

The error points at the reference cell, not the ID row. The ID parser is the
rule being reused, but the invalid authored value is in `Parent`.

!!! note "Typed references use target parsing only for lookup"
    The reference field itself does not become an integer. It becomes the
    resolved record object. The key is converted only so Talika can find the
    matching target record.

## References Also Work in Row Tables

Column tables are common for CMS-style linked content, but references are not
limited to column-shaped data. A row table can declare an `id_field(...)` and
reference it by attribute name.

```python title="A row-shaped dependency table"
--8<-- "docs_src/guides/advanced/references.py:row-schema"
```

```python title="Resolving row-table dependencies"
--8<-- "docs_src/guides/advanced/references.py:row-parse"
```

The same local-resolution rules apply. Talika parses every row into a record,
builds an index from `key`, and replaces `depends_on` with the referenced task
record.

Use row-shaped references when each row is naturally one object and the table
reader benefits from scanning relationships across rows.

!!! tip "Keep reference tables readable"
    References are easiest to maintain when keys are short, stable, and visible
    in the same table. If authors need to search elsewhere to understand a
    key, the table may need a clearer ID or shape.
