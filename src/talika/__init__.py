"""Public API for talika.

The package exports the schema, parser, transformation, context, diagnostic,
introspection, pytest, and CLI-checking helpers intended for normal project use.
Top-level exports include both everyday helpers and advanced extension objects
so projects can build custom parsers, transformers, and diagnostics without
depending on private module paths.

!!! info
    Install optional extras only for integrations you use. Core schema parsing
    has no runtime dependencies beyond the Python standard library.
"""

from importlib.metadata import PackageNotFoundError, version

from .checker import (
    FeatureDiagnostic,
    FeatureTable,
    check_feature,
    discover_feature_tables,
)
from .context import CellContext, DefaultContext, ParseContext
from .dsl import CellDSL, CellDSLChain, compose_cell_dsls
from .errors import (
    SchemaDefinitionError,
    TableError,
    TableErrorCode,
    TableErrors,
)
from .fields import (
    Field,
    ReferenceSpec,
    discriminator,
    discriminator_field,
    field,
    id_field,
    reference,
)
from .group_expansion import (
    AlphabeticRange,
    ColumnGroupExpander,
    NumericRange,
    PrefixRepeat,
    RangeRule,
    RepeatRule,
    SuffixRepeat,
)
from .introspection import FieldContract, TableContract, VariantContract
from .parsers import (
    boolean,
    choice,
    compose,
    decimal,
    each,
    floating,
    integer,
    map_value,
    optional,
    split,
    string,
)
from .parsing import parse_table, parse_table_records
from .schema import ColumnTable, RowTable, TableFields
from .sources import RecordSource
from .table import TableCell, TableData
from .transformers import (
    TableTransformer,
    TransformerPipeline,
    compose_transformers,
)

try:
    __version__ = version("talika")
except PackageNotFoundError:
    __version__ = "0.1.1"

__all__ = [
    "TableError",
    "TableErrorCode",
    "TableErrors",
    "AlphabeticRange",
    "CellDSL",
    "CellDSLChain",
    "CellContext",
    "ColumnTable",
    "ColumnGroupExpander",
    "Field",
    "FeatureDiagnostic",
    "FeatureTable",
    "FieldContract",
    "DefaultContext",
    "ParseContext",
    "NumericRange",
    "PrefixRepeat",
    "RangeRule",
    "RepeatRule",
    "RecordSource",
    "ReferenceSpec",
    "RowTable",
    "TableCell",
    "TableContract",
    "TableData",
    "TableFields",
    "TableTransformer",
    "TransformerPipeline",
    "VariantContract",
    "SchemaDefinitionError",
    "SuffixRepeat",
    "__version__",
    "field",
    "boolean",
    "choice",
    "compose",
    "compose_cell_dsls",
    "compose_transformers",
    "decimal",
    "discriminator",
    "discriminator_field",
    "each",
    "floating",
    "id_field",
    "integer",
    "map_value",
    "optional",
    "parse_table",
    "parse_table_records",
    "reference",
    "check_feature",
    "discover_feature_tables",
    "split",
    "string",
]
