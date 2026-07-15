"""Internal parsing engine and schema class implementation.

This private module owns the core parsing lifecycle: raw rows become source-aware
``TableData``, optional transformations run, labels are validated, field values
are parsed, variants are selected, references are resolved, validators run, and
optional output objects are built.

!!! warning
    Most helpers in this module are private lifecycle steps. They are documented
    because they carry important invariants, not because they are stable public
    extension points.
"""

from __future__ import annotations

import warnings
from collections.abc import Callable, Mapping, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast, overload

from .column_orientation import parse_column_table
from .context import CellContext, DefaultContext, ParseContext
from .diagnostics import (
    DiagnosticSeverity,
    TalikaWarning,
    ValidationResult,
    stable_text_value,
)
from .engine_types import (
    INVALID,
    DiagnosticCollector,
    LifecycleOutcome,
    error_diagnostic,
    non_raising_result,
    raising_result,
)
from .errors import (
    SchemaDefinitionError,
    TableError,
    TableErrorCode,
    TableErrors,
)
from .fields import MISSING, Field
from .output import build_outputs
from .records import TableRecord
from .references import resolve_references
from .row_orientation import parse_row_table
from .schema_compiler import (
    RESERVED_FIELD_NAMES,
    collect_fields,
    compile_schema,
    read_only_fields,
    resolve_annotations,
    update_variant_plan,
    validate_schema_family,
)
from .schema_plan import EmptyPolicy, ErrorMode, SchemaPlan
from .sources import RecordSource
from .table import RawTable, TableCell, TableData
from .validation import run_validation

if TYPE_CHECKING:
    from .introspection import TableContract

TableT = TypeVar("TableT", bound="BaseTable")
OutputT = TypeVar("OutputT")
_INVALID = INVALID


class SchemaMeta(type):
    """Collect field declarations and validate schema classes as they form.

    !!! info
        Schema creation is where inheritance, annotation-driven parser
        inference, and declarative variant generation become concrete runtime
        metadata.
    """

    def __new__(
        mcls, name: str, bases: tuple[type, ...], namespace: dict[str, Any]
    ) -> SchemaMeta:
        """Create one schema class.

        Args:
            name: Class name being created.
            bases: Base classes from the class definition.
            namespace: Class body namespace.

        Returns:
            Created schema class.

        Raises:
            TypeError: If declarative variant configuration is invalid.
            SchemaDefinitionError: If labels or policies are ambiguous.

        !!! info
            Inherited fields are cloned before being attached to the new class.
            This prevents parser inference or descriptor naming on a subclass
            from mutating the base schema declaration.

        """
        fields = collect_fields(name, bases, namespace)
        cls = super().__new__(mcls, name, bases, namespace)
        for field_name, declared in fields.items():
            if field_name not in namespace:
                type.__setattr__(cls, field_name, declared)
                declared.__set_name__(cls, field_name)
        schema_cls = cast(Any, cls)
        type.__setattr__(schema_cls, "__fields__", read_only_fields(fields))
        resolve_annotations(cls, fields)
        type.__setattr__(schema_cls, "__variants__", MappingProxyType({}))
        type.__setattr__(schema_cls, "__variant_root__", None)
        type.__setattr__(schema_cls, "__variant_value__", None)
        type.__setattr__(schema_cls, "__schema_sealed__", False)
        type.__setattr__(schema_cls, "__schema_plan__", compile_schema(cls, fields))
        type.__setattr__(schema_cls, "__schema_frozen__", True)
        declared_variant_fields = [
            declared
            for declared in namespace.values()
            if isinstance(declared, Field) and declared.variants is not None
        ]
        if declared_variant_fields:
            if len(declared_variant_fields) != 1:
                raise TypeError("A schema can declare only one variant mapping")
            mcls._register_component_variants(cls, declared_variant_fields[0])
            validate_schema_family(cls)
        return cls

    def __setattr__(cls, name: str, value: Any) -> None:
        """Reject mutation of metadata consumed by a compiled schema plan."""
        if cls.__dict__.get("__schema_frozen__", False):
            plan: SchemaPlan = cast(Any, cls).__schema_plan__
            protected = {
                *RESERVED_FIELD_NAMES,
                *plan.fields_by_name,
            }
            if name in protected or isinstance(value, Field):
                raise AttributeError(
                    f"Schema metadata is frozen; cannot assign {name!r}. "
                    "Declare the change on a schema subclass instead."
                )
        super().__setattr__(name, value)

    def _register_component_variants(cls: Any, declared: Field) -> None:
        """Compose declarative variant components with their table schema.

        Args:
            cls: Base table schema declaring ``discriminator(..., variants=...)``.
            declared: Discriminator field containing the component mapping.

        Raises:
            TypeError: If a mapping value is not a ``TableFields`` component.

        !!! info
            Generated variant classes inherit from both the component and the
            base schema, so selected records are instances of the base table
            and the active component.

        """
        variants = declared.variants or {}
        for value, component in variants.items():
            if not isinstance(component, SchemaMeta) or not issubclass(
                component, TableFields
            ):
                raise TypeError(
                    "discriminator variants must map to TableFields subclasses"
                )
            if issubclass(component, BaseTable):
                raise TypeError(
                    "declarative discriminator variants must be TableFields "
                    "components, not table schemas"
                )

            variant_name = f"{cls.__name__}{component.__name__}Variant"
            variant_display = (
                value if isinstance(value, str) else stable_text_value(value)
            )
            variant_cls = SchemaMeta(
                variant_name,
                (component, cls),
                {
                    "__module__": cls.__module__,
                    "__schema_display_name__": f"{cls.__name__}[{variant_display}]",
                    "__generated_variant__": True,
                    "__doc__": (
                        f"Generated {cls.__name__} variant for "
                        f"{stable_text_value(value)} using "
                        f"{component.__name__}."
                    ),
                },
            )
            cls.variant(value)(variant_cls)


