"""Static-typing smoke sample for the documented public API."""

from dataclasses import dataclass
from datetime import date as Date
from datetime import datetime as DateTime

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
    date,
    datetime,
    field,
    parse_table,
    parse_table_as,
    validate_table,
)


@dataclass
class User:
    name: str
    age: int


class UserTable(RowTable):
    name: str = field("name", required=True)
    age: int = field("age", required=True)


class EventTable(RowTable):
    event_date: Date = field("event date", required=True, parser=date())
    starts_at: DateTime = field("starts at", required=True, parser=datetime())


contract: TableContract = UserTable.describe()
records: list[UserTable] = UserTable.parse([["name", "age"], ["Alice", "30"]])
users: list[User] = UserTable.parse_as([["name", "age"], ["Alice", "30"]], User)
functional_records: list[UserTable] = parse_table(
    UserTable,
    [["name", "age"], ["Alice", "30"]],
)
functional_users: list[User] = parse_table_as(
    UserTable,
    [["name", "age"], ["Alice", "30"]],
    User,
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
event = EventTable.parse(
    [["event date", "starts at"], ["2026-07-18", "2026-07-18T14:30:45"]]
)[0]
event_date: Date = event.event_date
starts_at: DateTime = event.starts_at
