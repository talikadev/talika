# --8<-- [start:row-table]
Given the users exist
  | name  | role   | active |
  | Asha  | admin  | yes    |
  | Bruno | editor | no     |
# --8<-- [end:row-table]

# --8<-- [start:column-table]
Given the content exists
  | IDs      | article-1        | poll-1        |
  | Type     | Article          | Poll          |
  | Headline | Release notes    | Choose a plan |
  | Status   | draft            | published     |
# --8<-- [end:column-table]

# --8<-- [start:wide-row]
Given the content exists
  | id        | type    | headline      | body       | options       | status    |
  | article-1 | Article | Release notes | Many words |               | draft     |
  | poll-1    | Poll    | Choose a plan |            | Basic, Pro    | published |
# --8<-- [end:wide-row]

# --8<-- [start:column-contract]
from talika import ColumnTable, field, id_field


class ContentTable(ColumnTable):
    id = id_field("IDs")
    content_type = field("Type", required=True)
    headline = field("Headline", required=True)
    status = field("Status", required=True)
# --8<-- [end:column-contract]
