---
icon: lucide/combine
tags:
  - CellDSL
  - Parser composition
  - Custom parsing
  - Reusable parsers
---

# CellDSL Composition

Use CellDSL composition when table vocabulary is split across layers.

A project may have shared values such as `none` and `today`. A CMS area may
add content-specific values such as `fake:hero`. A payments area may add a
different set of generated values. Composition lets each vocabulary stay in
its own `CellDSL`, while one field parser can consult them together.

```gherkin title="A table using shared and content-specific syntax"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:feature-composition"
```

Composition does not copy all rules into one new registry. It asks each DSL in
order. The first DSL that matches the cell owns the result.

!!! tip "Think chain of responsibility"
    A composed parser asks the first DSL, then the second DSL, and so on. Once
    a DSL matches, later DSLs are not consulted for that cell.

## Define Shared Vocabulary

Shared vocabulary belongs in its own DSL.

```python title="Shared cell vocabulary"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:shared-dsl"
```

These tokens are not tied to one table shape. They can be reused across
schemas that want the same project meaning for `none` and `today`.

!!! note "Shared does not mean global state"
    A shared DSL is just a Python object containing parser rules. It does not
    create a global registry. A schema only uses it when you attach it as a
    field parser directly or through composition.

## Define Feature-Specific Vocabulary

Feature-specific vocabulary can live in another DSL.

```python title="Content-specific generated values"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:content-dsl"
```

This rule is only meaningful for content setup. Keeping it separate from
shared tokens avoids turning one DSL into a large mixed dictionary of unrelated
project syntax.

!!! tip "Group rules by ownership"
    Put organization-wide tokens in a shared DSL. Put feature-area syntax in a
    feature-area DSL. Then compose the pieces needed by each schema field.

## Compose the Parser

Use `compose_cell_dsls(...)` to create a parser that consults several DSLs.

```python title="Composed parser"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:compose-parser"
```

Attach the composed parser like any other field parser.

```python title="A schema using the composed parser"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:content-schema"
```

```python title="Parsing composed vocabulary"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:compose-call"
```

```bash { .talika-terminal title="Composed parser result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:compose-output"
```

The values resolve as follows:

- `none` matches `shared_cells`
- `fake:hero` does not match `shared_cells`, then matches `content_cells`
- `Literal` matches neither DSL and passes through unchanged
- `today` matches `shared_cells`

!!! note "Unmatched values still pass through"
    If no DSL in the chain matches the cell, the original value is returned.
    Composition does not make unmatched values invalid by itself.

## Order Decides Conflicts

If two DSLs can handle the same value, the earlier DSL wins.

```python title="Two DSLs with the same token"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:order-dsls"
```

```python title="Same DSLs in different orders"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:order-schema"
```

```bash { .talika-terminal title="Composition order result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:order-output"
```

This is useful, but it should be deliberate. If shared vocabulary and
feature-specific vocabulary use the same token, put the more specific DSL first
only when the feature really should override the shared meaning.

!!! warning "Composition order is part of the contract"
    Do not treat DSL order as cosmetic. It decides which parser owns conflicts.
    Keep the order visible near the schema field that uses it.

## Use the Method Form When It Reads Better

Each `CellDSL` also has `.compose(...)`. The method form is useful when one DSL
is clearly the primary vocabulary and the remaining DSLs are supporting layers.

```python title="Composing from the first DSL"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:method-compose"
```

```bash { .talika-terminal title="Method composition result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:method-output"
```

This is equivalent to:

```python title="Equivalent function form"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:method-equivalent"
```

Use whichever form makes ownership clearest in the surrounding code. The order
is the same: the receiver DSL is consulted first. The function form is often
clearer when every DSL is a peer and no single object should appear to own the
chain.

!!! note "The receiver goes first"
    `content_cells.compose(shared_cells)` means content rules are tried before
    shared rules.

## Place Fallbacks Carefully

A DSL with a fallback always matches any value that reaches it. That affects
composition.

```python title="A fallback DSL and a later token DSL"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:fallback-dsls"
```

The same two DSLs produce different results depending on order.

```python title="Fallback first vs fallback last"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:fallback-schema"
```

```bash { .talika-terminal title="Fallback order result" .speed-3}
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:fallback-output"
```

When fallback is first, it handles `none` before the later token DSL can see
it. When fallback is last, `none` resolves to `None`, and only unmatched values
reach fallback.

!!! warning "Fallbacks should usually be last"
    Put a fallback early only when it is meant to own every unmatched value
    before later DSLs. In most parser chains, fallback belongs at the end.

## Invalid Chains Fail Early

A composed chain must contain at least one DSL.

```python title="Empty composition"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:invalid-empty"
```

```text title="Empty composition error"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:invalid-empty-output"
```

Every item must be a `CellDSL` instance.

```python title="Invalid composition item"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:invalid-type"
```

```text title="Invalid composition item error"
--8<-- "docs_src/guides/advanced/cell-dsl-composition.py:invalid-type-output"
```

These checks happen when the composed parser is created, so schema code fails
early if the parser chain is not valid.

!!! note "Composition returns a parser"
    `compose_cell_dsls(...)` returns a callable parser object. Pass that object
    to `field(..., parser=...)` the same way you would pass a single `CellDSL`.

## Choose a Composition Shape

Use one DSL when the field has a small local vocabulary.

Use composition when the field should combine:

- shared project tokens
- feature-area generated values
- domain-specific normalizers
- temporary migration vocabulary
- a final fallback parser

Keep composition shallow. If a field needs many DSLs in a precise order, that
is a sign the table language may need to be simplified or split by ownership.

!!! tip "Keep parser ownership visible"
    A reader should be able to look at the schema field and understand which
    vocabularies are being applied, and in what order.
