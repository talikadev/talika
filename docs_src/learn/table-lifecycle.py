# --8<-- [start:source-table]
Given the content exists
  | IDs  | 1-3        |
  | Type | 3 Articles |
# --8<-- [end:source-table]

# --8<-- [start:logical-table]
[
    ["IDs", "1", "2", "3"],
    ["Type", "Article", "Article", "Article"],
]
# --8<-- [end:logical-table]

# --8<-- [start:lifecycle]
authored table text
  -> source-aware cells
  -> optional table transform
  -> shape and label checks
  -> field parsing
  -> records
  -> references and validation
  -> output objects
# --8<-- [end:lifecycle]

# --8<-- [start:contract]
from talika import ColumnGroupExpander, ColumnTable, NumericRange, PrefixRepeat
from talika import field, id_field


class ContentTable(ColumnTable):
    table_transformer = ColumnGroupExpander(
        key_row="IDs",
        range_rule=NumericRange("-"),
        repeat_rule=PrefixRepeat(" "),
    )

    id = id_field("IDs")
    content_type = field("Type", required=True)
# --8<-- [end:contract]
