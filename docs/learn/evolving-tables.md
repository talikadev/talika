---
icon: lucide/git-branch
tags:
  - Schema evolution
  - Backward compatibility
  - Aliases
  - Continuous integration
---

# Evolving Tables Safely

Feature tables change. A team renames a label. A new optional field appears. A
parser becomes stricter. Old scenarios still matter, but new scenarios should
read better.

Table evolution is healthiest when compatibility is intentional.

## Renaming language

An old table might use `Full name`:

```gherkin title="Older table wording"
--8<-- "docs_src/learn/evolving-tables.py:old-table"
```

A newer table might prefer `name` and add `active`:

```gherkin title="Newer table wording"
--8<-- "docs_src/learn/evolving-tables.py:new-table"
```

Both can be supported while the team migrates:

```python title="A contract that accepts old and new labels"
--8<-- "docs_src/learn/evolving-tables.py:contract"
```

The important part is that the old wording is visible. It is accepted because
the project chose to accept it, not because the parser ignored differences.

See [field aliases](../guides/basic/fields.md#aliases){ data-preview } for the
concrete migration mechanism.

!!! note "Compatibility should have a reason"
    Aliases are useful for migration, shared vocabulary, and external wording.
    They should not become a junk drawer for every spelling that ever appeared.

## Adding fields

Adding a required field breaks old tables immediately. Sometimes that is the
right choice. Other times the field should start as optional with a default, so
old scenarios remain valid while new scenarios can be more explicit.

Choose between those paths by asking whether an old table still describes a
valid scenario without the new field. If it does not, make the field required
and update the affected tables together. If omission still has a clear meaning,
introduce the field as optional and document the fallback in the schema.

!!! warning "Defaults can hide change"
    A default is convenient, but it also makes omitted data look intentional.
    Use it when omission is genuinely acceptable, not just to avoid updating
    tables.

## Preserve variant data during migration

Variant tables sometimes contain a value that belonged to an older record
shape. During a controlled migration, a project can preserve that known but
inapplicable value instead of treating it as an active field:

```python title="Preserving known variant fields during migration"
--8<-- "docs_src/learn/evolving-tables.py:preserve"
```

Preserved values live in `record.table_extras`; they do not appear in
`record.as_dict()` or become attributes on the selected variant. This policy
only applies to labels declared elsewhere in the variant family. Completely
unknown labels still follow the schema's `unknown_fields` policy.

Use preservation as a short-lived compatibility strategy while authors clean
up old tables. The [inapplicable-fields guide](../guides/advanced/inapplicable-fields.md#preserve-inapplicable-values){ data-preview }
shows how to inspect and eventually remove the preserved values.

## CI makes evolution safer

When table rules are explicit, a checker can validate feature files before the
scenario runs. That gives teams earlier feedback when a label changed, a parser
became stricter, or a compatibility alias was removed.

The static-checking guide shows how to [check feature tables from the CLI](../guides/advanced/static-checking.md#check-from-the-cli){ data-preview }.

!!! tip "Evolve in public"
    Feature tables are shared language. When you change that language, make the
    transition visible in the contract and easy to detect in CI.
