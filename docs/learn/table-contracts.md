---
icon: lucide/file-cog
tags:
  - Schemas
  - Contracts
  - Data tables
  - Validation
---

# Tables As Contracts

A table contract is the agreement between the feature file and the test code.
It says which labels are expected, which values are required, how cells should
be understood, and what should happen when the table does not match.

Start with a table that looks obvious:

```gherkin title="Authored table"
--8<-- "docs_src/learn/table-contracts.py:gherkin"
```

Humans can read this easily, but Python still needs the rules. Is `role` free
text or one of a few allowed values? Is `active` optional? Is `age` really a
number?

```python title="A table contract"
--8<-- "docs_src/learn/table-contracts.py:contract"
```

The contract is not only about conversion. It is a place to write down the
meaning of the table.

```python title="Meaning after parsing"
--8<-- "docs_src/learn/table-contracts.py:meaning"
```

## Labels and attributes

The table label is the word the feature author sees. The Python attribute is
the name test code uses after parsing.

That separation matters. Feature files can use product-facing language, while
Python keeps normal names. A future table might say `Full name`, while the code
still works with `record.name`.

!!! note "Contracts reduce drift"
    Drift happens when one step accepts `yes/no`, another accepts `true/false`,
    and a third silently accepts anything. A contract gives the table one place
    where those rules live.

## A contract protects the author too

If the authored labels no longer match the contract, the table should fail
near the table, not later in the test setup.

The fields guide turns this agreement into code, starting with how to
[define a field contract](../guides/basic/fields.md#define-a-field-contract){ data-preview }.

```gherkin title="A label that needs a decision"
--8<-- "docs_src/learn/table-contracts.py:bad-label"
```

This might be a mistake, or it might be a real vocabulary change. Either way,
the contract forces the project to decide instead of letting the table quietly
mean something different.

!!! tip "Treat contracts as documentation"
    A good contract is not just code that parses a table. It is executable
    documentation for the table language your project allows.
