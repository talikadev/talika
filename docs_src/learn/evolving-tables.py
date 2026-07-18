# --8<-- [start:old-table]
Given the users exist
  | Full name | age |
  | Mira Rao  | 34  |
# --8<-- [end:old-table]

# --8<-- [start:new-table]
Given the users exist
  | name     | age | active |
  | Mira Rao | 34  | true   |
# --8<-- [end:new-table]

# --8<-- [start:contract]
from talika import RowTable, boolean, field


class UserTable(RowTable):
    name = field("name", aliases=("Full name",), required=True)
    age: int = field("age", required=True)
    active = field("active", parser=boolean(), default=True)
# --8<-- [end:contract]

# --8<-- [start:preserve]
from talika import ColumnTable, TableFields, discriminator, field, id_field


class ArticleFields(TableFields):
    body = field("Body")


class PollFields(TableFields):
    options = field("Options")


class LegacyContentTable(ColumnTable):
    inapplicable_fields = "preserve"

    id = id_field("IDs")
    content_type = discriminator(
        "Type",
        variants={"Article": ArticleFields, "Poll": PollFields},
    )
# --8<-- [end:preserve]