class TableFields(metaclass=SchemaMeta):
    """Base class for reusable groups of field declarations.

    Components do not parse tables by themselves. Mix them into a concrete
    schema after ``RowTable`` or ``ColumnTable`` so their fields are collected
    by the shared schema metaclass.

    !!! example
        ```python
        class ArticleFields(TableFields):
            body = field("Body*", required=True)
        ```
    """

    __talika_framework_base__ = True
    __table_orientation__: ClassVar[str | None] = None


class BaseTable(TableRecord, TableFields):
    """Shared schema lifecycle for row- and column-oriented tables.

    Subclasses declare fields and may override lifecycle hooks such as
    :meth:`validate_record`. Users normally subclass :class:`RowTable` or
    :class:`ColumnTable` instead of using this class directly.

    Attributes:
        table_transformer: Optional reusable transformer object.
        output_model: Optional callable used by the default ``build_output``.
        unknown_fields: Policy for table labels not declared by the schema.
        inapplicable_fields: Policy for populated variant fields that do not
            apply to the selected variant.

    !!! info
        Public parsing APIs live on ``RowTable`` and ``ColumnTable`` because
        orientation determines how labels and records are found.

    """

    __talika_framework_base__ = True
    table_transformer = None
    output_model = None
    unknown_fields = "forbid"
    inapplicable_fields = "forbid"
    __variants__: ClassVar[Mapping[Any, type[BaseTable]]]
    __schema_plan__: ClassVar[SchemaPlan]
    __variant_root__: ClassVar[type[BaseTable] | None]
    __variant_value__: ClassVar[Any]

    @classmethod
    def variant(cls, value: Any) -> Callable[[type[BaseTable]], type[BaseTable]]:
        """Register a schema subclass for one discriminator value.

        The decorated class must inherit from the base schema. Its inherited
        fields remain common to every record, while newly declared fields are
        required, parsed, and validated only for records selecting that
        variant.

        Registration deliberately uses ordinary Python values. If a
        ``discriminator_field`` has a parser, register the parsed value rather
        than the raw table text.

        Args:
            value: Parsed discriminator value that should select the decorated
                schema subclass.

        Returns:
            A class decorator that registers and returns the variant class.

        !!! example
            ```python
            @ContentTable.variant("Article")
            class ArticleContent(ContentTable):
                body = field("Body*", required=True)
            ```

        """

        def register(variant_cls: type[BaseTable]) -> type[BaseTable]:
            """Register the decorated class as a discriminator variant.

            Args:
                variant_cls: Schema subclass selected by ``value``.

            Returns:
                The same class supplied by the decorator.

            Raises:
                TypeError: If the class does not inherit from the base schema
                    or the discriminator value is unhashable.
                ValueError: If ``value`` is already registered.

            !!! warning
                Variant values are looked up after discriminator parsing, so a
                custom discriminator parser changes the keys that should be
                registered here.

            """
            if cls.__dict__.get("__schema_sealed__", False):
                raise SchemaDefinitionError(
                    "Variant registration is sealed after schema finalization",
                    schema=cls.__name__,
                )
            if not isinstance(variant_cls, type) or not issubclass(variant_cls, cls):
                raise TypeError(
                    f"A variant of {cls.__name__} must inherit from {cls.__name__}"
                )
            if variant_cls is cls:
                raise TypeError("A schema cannot register itself as a variant")
            try:
                duplicate = value in cls.__variants__
            except TypeError as exc:
                raise TypeError("Variant values must be hashable") from exc
            if duplicate:
                raise ValueError(
                    "Variant value "
                    f"{stable_text_value(value)} is already registered on "
                    f"{cls.__name__}"
                )
            variants = dict(cls.__variants__)
            variants[value] = variant_cls
            type.__setattr__(cls, "__variants__", MappingProxyType(variants))
            type.__setattr__(variant_cls, "__variant_root__", cls)
            type.__setattr__(variant_cls, "__variant_value__", value)
            update_variant_plan(cls)
            return variant_cls

        return register

    @classmethod
    def variant_for(cls, value: Any) -> type[BaseTable]:
        """Return the registered schema class for one parsed selector value.

        This is especially useful with declarative ``discriminator()``
        mappings, whose concrete schema classes are generated by the package.
        A missing value raises ``KeyError`` just like an ordinary mapping.

        Args:
            value: Parsed discriminator value.

        Returns:
            Registered concrete variant schema class.

        !!! info
            Prefer this method over relying on generated variant class names.

        """
        return cls.__schema_plan__.variants[value].schema_type

    @classmethod
    def describe(cls) -> TableContract:
        """Return an immutable machine-readable description of this schema.

        The import is local to keep the parser core independent from the
        introspection dataclasses during class creation.

        Returns:
            Immutable machine-readable table contract.

        !!! example
            ```python
            contract = UserTable.describe()
            assert contract.fields[0].label == "name"
            ```

        """
        from .introspection import describe_schema

        validate_schema_family(cls)
        return describe_schema(cls)

    @classmethod
    def parse(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a table into validated records for a concrete orientation.

        Args:
            datatable: Raw string rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of the concrete schema class.

        Raises:
            NotImplementedError: Always, because ``BaseTable`` lacks an
                orientation.

        !!! warning
            Use ``RowTable`` or ``ColumnTable``. This base method documents the
            common signature only.

        """
        raise NotImplementedError("Use RowTable or ColumnTable")

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT],
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT]: ...

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]: ...

    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT] | None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT] | list[Any]:
        """Parse a table and convert each validated record.

        Args:
            datatable: Raw string rows or source-aware ``TableData``.
            output_model: Optional callable receiving record fields as keyword
                arguments. When omitted, use configured output hooks.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Converted output objects.

        Raises:
            NotImplementedError: Always, because ``BaseTable`` lacks an
                orientation.

        !!! warning
            Use ``RowTable`` or ``ColumnTable``. This base method documents the
            common signature only.

        """
        raise NotImplementedError("Use RowTable or ColumnTable")

    @classmethod
    def validate(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
    ) -> ValidationResult[TableT]:
        """Validate table data through a concrete orientation.

        Args:
            datatable: Raw string rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.

        Returns:
            A non-raising validation result containing records or diagnostics.

        Raises:
            NotImplementedError: Always, because ``BaseTable`` lacks an
                orientation.

        """
        raise NotImplementedError("Use RowTable or ColumnTable")

    def validate_record(self, context: ParseContext) -> None:
        """Validate one parsed record after fields and references are available.

        Args:
            context: Parse context for the current operation.

        Raises:
            TableError: For custom source-aware diagnostics.
            Exception: Any other exception is wrapped as a record validation
                failure.

        !!! example
            ```python
            def validate_record(self, context):
                if self.end < self.start:
                    raise ValueError("end must be after start")
            ```

        """

    @classmethod
    def validate_records(
        cls, records: Sequence[BaseTable], context: ParseContext
    ) -> None:
        """Validate relationships across all parsed records.

        Args:
            records: Validated records from one table.
            context: Parse context for the current operation.

        Raises:
            TableError: For custom source-aware diagnostics.
            Exception: Any other exception is wrapped as a table validation
                failure.

        !!! info
            This hook runs after local references are resolved, so validators
            can inspect linked records.

        """

    @classmethod
    def build_output(cls, record: BaseTable, context: ParseContext) -> Any:
        """Convert one validated schema record to its public result object.

        The default implementation returns the schema record unchanged unless
        ``output_model`` is configured, in which case it calls that model with
        the record fields as keyword arguments. Projects may override this
        hook for custom constructors, selected fields, context dependencies,
        or factory services.

        Args:
            record: Validated schema record.
            context: Parse context for the current operation.

        Returns:
            Public object returned by ``parse_as()`` for this record.

        !!! info
            ``parse()`` returns schema records without calling this hook.
            ``parse_as()`` uses it only when no explicit output model is
            supplied.

        """
        output_model = cls.__schema_plan__.hooks.output_model
        if output_model is None:
            return record
        return output_model(**record.as_dict())

    @classmethod
    def transform_table(cls, table: TableData, context: ParseContext) -> TableData:
        """Return the source-aware table that should be parsed by the schema.

        The default implementation delegates to ``table_transformer`` when a
        schema declares one; otherwise it returns the table unchanged. A
        project may override this hook for a table shape or grammar that does
        not fit a reusable transformer.

        Implementations must return :class:`TableData`. Reuse existing cells
        and create changed values with :meth:`TableCell.with_value` so later
        errors continue to identify the original feature-file cell.

        Args:
            table: Source-aware table after raw input normalization.
            context: Parse context for the current operation.

        Returns:
            Source-aware table consumed by orientation-specific parsing.

        !!! warning
            Returning raw rows loses source information and is rejected by the
            parser lifecycle.

        """
        transformer = cls.__schema_plan__.hooks.table_transformer
        if transformer is None:
            return table
        return transformer.transform(table, context, schema=cls)

    @classmethod
    def _accepted_labels(cls) -> set[str]:
        """Return labels declared by the base schema or any variant.

        Returns:
            Set of canonical labels and aliases accepted by the table family.

        !!! info
            Variant labels are accepted at table-shape validation time because
            the parser has not selected a variant for each record yet.

        """
        plan = cls.__schema_plan__
        labels = set(plan.accepted_labels)
        for variant in plan.variants.values():
            labels.update(variant.accepted_labels)
        return labels

    @classmethod
    def _declared_by_label(cls) -> dict[str, tuple[str, Field]]:
        """Map every canonical label and alias to its declaration.

        Returns:
            Mapping from table label text to ``(field_name, Field)``.

        !!! info
            This map is per schema class, so base and variant duplicate checks
            can evaluate their own applicable fields.

        """
        return {
            label: (item.name, item.declaration)
            for label, item in cls.__schema_plan__.fields_by_label.items()
        }

    @classmethod
    def _cell_for_field(
        cls,
        declared: Field,
        cells_by_label: Mapping[str, TableCell],
    ) -> TableCell | None:
        """Return the source cell for a field using its label or aliases.

        Args:
            declared: Field declaration to locate.
            cells_by_label: Mapping from actual table labels to source cells.

        Returns:
            Matching source cell, or ``None`` when the field is absent.

        !!! info
            Alias lookup preserves the distinction between an omitted field and
            an explicit empty cell.

        """
        for label in declared.labels:
            if label in cells_by_label:
                return cells_by_label[label]
        return None

    @classmethod
    def _validate_table_labels(
        cls,
        label_cells: Sequence[TableCell],
        errors: DiagnosticCollector,
    ) -> None:
        """Validate unknown labels and canonical/alias duplication.

        Args:
            label_cells: Source cells containing labels for one table
                orientation.
            errors: Optional collection sink for recoverable diagnostics.

        Raises:
            TableError: In fail-fast mode when an invalid label is found.

        !!! info
            Canonical/alias duplication is checked per schema and per variant
            so a table cannot provide both ``Headline`` and its alias ``Title``
            for the same applicable field.

        """
        accepted = cls._accepted_labels()
        for cell in label_cells:
            if cell.value in accepted:
                continue
            cls._report(
                TableError.from_cell(
                    "Unknown field label",
                    cell,
                    schema=cls,
                    field_label=cell.value,
                    code=TableErrorCode.UNKNOWN_FIELD,
                    hint="Use one of the schema field labels or aliases.",
                ),
                errors,
            )

        plans = (cls.__schema_plan__, *cls.__schema_plan__.variants.values())
        for plan in plans:
            bindings = {
                label: (item.name, item.declaration)
                for label, item in plan.fields_by_label.items()
            }
            seen: dict[str, tuple[str, TableCell]] = {}
            for cell in label_cells:
                binding = bindings.get(cell.value)
                if binding is None:
                    continue
                field_name, declared = binding
                if field_name in seen:
                    previous_label, _ = seen[field_name]
                    if previous_label == cell.value:
                        continue
                    cls._report(
                        TableError.from_cell(
                            "Table contains both a field label and one of its aliases",
                            cell,
                            schema=cls,
                            field_name=field_name,
                            field_label=declared.label,
                            code=TableErrorCode.DUPLICATE_LABEL,
                            hint=(
                                "Use either the canonical label or one alias, not "
                                "both in the same table."
                            ),
                        ),
                        errors,
                    )
                seen[field_name] = (cell.value, cell)

    @classmethod
    def _select_record_schema(
        cls,
        cells_by_label: Mapping[str, TableCell],
        *,
        parse_context: ParseContext,
        item_id: Any | None,
        errors: DiagnosticCollector,
    ) -> tuple[type[BaseTable] | None, dict[str, Any]]:
        """Select one record schema and return parsed selector values.

        Args:
            cells_by_label: Mapping from table labels to cells for one record.
            parse_context: Parse context for the current operation.
            item_id: Current record ID when available.
            errors: Optional collection sink for recoverable diagnostics.

        Returns:
            ``(record_schema, parsed_selector_values)``. ``record_schema`` is
            ``None`` when selector parsing failed in collect mode.

        !!! warning
            The discriminator parser runs before variant lookup. Registered
            variant keys must match parsed values, not raw table text.

        """
        plan = cls.__schema_plan__
        if not plan.variants:
            return cls, {}

        discriminator = plan.discriminator
        if discriminator is None:
            raise RuntimeError("A finalized variant family must have a discriminator")
        name = discriminator.name
        declared = discriminator.declaration
        cell = cls._cell_for_field(declared, cells_by_label)
        value = cls._value_for(
            declared,
            present=cell is not None,
            cell=cell,
            parse_context=parse_context,
            item_id=item_id,
            source_uri=cell.source_uri if cell is not None else None,
            errors=errors,
        )
        if value is _INVALID:
            return None, {}
        try:
            variant_cls = plan.variants[value].schema_type
        except (KeyError, TypeError) as exc:
            if cell is None:
                raise RuntimeError("A required discriminator must have a cell") from exc
            choices = ", ".join(stable_text_value(choice) for choice in plan.variants)
            error = TableError.from_cell(
                (
                    f"Unknown variant {stable_text_value(value)}; "
                    f"expected one of: {choices}"
                ),
                cell,
                schema=cls,
                field_name=declared.name,
                field_label=declared.label,
                item_id=item_id,
                code=TableErrorCode.UNKNOWN_VARIANT,
                hint="Use a discriminator value registered on this schema.",
                cause=exc,
            )
            cls._report(error, errors)
            return None, {}
        return variant_cls, {name: value}

    @classmethod
    def _reject_inapplicable_values(
        cls,
        record_cls: type[BaseTable],
        cells_by_label: Mapping[str, TableCell],
        *,
        item_id: Any | None,
        errors: DiagnosticCollector,
    ) -> dict[str, Any]:
        """Apply policy to values belonging to another selected variant.

        Variant tables often include the union of all possible rows or
        columns. An empty cell is therefore harmless, but a non-empty cell for
        a field that the selected variant does not declare usually indicates
        a typo or a misunderstood table.

        Args:
            record_cls: Variant schema selected for the current record.
            cells_by_label: Mapping from table labels to cells for one record.
            item_id: Current record ID when available.
            errors: Optional collection sink for recoverable diagnostics.

        Returns:
            Preserved inapplicable values when policy is ``"preserve"``.

        !!! info
            Empty inapplicable cells are ignored so one table can contain the
            union of variant fields without requiring every record shape to
            populate every column or row.

        """
        if record_cls is cls:
            return {}
        applicable = record_cls.__schema_plan__.accepted_labels
        extras: dict[str, Any] = {}
        for label, cell in cells_by_label.items():
            if label in applicable or cell.value == "":
                continue
            if label not in cls._accepted_labels():
                continue
            if cls.__schema_plan__.policies.inapplicable_fields.value == "preserve":
                extras[label] = cell.value
                continue
            error = TableError.from_cell(
                "Field does not apply to variant "
                f"{stable_text_value(record_cls.__variant_value__)}",
                cell,
                schema=record_cls,
                field_label=label,
                item_id=item_id,
                code=TableErrorCode.INAPPLICABLE_FIELD,
                hint=(
                    "Move this value to a record with the matching variant, leave "
                    "the cell empty, or change inapplicable_fields policy."
                ),
            )
            cls._report(error, errors)
        return extras

    @classmethod
    def _parse_context(
        cls, context: Mapping[str, Any] | ParseContext | None
    ) -> ParseContext:
        """Normalize user-supplied parse context.

        Args:
            context: ``None``, a mapping, or an existing ``ParseContext``.

        Returns:
            A ``ParseContext`` instance.

        Raises:
            TableError: If the context cannot be treated as a mapping.

        !!! info
            Wrapping context errors in ``TableError`` keeps public parse
            failures consistent with table diagnostics.

        """
        try:
            return ParseContext.from_value(context)
        except (TypeError, ValueError) as exc:
            raise TableError(
                "Context must be a mapping",
                schema=cls,
                code=TableErrorCode.INVALID_CONTEXT,
                cause=exc,
            ) from exc

    @classmethod
    def _validate_error_mode(cls, error_mode: str) -> ErrorMode:
        """Normalize the public failure strategy before parsing begins.

        Args:
            error_mode: Public parser failure strategy.

        Raises:
            ValueError: If ``error_mode`` is not ``"first"`` or ``"collect"``.

        !!! warning
            This is an API misuse check rather than a table diagnostic, so it
            raises ``ValueError`` directly.

        """
        try:
            return ErrorMode(error_mode)
        except ValueError as exc:
            raise ValueError("error_mode must be 'first' or 'collect'") from exc

    @staticmethod
    def _report(
        error: TableError,
        errors: DiagnosticCollector,
        *,
        allow_warning: bool = False,
    ) -> object:
        """Raise immediately or append one recoverable diagnostic.

        Args:
            error: Structured diagnostic to report.
            errors: Collector containing the active error mode and diagnostics.
            allow_warning: Whether a warning may continue without producing a
                value. Only validation hooks enable this path.

        Returns:
            Internal invalid sentinel when the error is collected.

        Raises:
            TableError: In fail-fast mode.

        !!! info
            Returning a sentinel lets parsing continue safely while skipping
            only the invalid value or record.

        """
        if error.severity is DiagnosticSeverity.WARNING and allow_warning:
            if errors.mode is ErrorMode.FIRST:
                warnings.warn(TalikaWarning(error.diagnostic), stacklevel=4)
                return _INVALID
            errors.items.append(error)
            return _INVALID
        if error.severity is DiagnosticSeverity.WARNING:
            error = TableError.from_diagnostic(error_diagnostic(error.diagnostic))
        if errors.mode is ErrorMode.FIRST:
            raise error
        errors.items.append(error)
        return _INVALID

    @staticmethod
    def _raise_collected(errors: DiagnosticCollector) -> None:
        """Raise the public aggregate after all safe validation has run.

        Args:
            errors: Active lifecycle diagnostic collector.

        Raises:
            TableErrors: If ``errors`` contains one or more diagnostics.

        !!! warning
            Dependent lifecycle stages stop after collected structural errors
            so users do not receive noisy secondary failures.

        """
        if errors.errors:
            raise TableErrors(errors.items)

    @classmethod
    def _prepare_table(
        cls,
        datatable: RawTable | TableData,
        parse_context: ParseContext,
    ) -> TableData:
        """Create source cells, run transformation, and validate its contract.

        Args:
            datatable: Raw rows or already source-aware table.
            parse_context: Parse context for the current operation.

        Returns:
            Transformed source-aware table.

        Raises:
            TableError: If raw or transformed tables are empty, the
                transformer fails, or the transformer returns a non-TableData
                value.

        !!! info
            Both the source and transformed table are checked for minimum shape
            so transformation cannot produce an unparsable empty table.

        """
        try:
            source_table = TableData.ensure(datatable)
        except (TypeError, ValueError) as exc:
            raise TableError(
                f"Invalid table input: {exc}",
                schema=cls,
                code=TableErrorCode.INVALID_TABLE_INPUT,
                cause=exc,
            ) from exc
        cls._check_table(source_table)

        try:
            transform = cls.__schema_plan__.hooks.transform_table
            if transform is None:
                transformed = source_table
            else:
                transformed = transform(source_table, parse_context)
        except (TableError, TableErrors, SchemaDefinitionError):
            raise
        except Exception as exc:
            raise TableError(
                f"Table transformation failed: {exc}",
                schema=cls,
                code=TableErrorCode.TRANSFORM_FAILED,
                source_uri=source_table.source_uri,
                cause=exc,
            ) from exc

        if not isinstance(transformed, TableData):
            raise TableError(
                "Table transformation must return TableData",
                schema=cls,
                code=TableErrorCode.INVALID_TRANSFORM,
                source_uri=source_table.source_uri,
            )

        if transformed.source_uri is None and source_table.source_uri is not None:
            transformed = transformed.with_source(source_table.source_uri)
        cls._check_table(transformed)
        return transformed

    @classmethod
    def _value_for(
        cls,
        declared: Field,
        *,
        present: bool,
        cell: TableCell | None,
        parse_context: ParseContext,
        item_id: Any | None,
        source_uri: str | None = None,
        errors: DiagnosticCollector,
    ) -> Any:
        """Resolve one declared field from a present or missing cell.

        Args:
            declared: Field declaration being resolved.
            present: Whether any canonical label or alias appeared.
            cell: Source cell when the field is present.
            parse_context: Parse context for the current operation.
            item_id: Current record ID when available.
            source_uri: Source document URI when no cell supplies it.
            errors: Optional collection sink for recoverable diagnostics.

        Returns:
            Parsed/default field value, or the internal invalid sentinel when
            collect mode records a failure.

        Raises:
            RuntimeError: If callers mark a field present without passing a
                source cell.
            TableError: In fail-fast mode for missing/empty/parser failures.

        !!! warning
            Missing optional fields and explicit empty cells are distinct.
            Defaults run only when the field label is absent.

        """
        if not present:
            if declared.required:
                return cls._report(
                    TableError(
                        "Required field is missing from the table",
                        schema=cls,
                        field_name=declared.name,
                        field_label=declared.label,
                        source_uri=source_uri,
                        item_id=item_id,
                        code=TableErrorCode.MISSING_REQUIRED,
                        hint=(
                            "Add this field to the table, or make the schema field "
                            "optional if the project should supply it."
                        ),
                    ),
                    errors,
                )
            if declared.default_factory is not MISSING:
                factory_context = DefaultContext(
                    schema=cls,
                    field_name=declared.name,
                    field_label=cast(str, declared.label),
                    item_id=item_id,
                    user_data=parse_context.user_data,
                    source_uri=source_uri,
                )
                try:
                    factory = cast(
                        Callable[[DefaultContext], Any], declared.default_factory
                    )
                    return factory(factory_context)
                except TableError as exc:
                    return cls._report(exc, errors)
                except (TableErrors, SchemaDefinitionError):
                    raise
                except Exception as exc:
                    error = TableError(
                        f"Default factory failed: {exc}",
                        schema=cls,
                        field_name=declared.name,
                        field_label=declared.label,
                        source_uri=source_uri,
                        item_id=item_id,
                        code=TableErrorCode.DEFAULT_FACTORY_FAILED,
                        cause=exc,
                    )
                    return cls._report(
                        error,
                        errors,
                    )
            return None if declared.default is MISSING else declared.default

        if cell is None:
            raise RuntimeError("A present field must provide a TableCell")

        if cell.value == "":
            empty_policy = cls.__schema_plan__.fields_by_name[declared.name].empty
            if declared.required:
                return cls._report(
                    TableError.from_cell(
                        "Required field has an empty value",
                        cell,
                        schema=cls,
                        field_name=declared.name,
                        field_label=declared.label,
                        item_id=item_id,
                        code=TableErrorCode.EMPTY_REQUIRED,
                        hint=(
                            "Fill the cell, or remove required=True if an explicit "
                            "empty value should be valid."
                        ),
                    ),
                    errors,
                )
            if not declared.required and empty_policy is EmptyPolicy.NONE:
                return None
            if not declared.required and empty_policy is EmptyPolicy.ERROR:
                return cls._report(
                    TableError.from_cell(
                        "Optional field has an empty value",
                        cell,
                        schema=cls,
                        field_name=declared.name,
                        field_label=declared.label,
                        item_id=item_id,
                        code=TableErrorCode.EMPTY_OPTIONAL,
                        hint=(
                            "Fill the cell, omit the field, or choose a different "
                            "empty-cell policy for this schema field."
                        ),
                    ),
                    errors,
                )
            if empty_policy is not EmptyPolicy.PARSE:
                return ""

        if declared.parser is None:
            return cell.value

        cell_context = CellContext(
            schema=cls,
            field_name=declared.name,
            field_label=cast(str, declared.label),
            row=cell.source_row,
            column=cell.source_column,
            item_id=item_id,
            source_value=cell.source_value,
            user_data=parse_context.user_data,
            source_uri=cell.source_uri,
        )
        try:
            return declared.parser(cell.value, cell_context)
        except TableError as exc:
            return cls._report(exc, errors)
        except (TableErrors, SchemaDefinitionError):
            raise
        except Exception as exc:
            error = TableError.from_cell(
                f"Field parser failed: {exc}",
                cell,
                schema=cls,
                field_name=declared.name,
                field_label=declared.label,
                item_id=item_id,
                code=TableErrorCode.PARSER_FAILED,
                hint="Check the cell value or adjust the field parser for this syntax.",
                cause=exc,
            )
            return cls._report(
                error,
                errors,
            )

    @classmethod
    def _check_table(cls, table: TableData) -> None:
        """Reject tables that cannot contain schema labels.

        Args:
            table: Source-aware table to validate.

        Raises:
            TableError: If the table or its label row/column is empty.

        !!! info
            Orientation-specific parsers perform rectangularity checks after
            this minimum shape validation.

        """
        if not table.rows:
            raise TableError(
                "Table is empty",
                schema=cls,
                source_uri=table.source_uri,
                code=TableErrorCode.TABLE_EMPTY,
                hint="Provide at least a header row with field labels.",
            )
        if not table.rows[0]:
            raise TableError(
                "Table header is empty",
                schema=cls,
                source_uri=table.source_uri,
                row=1,
                code=TableErrorCode.HEADER_EMPTY,
                hint="Provide field labels in the first row or first column.",
            )

    @classmethod
    def _validate_id(
        cls,
        value: Any,
        cell: TableCell,
        declared: Field,
        errors: DiagnosticCollector,
    ) -> bool:
        """Require a parsed identity value that can safely key indexes."""
        try:
            hash(value)
        except TypeError as exc:
            error = TableError.from_cell(
                f"Parsed item ID {stable_text_value(value)} must be hashable",
                cell,
                schema=cls,
                field_name=declared.name,
                field_label=declared.label,
                code=TableErrorCode.INVALID_ID,
                hint="Return a hashable scalar value from the ID parser.",
                cause=exc,
            )
            cls._report(error, errors)
            return False
        return True

    @classmethod
    def _reject_duplicates(
        cls,
        label_cells: Sequence[TableCell],
        errors: DiagnosticCollector,
    ) -> None:
        """Reject repeated table labels using original source locations.

        Args:
            label_cells: Cells containing labels for the active orientation.
            errors: Optional collection sink for recoverable diagnostics.

        Raises:
            TableError: In fail-fast mode when a duplicate is found.

        !!! warning
            Duplicate labels are rejected before field lookup because otherwise
            the parser would have to choose between multiple source cells for
            the same schema field.

        """
        seen = set()
        for cell in label_cells:
            label = cell.value
            if label in seen:
                cls._report(
                    TableError.from_cell(
                        "Table contains a duplicate field label",
                        cell,
                        schema=cls,
                        field_label=label,
                        code=TableErrorCode.DUPLICATE_LABEL,
                        hint="Keep only one row or column for this field label.",
                    ),
                    errors,
                )
            seen.add(label)

    @classmethod
    def _validate_required_presence(
        cls,
        labels: Sequence[str],
        errors: DiagnosticCollector,
        *,
        source_uri: str | None = None,
    ) -> None:
        """Validate required fields when a table contains no records.

        Args:
            labels: Labels present in the table's label row or column.
            errors: Optional collection sink for recoverable diagnostics.
            source_uri: Source document URI for missing-field diagnostics.

        Raises:
            TableError: In fail-fast mode when a required field is absent.

        !!! info
            Normal record parsing reports missing required fields per record.
            This helper handles empty data tables where no record loop runs.

        """
        present = set(labels)
        for item in cls.__schema_plan__.fields:
            declared = item.declaration
            if declared.required and not present.intersection(declared.labels):
                cls._report(
                    TableError(
                        "Required field is missing from the table",
                        schema=cls,
                        field_name=item.name,
                        field_label=declared.label,
                        source_uri=source_uri,
                        code=TableErrorCode.MISSING_REQUIRED,
                        hint=(
                            "Add this field to the table, or make the schema field "
                            "optional if the project should supply it."
                        ),
                    ),
                    errors,
                )

    @classmethod
    def _parse_record_values(
        cls,
        record_cls: type[BaseTable],
        cells_by_label: Mapping[str, TableCell],
        *,
        parse_context: ParseContext,
        item_id: Any | None,
        errors: DiagnosticCollector,
        parsed_values: Mapping[str, Any] | None = None,
        parsed_sources: Mapping[str, TableCell] | None = None,
    ) -> tuple[bool, dict[str, Any], dict[str, TableCell], Any | None]:
        """Parse applicable fields for one record schema."""
        values = dict(parsed_values or {})
        source_cells = dict(parsed_sources or {})
        source_uri = next(
            (cell.source_uri for cell in cells_by_label.values() if cell.source_uri),
            None,
        )
        record_item_id = item_id
        valid_record = True

        for item in record_cls.__schema_plan__.fields:
            name = item.name
            declared = item.declaration
            cell = record_cls._cell_for_field(declared, cells_by_label)
            if name in values:
                value = values[name]
            else:
                value = record_cls._value_for(
                    declared,
                    present=cell is not None,
                    cell=cell,
                    parse_context=parse_context,
                    item_id=record_item_id,
                    source_uri=source_uri,
                    errors=errors,
                )
                if value is _INVALID:
                    valid_record = False
                    continue
                values[name] = value

            if cell is not None:
                source_cells[name] = cell
            if declared.is_id:
                record_item_id = value

        return valid_record, values, source_cells, record_item_id

    @classmethod
    def _record_from_values(
        cls,
        values: dict[str, Any],
        *,
        cells: Mapping[str, TableCell],
        row: int | None = None,
        column: int | None = None,
        item_id: Any | None = None,
        extras: Mapping[str, Any] | None = None,
    ) -> BaseTable:
        """Construct one schema record with immutable source metadata.

        Args:
            values: Parsed field values keyed by schema attribute name.
            cells: Source cells keyed by schema attribute name.
            row: Source row for row-oriented records.
            column: Source ID column for column-oriented records.
            item_id: Parsed record ID when available.
            extras: Preserved inapplicable variant values.

        Returns:
            Populated schema record.

        !!! info
            Source metadata is attached before validation hooks run so custom
            validators can raise source-aware diagnostics.

        """
        source = RecordSource.create(
            item_id=item_id,
            row=row,
            column=column,
            cells=cells,
            source_uri=next(
                (cell.source_uri for cell in cells.values() if cell.source_uri),
                None,
            ),
        )
        return cast(BaseTable, cls._from_values(values, source=source, extras=extras))

    @classmethod
    def _finalize_records(
        cls,
        records: list[BaseTable],
        parse_context: ParseContext,
        errors: DiagnosticCollector,
        *,
        convert_output: bool = True,
        output_model: Callable[..., Any] | None = None,
    ) -> list[Any]:
        """Run reference resolution, validation, and output conversion.

        Args:
            records: Parsed schema records.
            parse_context: Parse context for the current operation.
            errors: Lifecycle diagnostic collector.
            convert_output: Whether to call output builders.
            output_model: Explicit callable applied to every converted record.

        Returns:
            Schema records or converted output objects.

        Raises:
            TableError: In fail-fast mode for reference, validation, or
                output failures.
            TableErrors: In collect mode when diagnostics were collected.

        !!! warning
            Dependent lifecycle stages run only after structural parse errors
            have been raised. This keeps collected diagnostics actionable.

        """
        # Cross-record references and validators assume every parsed record is
        # structurally valid. Running them against a partial table would add
        # misleading secondary failures, so collect mode reports cell parsing
        # errors first and stops before dependent lifecycle stages.
        cls._raise_collected(errors)

        resolve_references(cast(Any, cls), records, parse_context, errors)
        cls._raise_collected(errors)

        run_validation(cast(Any, cls), records, parse_context, errors)
        cls._raise_collected(errors)

        if not convert_output:
            return records

        converted = build_outputs(
            cast(Any, cls),
            records,
            parse_context,
            errors,
            output_model=output_model,
        )
        cls._raise_collected(errors)
        return converted

    @classmethod
    def _has_configured_output(cls) -> bool:
        """Return whether this schema family declares any output conversion."""
        plans = (cls.__schema_plan__, *cls.__schema_plan__.variants.values())
        return any(
            plan.hooks.output_model is not None or plan.hooks.build_output is not None
            for plan in plans
        )


class RowTable(BaseTable):
    """Parse tables whose first row contains labels and later rows are records.

    !!! example
        ```python
        class UserTable(RowTable):
            name = field("name", required=True)

        users = UserTable.parse([["name"], ["Alice"]])
        ```
    """

    __talika_framework_base__ = True
    __table_orientation__ = "row"

    @classmethod
    def parse(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a row-oriented table into validated schema records.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of this row schema. Configured output models
            and builders are intentionally not called.

        Raises:
            ValueError: If ``error_mode`` is unsupported.
            SchemaDefinitionError: If the schema family is invalid.
            TableError: If the first error-severity failure is found.
            TableErrors: If collect mode finds one or more error-severity
                failures.

        !!! info
            The first row supplies labels. Each following row is parsed as one
            record using those labels.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` and do not discard the records.

        """
        cls._validate_error_mode(error_mode)
        return raising_result(
            lambda: parse_row_table(
                cast(Any, cls),
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=False,
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=(
                datatable.source_uri if isinstance(datatable, TableData) else None
            ),
        )

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT],
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT]: ...

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]: ...

    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT] | None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT] | list[Any]:
        """Parse row records and convert them into public output objects.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            output_model: Optional callable receiving every parsed field as a
                keyword argument. When omitted, each record uses its configured
                ``output_model`` or custom ``build_output()`` hook.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Objects created after parsing, references, and validation finish.
            Supplying a callable produces ``list[OutputT]``.

        Raises:
            TypeError: If ``output_model`` is not callable.
            ValueError: If no explicit or configured conversion exists.
            TableError: If parsing, validation, or output construction fails.
            TableErrors: If collect mode finds multiple failures.

        !!! info
            An explicit callable overrides configured base and variant output
            hooks for this call.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` before converted objects are returned.

        """
        cls._validate_error_mode(error_mode)
        if output_model is not None and not callable(output_model):
            raise TypeError("output_model must be callable")
        if output_model is None and not cls._has_configured_output():
            raise ValueError(
                "parse_as() requires an output model or custom build_output()"
            )
        return raising_result(
            lambda: parse_row_table(
                cast(Any, cls),
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=True,
                output_model=output_model,
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=(
                datatable.source_uri if isinstance(datatable, TableData) else None
            ),
        )

    @classmethod
    def validate(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
    ) -> ValidationResult[TableT]:
        """Validate a row table without raising table-data diagnostics.

        Output models and custom output builders are deliberately skipped.
        Invalid results contain no partial records.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.

        Returns:
            Complete schema records and ordered diagnostics. Warning-only
            results are valid and retain their records.

        Raises:
            SchemaDefinitionError: If the schema family is invalid.

        """
        source_uri = datatable.source_uri if isinstance(datatable, TableData) else None
        return non_raising_result(
            lambda: cast(
                LifecycleOutcome[TableT],
                parse_row_table(
                    cast(Any, cls),
                    datatable,
                    context=context,
                    error_mode="collect",
                    convert_output=False,
                ),
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=source_uri,
        )


class ColumnTable(BaseTable):
    """Parse tables whose first column contains labels and later columns are records.

    !!! example
        ```python
        class ContentTable(ColumnTable):
            id = id_field("IDs")
            headline = field("Headline*", required=True)
        ```
    """

    __talika_framework_base__ = True
    __table_orientation__ = "column"

    @classmethod
    def parse(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a column-oriented table into validated schema records.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of this column schema. Configured output models
            and builders are intentionally not called.

        Raises:
            ValueError: If ``error_mode`` is unsupported.
            SchemaDefinitionError: If the schema family is invalid.
            TableError: If the first error-severity failure is found.
            TableErrors: If collect mode finds one or more error-severity
                failures.

        !!! info
            The first column supplies labels. Each following column is parsed
            as one record.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` and do not discard the records.

        """
        cls._validate_error_mode(error_mode)
        return raising_result(
            lambda: parse_column_table(
                cast(Any, cls),
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=False,
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=(
                datatable.source_uri if isinstance(datatable, TableData) else None
            ),
        )

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT],
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT]: ...

    @overload
    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]: ...

    @classmethod
    def parse_as(
        cls,
        datatable: RawTable | TableData,
        output_model: Callable[..., OutputT] | None = None,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[OutputT] | list[Any]:
        """Parse column records and convert them into public output objects.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            output_model: Optional callable receiving every parsed field as a
                keyword argument. When omitted, each record uses its configured
                ``output_model`` or custom ``build_output()`` hook.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Objects created after parsing, references, and validation finish.
            Supplying a callable produces ``list[OutputT]``.

        Raises:
            TypeError: If ``output_model`` is not callable.
            ValueError: If no explicit or configured conversion exists.
            TableError: If parsing, validation, or output construction fails.
            TableErrors: If collect mode finds multiple failures.

        !!! info
            An explicit callable overrides configured base and variant output
            hooks for this call.

        !!! note
            Warning-severity validation diagnostics are emitted as
            ``TalikaWarning`` before converted objects are returned.

        """
        cls._validate_error_mode(error_mode)
        if output_model is not None and not callable(output_model):
            raise TypeError("output_model must be callable")
        if output_model is None and not cls._has_configured_output():
            raise ValueError(
                "parse_as() requires an output model or custom build_output()"
            )
        return raising_result(
            lambda: parse_column_table(
                cast(Any, cls),
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=True,
                output_model=output_model,
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=(
                datatable.source_uri if isinstance(datatable, TableData) else None
            ),
        )

    @classmethod
    def validate(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
    ) -> ValidationResult[TableT]:
        """Validate a column table without raising table-data diagnostics.

        Output models and custom output builders are deliberately skipped.
        Invalid results contain no partial records.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.

        Returns:
            Complete schema records and ordered diagnostics. Warning-only
            results are valid and retain their records.

        Raises:
            SchemaDefinitionError: If the schema family is invalid.

        """
        source_uri = datatable.source_uri if isinstance(datatable, TableData) else None
        return non_raising_result(
            lambda: cast(
                LifecycleOutcome[TableT],
                parse_column_table(
                    cast(Any, cls),
                    datatable,
                    context=context,
                    error_mode="collect",
                    convert_output=False,
                ),
            ),
            schema_name=cls.__schema_plan__.display_name,
            source_uri=source_uri,
        )
