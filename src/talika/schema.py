"""Row- and column-oriented BDD table schemas.

This module owns the core parsing lifecycle: raw rows become source-aware
``TableData``, optional transformations run, labels are validated, field values
are parsed, variants are selected, references are resolved, validators run, and
optional output objects are built.

!!! warning
    Most helpers in this module are private lifecycle steps. They are documented
    because they carry important invariants, not because they are stable public
    extension points.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, TypeVar, cast, get_type_hints

from .annotations import parser_for_annotation
from .context import CellContext, DefaultContext, ParseContext
from .errors import (
    SchemaDefinitionError,
    TableError,
    TableErrorCode,
    TableErrors,
)
from .fields import MISSING, Field
from .records import TableRecord
from .sources import RecordSource
from .table import RawTable, TableCell, TableData

if TYPE_CHECKING:
    from .introspection import TableContract

_INVALID = object()
TableT = TypeVar("TableT", bound="BaseTable")


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
        fields: dict[str, Field] = {}
        for base in bases:
            fields.update(
                (field_name, declared.clone())
                for field_name, declared in getattr(base, "__fields__", {}).items()
            )
        fields.update(
            (attribute, value)
            for attribute, value in namespace.items()
            if isinstance(value, Field)
        )
        cls = super().__new__(mcls, name, bases, namespace)
        for field_name, declared in fields.items():
            if field_name not in namespace:
                setattr(cls, field_name, declared)
                declared.__set_name__(cls, field_name)
        schema_cls = cast(Any, cls)
        schema_cls.__fields__ = fields
        mcls._validate_declaration(cls)
        try:
            annotations = get_type_hints(cls)
        except (NameError, TypeError):
            annotations = getattr(cls, "__annotations__", {})
        for field_name, declared in fields.items():
            if declared.parser is not None or field_name not in annotations:
                continue
            inferred = parser_for_annotation(annotations[field_name])
            if inferred is not None:
                declared.parser = inferred
                declared.parse_empty = bool(getattr(inferred, "parse_empty", False))
        schema_cls.__variants__ = {}
        schema_cls.__variant_root__ = None
        schema_cls.__variant_value__ = None
        declared_variant_fields = [
            declared
            for declared in namespace.values()
            if isinstance(declared, Field) and declared.variants is not None
        ]
        if declared_variant_fields:
            if len(declared_variant_fields) != 1:
                raise TypeError("A schema can declare only one variant mapping")
            mcls._register_component_variants(cls, declared_variant_fields[0])
        return cls

    @staticmethod
    def _validate_declaration(cls: Any) -> None:
        """Reject ambiguous labels and invalid schema policies.

        Args:
            cls: Schema class being validated during creation.

        Raises:
            SchemaDefinitionError: If labels/aliases collide or a policy value
                is unsupported.

        !!! warning
            This runs at import/class-definition time, so failures identify
            schema-code problems before any feature table is parsed.

        """
        labels: dict[str, str] = {}
        for field_name, declared in cls.__fields__.items():
            for label in declared.labels:
                if label in labels and labels[label] != field_name:
                    raise SchemaDefinitionError(
                        f"Field label or alias {label!r} is already used by "
                        f"{labels[label]!r}",
                        schema=cls.__name__,
                    )
                labels[label] = field_name

        policy_options = {
            "unknown_fields": ("forbid",),
            "inapplicable_fields": ("forbid", "preserve"),
        }
        for policy_name, allowed in policy_options.items():
            policy = getattr(cls, policy_name, "forbid")
            if policy not in allowed:
                allowed_values = " or ".join(f"{value!r}" for value in allowed)
                raise SchemaDefinitionError(
                    f"{policy_name} must be {allowed_values}",
                    schema=cls.__name__,
                )

    @staticmethod
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
            variant_cls = SchemaMeta(
                variant_name,
                (component, cls),
                {
                    "__module__": cls.__module__,
                    "__schema_display_name__": f"{cls.__name__}[{value}]",
                    "__generated_variant__": True,
                    "__doc__": (
                        f"Generated {cls.__name__} variant for {value!r} using "
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

    table_transformer = None
    output_model = None
    unknown_fields = "forbid"
    inapplicable_fields = "forbid"
    __variants__: ClassVar[dict[Any, type[BaseTable]]]
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
                    f"Variant value {value!r} is already registered on {cls.__name__}"
                )
            cls.__variants__[value] = variant_cls
            variant_cls.__variant_root__ = cls
            variant_cls.__variant_value__ = value
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
        return cls.__variants__[value]

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

        return describe_schema(cls)

    @classmethod
    def parse(
        cls,
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]:
        """Parse a table through a concrete row or column orientation.

        Args:
            datatable: Raw string rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Public output objects for parsed records.

        Raises:
            NotImplementedError: Always, because ``BaseTable`` lacks an
                orientation.

        !!! warning
            Use ``RowTable`` or ``ColumnTable``. This base method documents the
            common signature only.

        """
        raise NotImplementedError("Use RowTable or ColumnTable")

    @classmethod
    def parse_records(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a table and return validated schema records.

        ``parse()`` remains the high-level API and may return output-model
        objects when ``output_model`` or ``build_output()`` is configured.
        ``parse_records()`` is for callers and type checkers that specifically
        want instances of the schema class before output conversion.

        Args:
            datatable: Raw string rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated schema record instances.

        Raises:
            NotImplementedError: Always, because ``BaseTable`` lacks an
                orientation.

        !!! info
            Concrete orientation classes implement this shared contract.

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
            Public object returned by ``parse`` for this record.

        !!! warning
            ``parse_records`` bypasses this hook intentionally and returns the
            schema record itself.

        """
        if cls.output_model is None:
            return record
        return cls.output_model(**record.as_dict())

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
        if cls.table_transformer is None:
            return table
        return cls.table_transformer.transform(table, context, schema=cls)

    @classmethod
    def _validate_variant_configuration(cls) -> None:
        """Validate discriminator and variant declarations before parsing.

        Raises:
            TableError: If variants lack exactly one inherited discriminator
                or replace the base discriminator field.

        !!! info
            This check runs at parse time because variants may be registered by
            decorators after the base class has already been created.

        """
        cls._validate_schema_labels()
        if not cls.__variants__:
            return

        discriminators = [
            (name, declared)
            for name, declared in cls.__fields__.items()
            if declared.is_discriminator
        ]
        if len(discriminators) != 1:
            raise TableError(
                "Schemas with registered variants require exactly one "
                "discriminator_field",
                schema=cls,
            )

        discriminator_name, discriminator = discriminators[0]
        for variant_cls in cls.__variants__.values():
            variant_cls._validate_schema_labels()
            variant_discriminators = [
                (name, declared)
                for name, declared in variant_cls.__fields__.items()
                if declared.is_discriminator
            ]
            if len(variant_discriminators) != 1:
                raise TableError(
                    "Each variant must inherit the base discriminator_field",
                    schema=variant_cls,
                )
            name, declared = variant_discriminators[0]
            if name != discriminator_name or declared.label != discriminator.label:
                raise TableError(
                    "Variants cannot replace the base discriminator_field",
                    schema=variant_cls,
                    field=declared.label,
                )

    @classmethod
    def _accepted_labels(cls) -> set[str]:
        """Return labels declared by the base schema or any variant.

        Returns:
            Set of canonical labels and aliases accepted by the table family.

        !!! info
            Variant labels are accepted at table-shape validation time because
            the parser has not selected a variant for each record yet.

        """
        labels = {
            label for declared in cls.__fields__.values() for label in declared.labels
        }
        for variant_cls in cls.__variants__.values():
            labels.update(
                label
                for declared in variant_cls.__fields__.values()
                for label in declared.labels
            )
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
            label: (name, declared)
            for name, declared in cls.__fields__.items()
            for label in declared.labels
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
        errors: list[TableError] | None = None,
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
                    field=cell.value,
                    code=TableErrorCode.UNKNOWN_FIELD,
                    hint="Use one of the schema field labels or aliases.",
                ),
                errors,
            )

        schemas = (cls, *cls.__variants__.values())
        for schema in schemas:
            bindings = schema._declared_by_label()
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
                            field=declared.label,
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
        errors: list[TableError] | None = None,
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
        if not cls.__variants__:
            return cls, {}

        name, declared = next(
            (name, declared)
            for name, declared in cls.__fields__.items()
            if declared.is_discriminator
        )
        cell = cls._cell_for_field(declared, cells_by_label)
        value = cls._value_for(
            declared,
            present=cell is not None,
            cell=cell,
            parse_context=parse_context,
            item_id=item_id,
            errors=errors,
        )
        if value is _INVALID:
            return None, {}
        try:
            variant_cls = cls.__variants__[value]
        except (KeyError, TypeError) as exc:
            if cell is None:
                raise RuntimeError("A required discriminator must have a cell") from exc
            choices = ", ".join(repr(choice) for choice in cls.__variants__)
            error = TableError.from_cell(
                f"Unknown variant {value!r}; expected one of: {choices}",
                cell,
                schema=cls,
                field=declared.label,
                item_id=item_id,
                code=TableErrorCode.UNKNOWN_VARIANT,
                hint="Use a discriminator value registered on this schema.",
            )
            error.__cause__ = exc
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
        errors: list[TableError] | None = None,
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
        applicable = {
            label
            for declared in record_cls.__fields__.values()
            for label in declared.labels
        }
        extras: dict[str, Any] = {}
        for label, cell in cells_by_label.items():
            if label in applicable or cell.value == "":
                continue
            if label not in cls._accepted_labels():
                continue
            if cls.inapplicable_fields == "preserve":
                extras[label] = cell.value
                continue
            error = TableError.from_cell(
                f"Field does not apply to variant {record_cls.__variant_value__!r}",
                cell,
                schema=record_cls,
                field=label,
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
            ) from exc

    @classmethod
    def _validate_error_mode(cls, error_mode: str) -> None:
        """Validate the public failure strategy before parsing begins.

        Args:
            error_mode: Public parser failure strategy.

        Raises:
            ValueError: If ``error_mode`` is not ``"first"`` or ``"collect"``.

        !!! warning
            This is an API misuse check rather than a table diagnostic, so it
            raises ``ValueError`` directly.

        """
        if error_mode not in {"first", "collect"}:
            raise ValueError("error_mode must be 'first' or 'collect'")

    @staticmethod
    def _report(
        error: TableError,
        errors: list[TableError] | None,
    ) -> object:
        """Raise immediately or append one recoverable diagnostic.

        Args:
            error: Structured diagnostic to report.
            errors: ``None`` for fail-fast mode or a list for collect mode.

        Returns:
            Internal invalid sentinel when the error is collected.

        Raises:
            TableError: In fail-fast mode.

        !!! info
            Returning a sentinel lets parsing continue safely while skipping
            only the invalid value or record.

        """
        if errors is None:
            raise error
        errors.append(error)
        return _INVALID

    @staticmethod
    def _raise_collected(errors: list[TableError] | None) -> None:
        """Raise the public aggregate after all safe validation has run.

        Args:
            errors: Optional collected diagnostic list.

        Raises:
            TableErrors: If ``errors`` contains one or more diagnostics.

        !!! warning
            Dependent lifecycle stages stop after collected structural errors
            so users do not receive noisy secondary failures.

        """
        if errors:
            raise TableErrors(errors)

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
        source_table = TableData.ensure(datatable)
        cls._check_table(source_table)

        try:
            transformed = cls.transform_table(source_table, parse_context)
        except TableError:
            raise
        except Exception as exc:
            raise TableError(
                f"Table transformation failed: {exc}",
                schema=cls,
                code=TableErrorCode.TRANSFORM_FAILED,
            ) from exc

        if not isinstance(transformed, TableData):
            raise TableError(
                "Table transformation must return TableData",
                schema=cls,
                code=TableErrorCode.INVALID_TRANSFORM,
            )

        cls._check_table(transformed)
        return transformed

    @classmethod
    def _validate_schema_labels(cls) -> None:
        """Validate canonical schema labels.

        Raises:
            TableError: If two fields on the same schema declare the same
                canonical label.

        !!! warning
            Alias collisions are rejected during class creation. This runtime
            check protects variant classes and late decorator registration.

        """
        labels: dict[str, str] = {}
        for name, declared in cls.__fields__.items():
            if declared.label in labels:
                raise TableError(
                    "Schema contains duplicate field labels",
                    schema=cls,
                    field=declared.label,
                )
            labels[declared.label] = name

    @classmethod
    def _value_for(
        cls,
        declared: Field,
        *,
        present: bool,
        cell: TableCell | None,
        parse_context: ParseContext,
        item_id: Any | None,
        errors: list[TableError] | None = None,
    ) -> Any:
        """Resolve one declared field from a present or missing cell.

        Args:
            declared: Field declaration being resolved.
            present: Whether any canonical label or alias appeared.
            cell: Source cell when the field is present.
            parse_context: Parse context for the current operation.
            item_id: Current record ID when available.
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
                        field=declared.label,
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
                    field_label=declared.label,
                    item_id=item_id,
                    user_data=parse_context.user_data,
                )
                try:
                    factory = cast(
                        Callable[[DefaultContext], Any], declared.default_factory
                    )
                    return factory(factory_context)
                except Exception as exc:
                    error = TableError(
                        f"Default factory failed: {exc}",
                        schema=cls,
                        field=declared.label,
                        item_id=item_id,
                        code=TableErrorCode.DEFAULT_FACTORY_FAILED,
                    )
                    error.__cause__ = exc
                    return cls._report(
                        error,
                        errors,
                    )
            return None if declared.default is MISSING else declared.default

        if cell is None:
            raise RuntimeError("A present field must provide a TableCell")

        if cell.value == "":
            if declared.required and not declared.parse_empty:
                return cls._report(
                    TableError.from_cell(
                        "Required field has an empty value",
                        cell,
                        schema=cls,
                        field=declared.label,
                        item_id=item_id,
                        code=TableErrorCode.EMPTY_REQUIRED,
                        hint=(
                            "Fill the cell, or remove required=True if an explicit "
                            "empty value should be valid."
                        ),
                    ),
                    errors,
                )
            if not declared.required and declared.empty == "none":
                return None
            if not declared.required and declared.empty == "error":
                return cls._report(
                    TableError.from_cell(
                        "Optional field has an empty value",
                        cell,
                        schema=cls,
                        field=declared.label,
                        item_id=item_id,
                        code=TableErrorCode.EMPTY_OPTIONAL,
                        hint=(
                            "Fill the cell, omit the field, or choose a different "
                            "empty-cell policy for this schema field."
                        ),
                    ),
                    errors,
                )
            if not declared.parse_empty:
                return ""

        if declared.parser is None:
            return cell.value

        cell_context = CellContext(
            schema=cls,
            field_name=declared.name,
            field_label=declared.label,
            row=cell.source_row,
            column=cell.source_column,
            item_id=item_id,
            source_value=cell.source_value,
            user_data=parse_context.user_data,
        )
        try:
            return declared.parser(cell.value, cell_context)
        except Exception as exc:
            error = TableError.from_cell(
                f"Field parser failed: {exc}",
                cell,
                schema=cls,
                field=declared.label,
                item_id=item_id,
                code=TableErrorCode.PARSER_FAILED,
                hint="Check the cell value or adjust the field parser for this syntax.",
            )
            error.__cause__ = exc
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
                code=TableErrorCode.TABLE_EMPTY,
                hint="Provide at least a header row with field labels.",
            )
        if not table.rows[0]:
            raise TableError(
                "Table header is empty",
                schema=cls,
                row=1,
                code=TableErrorCode.HEADER_EMPTY,
                hint="Provide field labels in the first row or first column.",
            )

    @classmethod
    def _reject_duplicates(
        cls,
        label_cells: Sequence[TableCell],
        errors: list[TableError] | None = None,
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
                        field=label,
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
        errors: list[TableError] | None = None,
    ) -> None:
        """Validate required fields when a table contains no records.

        Args:
            labels: Labels present in the table's label row or column.
            errors: Optional collection sink for recoverable diagnostics.

        Raises:
            TableError: In fail-fast mode when a required field is absent.

        !!! info
            Normal record parsing reports missing required fields per record.
            This helper handles empty data tables where no record loop runs.

        """
        present = set(labels)
        for declared in cls.__fields__.values():
            if declared.required and not present.intersection(declared.labels):
                cls._report(
                    TableError(
                        "Required field is missing from the table",
                        schema=cls,
                        field=declared.label,
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
        errors: list[TableError] | None = None,
        parsed_values: Mapping[str, Any] | None = None,
        parsed_sources: Mapping[str, TableCell] | None = None,
    ) -> tuple[bool, dict[str, Any], dict[str, TableCell], Any | None]:
        """Parse applicable fields for one record schema."""
        values = dict(parsed_values or {})
        source_cells = dict(parsed_sources or {})
        record_item_id = item_id
        valid_record = True

        for name, declared in record_cls.__fields__.items():
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
        )
        return cast(BaseTable, cls._from_values(values, source=source, extras=extras))

    @classmethod
    def _finalize_records(
        cls,
        records: list[BaseTable],
        parse_context: ParseContext,
        errors: list[TableError] | None = None,
        *,
        convert_output: bool = True,
    ) -> list[Any]:
        """Run reference resolution, validation, and output conversion.

        Args:
            records: Parsed schema records.
            parse_context: Parse context for the current operation.
            errors: Optional collection sink for recoverable diagnostics.
            convert_output: Whether to call output builders.

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

        references_valid = True
        try:
            cls._resolve_references(records, parse_context)
        except TableError as exc:
            cls._report(exc, errors)
            references_valid = False

        for record in records if references_valid else ():
            source = record.table_source
            record_cls = type(record)
            try:
                record.validate_record(parse_context)
            except TableError as exc:
                if errors is None:
                    raise
                errors.append(exc)
            except Exception as exc:
                error = TableError(
                    f"Record validation failed: {exc}",
                    schema=record_cls,
                    row=source.row,
                    column=source.column,
                    item_id=source.item_id,
                    code=TableErrorCode.RECORD_VALIDATION_FAILED,
                )
                error.__cause__ = exc
                cls._report(
                    error,
                    errors,
                )

        if references_valid:
            try:
                cls.validate_records(records, parse_context)
            except TableError as exc:
                cls._report(exc, errors)
            except Exception as exc:
                error = TableError(
                    f"Table validation failed: {exc}",
                    schema=cls,
                    code=TableErrorCode.TABLE_VALIDATION_FAILED,
                )
                error.__cause__ = exc
                cls._report(
                    error,
                    errors,
                )

        cls._raise_collected(errors)

        if not convert_output:
            return records

        converted = []
        for record in records:
            source = record.table_source
            record_cls = type(record)
            try:
                converted.append(record_cls.build_output(record, parse_context))
            except Exception as exc:
                target = record_cls.output_model or record_cls.build_output
                target_name = getattr(target, "__name__", repr(target))
                subject = (
                    "Output model" if record_cls.output_model else "Output builder"
                )
                error = TableError(
                    f"{subject} {target_name} rejected the record: {exc}",
                    schema=record_cls,
                    row=source.row,
                    column=source.column,
                    item_id=source.item_id,
                    code=TableErrorCode.OUTPUT_FAILED,
                )
                error.__cause__ = exc
                cls._report(error, errors)
        cls._raise_collected(errors)
        return converted

    @classmethod
    def _resolve_references(
        cls,
        records: list[BaseTable],
        parse_context: ParseContext,
    ) -> None:
        """Resolve declared local references against records from this table.

        Args:
            records: Parsed records from one table.
            parse_context: Parse context for the current operation.

        Raises:
            TableError: If reference targets are missing, duplicate, or
                cannot be converted to the target key type.

        !!! info
            References are local to one parsed table. They do not query
            external registries or previously parsed feature data.

        """
        records_with_references = [
            record
            for record in records
            if any(
                declared.reference is not None
                for declared in type(record).__fields__.values()
            )
        ]
        if not records_with_references:
            return

        indexes: dict[str, dict[Any, BaseTable]] = {}
        for source_record in records_with_references:
            for declared in type(source_record).__fields__.values():
                spec = declared.reference
                if spec is None or spec.target in indexes:
                    continue
                index: dict[Any, BaseTable] = {}
                for record in records:
                    if spec.target not in type(record).__fields__:
                        continue
                    target_value = getattr(record, spec.target)
                    if target_value in index:
                        target_declared = type(record).__fields__[spec.target]
                        cell = record.source_for(spec.target)
                        raise TableError.from_cell(
                            f"Reference target {target_value!r} is not unique",
                            cell,
                            schema=type(record),
                            field=target_declared.label,
                            code=TableErrorCode.REFERENCE_FAILED,
                        )
                    index[target_value] = record
                if not index:
                    raise TableError(
                        f"Reference target field {spec.target!r} is not declared",
                        schema=type(source_record),
                        field=declared.label,
                        code=TableErrorCode.REFERENCE_FAILED,
                    )
                indexes[spec.target] = index

        for record in records:
            for name, declared in type(record).__fields__.items():
                spec = declared.reference
                if spec is None:
                    continue
                raw = getattr(record, name)
                if raw in (None, ""):
                    setattr(record, name, [] if spec.many else None)
                    continue
                keys = (
                    [part.strip() for part in str(raw).split(spec.separator)]
                    if spec.many
                    else [raw]
                )
                resolved = []
                for key in keys:
                    key = cls._parse_reference_key(
                        key,
                        target_field=next(
                            type(candidate).__fields__[spec.target]
                            for candidate in records
                            if spec.target in type(candidate).__fields__
                        ),
                        source_record=record,
                        source_field=name,
                        parse_context=parse_context,
                    )
                    try:
                        resolved.append(indexes[spec.target][key])
                    except KeyError as exc:
                        cell = record.source_for(name)
                        raise TableError.from_cell(
                            f"Reference target {key!r} was not found",
                            cell,
                            schema=cls,
                            field=declared.label,
                            item_id=record.table_source.item_id,
                            code=TableErrorCode.REFERENCE_FAILED,
                        ) from exc
                setattr(record, name, resolved if spec.many else resolved[0])

    @classmethod
    def _parse_reference_key(
        cls,
        value: Any,
        *,
        target_field: Field,
        source_record: BaseTable,
        source_field: str,
        parse_context: ParseContext,
    ) -> Any:
        """Apply the target field parser so typed IDs and references match.

        Args:
            value: Raw reference key value.
            target_field: Referenced field declaration.
            source_record: Record containing the reference cell.
            source_field: Name of the reference field on ``source_record``.
            parse_context: Parse context for the current operation.

        Returns:
            Reference key converted with the target field parser, or the raw
            key when the target field has no parser.

        Raises:
            TableError: If target-key conversion fails.

        !!! warning
            The source cell for the reference field is used in diagnostics, not
            the target field cell, because that is where the bad key was
            written.

        """
        if target_field.parser is None:
            return value
        source_cell = source_record.source_for(source_field)
        cell_context = CellContext(
            schema=type(source_record),
            field_name=source_field,
            field_label=type(source_record).__fields__[source_field].label,
            row=source_cell.source_row,
            column=source_cell.source_column,
            item_id=source_record.table_source.item_id,
            source_value=source_cell.source_value,
            user_data=parse_context.user_data,
        )
        try:
            return target_field.parser(value, cell_context)
        except Exception as exc:
            raise TableError.from_cell(
                f"Reference key conversion failed: {exc}",
                source_cell,
                schema=type(source_record),
                field=type(source_record).__fields__[source_field].label,
                item_id=source_record.table_source.item_id,
                code=TableErrorCode.REFERENCE_FAILED,
            ) from exc


