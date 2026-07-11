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

!!! warning "Defaults can hide change"
    A default is convenient, but it also makes omitted data look intentional.
    Use it when omission is genuinely acceptable, not just to avoid updating
    tables.

## Preserving old information

Some projects temporarily preserve old columns or variant-specific values while
they migrate:

```python title="A legacy transition idea"
--8<-- "docs_src/learn/evolving-tables.py:preserve"
```

That should be a short-lived compatibility strategy, not the permanent design.

## CI makes evolution safer

When table rules are explicit, a checker can validate feature files before the
scenario runs. That gives teams earlier feedback when a label changed, a parser
became stricter, or a compatibility alias was removed.

The static-checking guide shows how to [check feature tables from the CLI](../guides/advanced/static-checking.md#check-from-the-cli){ data-preview }.

!!! tip "Evolve in public"
    Feature tables are shared language. When you change that language, make the
    transition visible in the contract and easy to detect in CI.
