"""Static-typing smoke sample for the documented public API."""

from talika import (
    RowTable,
    TableContract,
    TableError,
    TableErrorCode,
    TableErrors,
    __version__,
    field,
    parse_table,
    parse_table_records,
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
version_text: str = __version__
name: str = records[0].name
functional_name: str = functional_records[0].name
table_error = TableError("Invalid table", code=TableErrorCode.TABLE_ERROR)
table_errors = TableErrors([table_error])
error_code: str = table_error.code
error_count: int = len(table_errors)
