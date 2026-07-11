---
icon: lucide/languages
tags:
  - CellDSL
  - Domain language
  - Parsers
  - Data tables
---

# Table Vocabulary

As a test suite grows, feature tables often develop their own vocabulary. This
is not a bad thing. It is how teams keep examples readable.

A content author might prefer this:

```gherkin title="Author-friendly cells"
--8<-- "docs_src/learn/table-vocabulary.py:literal-table"
```

The words `random`, `20 words`, and `today` are not Python values. They are
project vocabulary. The project has to decide what they mean.

!!! tip "Vocabulary is a contract with authors"
    If a word appears in feature files, it should have one documented meaning.
    Otherwise every step definition becomes a private dialect.

## Compact table language

Sometimes vocabulary belongs to the whole table shape, not just one cell.

```gherkin title="Compact content table"
--8<-- "docs_src/learn/table-vocabulary.py:compact-table"
```

This might mean:

```python title="Logical records"
--8<-- "docs_src/learn/table-vocabulary.py:expanded-meaning"
```

The compact form is easier to write. The expanded form is easier for test code
to use. A good table layer lets the author write the compact form while keeping
diagnostics tied to the original cells.

## Own the language

Talika gives hooks for project vocabulary, but the project owns the words.

```python title="A project-owned word"
--8<-- "docs_src/learn/table-vocabulary.py:owner"
```

That function is not merely a parser. It is a decision: in the `headline`
field, the word `random` means "ask the test data generator for a headline."

For implementation choices, compare a [custom compact-domain parser](../guides/basic/custom-parsers.md#parse-compact-domain-syntax){ data-preview }
with [CellDSL tokens for stable vocabulary](../guides/advanced/cell-dsl-tokens.md#choose-tokens-for-stable-vocabulary){ data-preview }.

!!! warning "Do not let magic words spread casually"
    Words like `random`, `today`, and `default` are powerful because they hide
    detail. Use them when they make the table clearer, and keep their meaning
    consistent.
