"""Stable public schema façade.

The implementation lives in focused internal compiler and engine modules.
Projects should continue importing :class:`RowTable`, :class:`ColumnTable`,
and :class:`TableFields` from :mod:`talika` or :mod:`talika.schema`.
"""

from __future__ import annotations

from .engine import BaseTable, ColumnTable, RowTable, SchemaMeta, TableFields

# Preserve the historical qualified names used by documentation, reprs, schema
# targets, and pickling even though the implementation now lives in engine.py.
for _schema_type in (SchemaMeta, TableFields, BaseTable, RowTable, ColumnTable):
    type.__setattr__(_schema_type, "__module__", __name__)

del _schema_type

__all__ = ["BaseTable", "ColumnTable", "RowTable", "SchemaMeta", "TableFields"]
