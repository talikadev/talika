# --8<-- [start:literal-table]
Given the articles exist
  | headline        | body                                | publish_date |
  | random          | 20 words                            | today        |
  | Release summary | The release shipped successfully.   | 2026-07-03   |
# --8<-- [end:literal-table]

# --8<-- [start:compact-table]
Given the content exists
  | IDs  | 1-3        |
  | Type | 3 Articles |
# --8<-- [end:compact-table]

# --8<-- [start:expanded-meaning]
[
    {"id": "1", "type": "Article"},
    {"id": "2", "type": "Article"},
    {"id": "3", "type": "Article"},
]
# --8<-- [end:expanded-meaning]

# --8<-- [start:owner]
@cells.token("random", fields=("headline",))
def random_headline(context):
    return context.user_data["faker"].headline()
# --8<-- [end:owner]
