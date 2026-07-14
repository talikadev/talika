"""Composition utilities for source-aware table transformations.

Transformers run after raw rows become ``TableData`` and before schema labels
and values are validated. They let projects turn compact BDD authoring syntax
into the logical table shape that schemas already understand.

!!! info
    Transformers must preserve source-aware cells so downstream diagnostics
    can still point at the original feature text.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from .context import ParseContext
from .errors import SchemaDefinitionError, TableError, TableErrorCode, TableErrors
from .table import TableData


class TableTransformer(Protocol):
    """Structural contract implemented by reusable table transformers.

    !!! info
        Any object with a compatible ``transform`` method satisfies this
        protocol; inheritance is not required.
    """

    def transform(
        self,
        table: TableData,
        context: ParseContext,
        *,
        schema: type | str | None = None,
    ) -> TableData:
        """Return a source-aware table for the next transformation stage.

        Args:
            table: Current source-aware logical table.
            context: Parse context for the current operation.
            schema: Optional schema identity for diagnostics.

        Returns:
            A ``TableData`` object.

        !!! warning
            Return ``TableData``, not raw rows. Use ``TableData.from_cells``
            after arranging source-aware cells.

        """


class TransformerPipeline:
    """Run table transformers from left to right.

    Each stage receives the previous stage's ``TableData`` and the same parse
    context. Unexpected failures identify the stage, while intentional
    ``TableError`` diagnostics pass through unchanged.

    Attributes:
        transformers: Immutable ordered transformation stages.

    !!! example
        ```python
        table_transformer = compose_transformers(
            NormalizeLabels(),
            ColumnGroupExpander(...),
        )
        ```

    """

    def __init__(self, transformers: Sequence[TableTransformer]) -> None:
        """Validate and store transformation stages.

        Args:
            transformers: Ordered transformer objects.

        Raises:
            ValueError: If no transformers are supplied.
            TypeError: If a stage lacks a callable ``transform`` method.

        !!! warning
            Pipeline order is observable because each stage receives the
            previous stage's output.

        """
        if not transformers:
            raise ValueError("TransformerPipeline requires at least one transformer")
        for transformer in transformers:
            if not callable(getattr(transformer, "transform", None)):
                raise TypeError("Table transformers must provide transform()")
        self.transformers = tuple(transformers)

    def transform(
        self,
        table: TableData,
        context: ParseContext,
        *,
        schema: type | str | None = None,
    ) -> TableData:
        """Apply every configured transformer and validate each result.

        Args:
            table: Initial source-aware table.
            context: Parse context for the current operation.
            schema: Optional schema identity for diagnostics.

        Returns:
            Final ``TableData`` produced by the last stage.

        Raises:
            TableError: If a stage raises a table error, raises an
                unexpected exception, or returns a non-``TableData`` value.

        !!! info
            Intentional ``TableError`` instances are re-raised unchanged so
            custom transformers keep their precise source diagnostics.

        """
        current = table
        for index, transformer in enumerate(self.transformers, start=1):
            stage_name = type(transformer).__name__
            source_uri = current.source_uri
            try:
                transformed = transformer.transform(current, context, schema=schema)
            except (TableError, TableErrors, SchemaDefinitionError):
                raise
            except Exception as exc:
                raise TableError(
                    f"Table transformer stage {index} ({stage_name}) failed: {exc}",
                    schema=schema,
                    code=TableErrorCode.TRANSFORM_FAILED,
                    source_uri=current.source_uri,
                    cause=exc,
                ) from exc
            if not isinstance(transformed, TableData):
                raise TableError(
                    f"Table transformer stage {index} ({stage_name}) must return "
                    "TableData",
                    schema=schema,
                    code=TableErrorCode.INVALID_TRANSFORM,
                    source_uri=source_uri,
                )
            current = (
                transformed.with_source(source_uri)
                if transformed.source_uri is None and source_uri is not None
                else transformed
            )
        return current


def compose_transformers(*transformers: TableTransformer) -> TransformerPipeline:
    """Create a reusable left-to-right table transformation pipeline.

    Args:
        *transformers: Ordered transformer stages.

    Returns:
        A ``TransformerPipeline`` that can be assigned to
        ``table_transformer`` on a schema.

    !!! example
        ```python
        class ContentTable(ColumnTable):
            table_transformer = compose_transformers(clean, expand)
        ```

    """
    return TransformerPipeline(transformers)
