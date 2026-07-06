---
icon: lucide/layout-panel-top
---

# Choosing A Table Shape

The first design choice is not which parser to use. It is how the table should
be read.

Some tables read naturally across rows. Others read better as vertical cards.
Both shapes are valid. The better one is the shape that makes the feature file
less tiring to scan.

## Row-shaped tables

Use a row-shaped table when every record has only a few fields and the reader
will compare many records at once.

```gherkin title="Rows are records"
--8<-- "docs_src/learn/choosing-table-shape.py:row-table"
```

This shape feels like a spreadsheet. It is compact, familiar, and good for
lists of users, roles, permissions, simple products, or short payments.

!!! tip "Good row-table signal"
    If your eyes naturally move left to right across one record, then down to
    the next record, a row-shaped table is probably right.

## Column-shaped tables

Use a column-shaped table when each item has many fields, or when readers think
of each item as a card.

```gherkin title="Columns are records"
--8<-- "docs_src/learn/choosing-table-shape.py:column-table"
```

Here, `article-1` and `poll-1` are the records. Each row describes one field of
those records. This is often easier for CMS content, configuration, page
sections, or objects with many optional fields.

```python title="The matching idea in code"
--8<-- "docs_src/learn/choosing-table-shape.py:column-contract"
```

## The wide-table smell

A row-shaped table can become hard to read when each record has too many
fields:

```gherkin title="Harder to scan"
--8<-- "docs_src/learn/choosing-table-shape.py:wide-row"
```

This table is still valid, but the reader has to work harder. Long text,
optional fields, and variant-specific columns often push a table toward the
column shape.

!!! note "Shape is for humans first"
    Talika can parse both shapes. The question is not "what can the library
    handle?" The question is "which table will future readers understand
    quickly?"