class RowTable(BaseTable):
    """Parse tables whose first row contains labels and later rows are records.

    !!! example
        ```python
        class UserTable(RowTable):
            name = field("name", required=True)

        users = UserTable.parse([["name"], ["Alice"]])
        ```
    """

    @classmethod
    def parse(
        cls,
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]:
        """Parse a row-oriented table into validated records or outputs.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Public output objects, including output-model conversion when
            configured.

        !!! info
            The first row supplies labels. Each following row is parsed as one
            record using those labels.

        """
        return cls._parse_row_table(
            datatable,
            context=context,
            error_mode=error_mode,
            convert_output=True,
        )

    @classmethod
    def parse_records(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a row-oriented table and return schema record instances.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of the schema class.

        !!! warning
            Output-model conversion is skipped so callers can inspect record
            source metadata and schema attributes directly.

        """
        return cast(
            list[TableT],
            cast(Any, cls)._parse_row_table(
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=False,
            ),
        )

    @classmethod
    def _parse_row_table(
        cls,
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None,
        error_mode: str,
        convert_output: bool,
    ) -> list[Any]:
        """Parse row-oriented records and optionally build output objects.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.
            convert_output: Whether to run output builders after validation.

        Returns:
            Parsed records or converted output objects.

        Raises:
            TableError: In fail-fast mode for structural, parsing, or
                lifecycle failures.
            TableErrors: In collect mode when recoverable diagnostics were
                collected.

        !!! warning
            Ragged rows are reported with the row's original source location,
            then skipped in collect mode so independent rows can still be
            checked.

        """
        cls._validate_error_mode(error_mode)
        errors: list[TableError] | None = [] if error_mode == "collect" else None
        parse_context = cls._parse_context(context)
        table = cls._prepare_table(datatable, parse_context)
        cls._validate_variant_configuration()
        header_cells = table.rows[0]
        headers = [cell.value for cell in header_cells]
        cls._reject_duplicates(header_cells, errors)
        cls._validate_table_labels(header_cells, errors)
        if len(table.rows) == 1:
            cls._validate_required_presence(headers, errors)
        id_fields = [
            (name, declared)
            for name, declared in cls.__fields__.items()
            if declared.is_id
        ]
        preparse_id = len(id_fields) == 1
        records: list[BaseTable] = []
        for row_number, row_cells in enumerate(table.rows[1:], start=2):
            if len(row_cells) != len(headers):
                source_row = row_cells[0].source_row if row_cells else row_number
                cls._report(
                    TableError(
                        f"Ragged row: expected {len(headers)} cells, "
                        f"got {len(row_cells)}",
                        schema=cls,
                        row=source_row,
                        code=TableErrorCode.RAGGED_ROW,
                        hint=(
                            "Make every data row contain the same number of cells "
                            "as the header row."
                        ),
                    ),
                    errors,
                )
                continue

            item_id = None
            cells_by_label = dict(zip(headers, row_cells, strict=True))
            parsed_values: dict[str, Any] = {}
            parsed_sources: dict[str, TableCell] = {}
            if preparse_id:
                id_name, id_declared = id_fields[0]
                id_cell = cls._cell_for_field(id_declared, cells_by_label)
                item_id = cls._value_for(
                    id_declared,
                    present=id_cell is not None,
                    cell=id_cell,
                    parse_context=parse_context,
                    item_id=id_cell.value if id_cell is not None else None,
                    errors=errors,
                )
                if item_id is _INVALID:
                    continue
                parsed_values[id_name] = item_id
                if id_cell is not None:
                    parsed_sources[id_name] = id_cell

            record_cls, parsed_selector = cls._select_record_schema(
                cells_by_label,
                parse_context=parse_context,
                item_id=item_id,
                errors=errors,
            )
            if record_cls is None:
                continue
            extras = cls._reject_inapplicable_values(
                record_cls,
                cells_by_label,
                item_id=item_id,
                errors=errors,
            )
            parsed_values.update(parsed_selector)
            valid_record, values, source_cells, item_id = cls._parse_record_values(
                record_cls,
                cells_by_label,
                parse_context=parse_context,
                item_id=item_id,
                errors=errors,
                parsed_values=parsed_values,
                parsed_sources=parsed_sources,
            )
            if not valid_record:
                continue
            records.append(
                record_cls._record_from_values(
                    values,
                    cells=source_cells,
                    row=row_cells[0].source_row if row_cells else row_number,
                    item_id=item_id,
                    extras=extras,
                )
            )
        return cls._finalize_records(
            records,
            parse_context,
            errors,
            convert_output=convert_output,
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

    @classmethod
    def parse(
        cls,
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[Any]:
        """Parse a column-oriented table into validated records or outputs.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Public output objects, including output-model conversion when
            configured.

        !!! info
            The first column supplies labels. Each following column is parsed
            as one record.

        """
        return cls._parse_column_table(
            datatable,
            context=context,
            error_mode=error_mode,
            convert_output=True,
        )

    @classmethod
    def parse_records(
        cls: type[TableT],
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None = None,
        error_mode: str = "first",
    ) -> list[TableT]:
        """Parse a column-oriented table and return schema record instances.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.

        Returns:
            Validated instances of the schema class.

        !!! warning
            Output-model conversion is skipped so callers can inspect source
            metadata, item IDs, and intermediate schema attributes directly.

        """
        return cast(
            list[TableT],
            cast(Any, cls)._parse_column_table(
                datatable,
                context=context,
                error_mode=error_mode,
                convert_output=False,
            ),
        )

    @classmethod
    def _parse_column_table(
        cls,
        datatable: RawTable | TableData,
        *,
        context: Mapping[str, Any] | ParseContext | None,
        error_mode: str,
        convert_output: bool,
    ) -> list[Any]:
        """Parse column-oriented records and optionally build output objects.

        Args:
            datatable: Raw rows or source-aware ``TableData``.
            context: Optional project data or existing parse context.
            error_mode: ``"first"`` or ``"collect"``.
            convert_output: Whether to run output builders after validation.

        Returns:
            Parsed records or converted output objects.

        Raises:
            TableError: For structural, ID, parsing, or lifecycle failures.
            TableErrors: In collect mode when recoverable diagnostics were
                collected.

        !!! warning
            ``ColumnTable`` requires exactly one ``id_field``. The first row's
            first cell must use that field's label or alias.

        """
        cls._validate_error_mode(error_mode)
        errors: list[TableError] | None = [] if error_mode == "collect" else None
        parse_context = cls._parse_context(context)
        table = cls._prepare_table(datatable, parse_context)
        cls._validate_variant_configuration()
        id_fields = [field for field in cls.__fields__.values() if field.is_id]
        if len(id_fields) != 1:
            raise TableError(
                "ColumnTable schemas require exactly one id_field",
                schema=cls,
                hint="Declare exactly one field with id_field(...).",
            )
        id_declared = id_fields[0]

        width = len(table.rows[0])
        id_label_cell = table.rows[0][0]
        if id_label_cell.value not in id_declared.labels:
            raise TableError.from_cell(
                "The first row must be the declared id field",
                id_label_cell,
                schema=cls,
                field=id_declared.label,
                hint="Move the declared id_field label into the first cell.",
            )
        for row_number, row_cells in enumerate(table.rows, start=1):
            if len(row_cells) != width:
                source_row = row_cells[0].source_row if row_cells else row_number
                cls._report(
                    TableError(
                        f"Ragged row: expected {width} cells, got {len(row_cells)}",
                        schema=cls,
                        row=source_row,
                        code=TableErrorCode.RAGGED_ROW,
                        hint=(
                            "Make every table row contain the same number of cells "
                            "as the ID row."
                        ),
                    ),
                    errors,
                )
        cls._raise_collected(errors)

        label_cells = [row[0] for row in table.rows]
        labels = [cell.value for cell in label_cells]
        cls._reject_duplicates(label_cells, errors)
        cls._validate_table_labels(label_cells, errors)
        if width == 1:
            cls._validate_required_presence(labels, errors)
        records: list[BaseTable] = []
        seen_ids = set()
        for column_index in range(1, width):
            id_cell = table.rows[0][column_index]
            item_id = cls._value_for(
                id_declared,
                present=True,
                cell=id_cell,
                parse_context=parse_context,
                item_id=id_cell.value or None,
                errors=errors,
            )
            if item_id is _INVALID:
                continue
            if item_id in seen_ids:
                cls._report(
                    TableError.from_cell(
                        "Duplicate item ID",
                        id_cell,
                        schema=cls,
                        field=id_declared.label,
                        item_id=item_id,
                        code=TableErrorCode.DUPLICATE_ID,
                        hint="Use one unique item ID per parsed column.",
                    ),
                    errors,
                )
                continue
            seen_ids.add(item_id)

            cells_by_label = {
                label: table.rows[row_index][column_index]
                for row_index, label in enumerate(labels)
            }
            record_cls, parsed_selector = cls._select_record_schema(
                cells_by_label,
                parse_context=parse_context,
                item_id=item_id,
                errors=errors,
            )
            if record_cls is None:
                continue
            extras = cls._reject_inapplicable_values(
                record_cls,
                cells_by_label,
                item_id=item_id,
                errors=errors,
            )
            id_name = id_declared.name
            parsed_values = {id_name: item_id, **parsed_selector}
            parsed_sources = {id_name: id_cell}
            valid_record, values, source_cells, item_id = cls._parse_record_values(
                record_cls,
                cells_by_label,
                parse_context=parse_context,
                item_id=item_id,
                errors=errors,
                parsed_values=parsed_values,
                parsed_sources=parsed_sources,
            )
            if not valid_record:
                continue
            records.append(
                record_cls._record_from_values(
                    values,
                    cells=source_cells,
                    column=id_cell.source_column,
                    item_id=item_id,
                    extras=extras,
                )
            )
        return cls._finalize_records(
            records,
            parse_context,
            errors,
            convert_output=convert_output,
        )
