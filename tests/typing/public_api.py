"""Static-typing smoke sample for the documented public API."""

from talika import (
    Diagnostic,
    DiagnosticSeverity,
    RowTable,
    TableContract,
    TableError,
    TableErrorCode,
    TableErrors,
    ValidationResult,
    __version__,
    field,
    parse_table,
    parse_table_records,
    validate_table,
)


class UserTable(RowTable):
    name: str = field("name", required=True)
    age: int = field("age")


contract: TableContract = UserTable.describe()
users: list[object] = UserTable.parse([["name", "age"], ["Alice", "30"]])
records: list[UserTable] = UserTable.parse_records([["name", "age"], ["Alice", "30"]])
functional_users: list[object] = parse_table(
    UserTable,
    [["name", "age"], ["Alice", "30"]],
)
functional_records: list[UserTable] = parse_table_records(
    UserTable,
    [["name", "age"], ["Alice", "30"]],
)
validation: ValidationResult[UserTable] = UserTable.validate(
    [["name", "age"], ["Alice", "30"]]
)
functional_validation: ValidationResult[UserTable] = validate_table(
    UserTable,
    [["name", "age"], ["Alice", "30"]],
)
diagnostic = Diagnostic(
    code="example",
    message="Example diagnostic",
    severity=DiagnosticSeverity.WARNING,
    source_value=None,
)
diagnostic_data: dict[str, object] = diagnostic.as_dict()
has_source_value: bool = diagnostic.has_source_value
version_text: str = __version__
name: str = records[0].name
functional_name: str = functional_records[0].name
table_error = TableError("Invalid table", code=TableErrorCode.TABLE_ERROR)
table_errors = TableErrors([table_error])
error_code: str = table_error.code
error_count: int = len(table_errors)
