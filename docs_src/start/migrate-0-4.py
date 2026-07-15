# --8<-- [start:typed-before]
class UserTable(RowTable):
    age: int = field("Age")
# --8<-- [end:typed-before]

# --8<-- [start:typed-after-required]
class UserTable(RowTable):
    age: int = field("Age", required=True)
# --8<-- [end:typed-after-required]

# --8<-- [start:typed-after-optional]
class UserTable(RowTable):
    age: int | None = field("Age", empty="none")
# --8<-- [end:typed-after-optional]

# --8<-- [start:output-before]
users = UserTable.parse(datatable)
records = UserTable.parse_records(datatable)
# --8<-- [end:output-before]

# --8<-- [start:output-after]
records = UserTable.parse(datatable)
users = UserTable.parse_as(datatable)
# --8<-- [end:output-after]

# --8<-- [start:explicit-output]
users = UserTable.parse_as(datatable, User)
# --8<-- [end:explicit-output]

# --8<-- [start:blank-before]
value = field(required=True, parser=optional(integer()))
# --8<-- [end:blank-before]

# --8<-- [start:blank-after]
value: int = field(required=True)
optional_value: int | None = field(empty="parse")
# --8<-- [end:blank-after]
