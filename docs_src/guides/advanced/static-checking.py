# --8<-- [start:feature]
Feature: Static checking

  Scenario: Invalid users
    Given the following checked users:
      | name  | age |
      |       | old |
# --8<-- [end:feature]

# --8<-- [start:schema]
from talika import RowTable, field


class CheckedUserTable(RowTable):
    name = field("name", required=True)
    age: int = field("age", required=True)
# --8<-- [end:schema]

# --8<-- [start:discover-api]
from talika import discover_feature_tables


tables = discover_feature_tables(
    "features/users.feature",
    step="the following checked users:",
)

feature_table = tables[0]
# --8<-- [end:discover-api]

# --8<-- [start:discover-output]
>> feature_table.table.to_rows()
[['name', 'age'], ['', 'old']]

>> (feature_table.feature, feature_table.scenario, feature_table.step)
('Static checking', 'Invalid users', 'the following checked users:')

>> (
...     feature_table.table.cell(2, 1).source_row,
...     feature_table.table.cell(2, 1).source_column,
... )
(6, 15)
# --8<-- [end:discover-output]

# --8<-- [start:check-api]
from talika import check_feature


diagnostics = check_feature(
    "features/users.feature",
    schema=CheckedUserTable,
    step="the following checked users:",
)
# --8<-- [end:check-api]

# --8<-- [start:check-output]
>> len(diagnostics)
2

>> [diagnostic.error.code for diagnostic in diagnostics]
['empty_required', 'parser_failed']

>> [(d.error.row, d.error.column, d.error.value) for d in diagnostics]
[(6, 15, ''), (6, 17, 'old')]
# --8<-- [end:check-output]

# --8<-- [start:object-types]
from talika import FeatureDiagnostic, FeatureTable


assert isinstance(feature_table, FeatureTable)
assert isinstance(diagnostics[0], FeatureDiagnostic)
# --8<-- [end:object-types]

# --8<-- [start:object-types-output]
>> type(feature_table).__name__
'FeatureTable'

>> type(diagnostics[0]).__name__
'FeatureDiagnostic'

>> (diagnostics[0].scenario, diagnostics[0].step, diagnostics[0].error.code)
('Invalid users', 'the following checked users:', 'empty_required')
# --8<-- [end:object-types-output]

# --8<-- [start:error-output]
Required field has an empty value (code=empty_required, schema=CheckedUserTable, field='name', row=6, column=15, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid.

Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=CheckedUserTable, field='age', row=6, column=17, value='old'). Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:error-output]

# --8<-- [start:cli-command]
$ talika check features/users.feature \
>>   --schema app.schemas:CheckedUserTable \
>>   --step "the following checked users:"
# --8<-- [end:cli-command]

# --8<-- [start:cli-output]
features/users.feature:6:15: empty_required: Required field has an empty value (code=empty_required, schema=CheckedUserTable, field='name', row=6, column=15, value=''). Hint: Fill the cell, or remove required=True if an explicit empty value should be valid. [scenario='Invalid users']
features/users.feature:6:17: parser_failed: Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=CheckedUserTable, field='age', row=6, column=17, value='old'). Hint: Check the cell value or adjust the field parser for this syntax. [scenario='Invalid users']
Found 2 table error(s) in 1 table(s).
# --8<-- [end:cli-output]

# --8<-- [start:json-command]
$ talika check features/users.feature \
>>   --schema app.schemas:CheckedUserTable \
>>   --step "the following checked users:" \
>>   --format json
# --8<-- [end:json-command]

# --8<-- [start:json-output]
{
  "diagnostics": [
    {
      "code": "empty_required",
      "column": 15,
      "diagnostic_version": 1,
      "feature": "Static checking",
      "field": "name",
      "field_label": "name",
      "field_name": "name",
      "has_item_id": false,
      "has_logical_value": true,
      "has_source_value": true,
      "hint": "Fill the cell, or remove required=True if an explicit empty value should be valid.",
      "item_id": null,
      "logical_value": "",
      "message": "Required field has an empty value",
      "path": "features/users.feature",
      "row": 6,
      "scenario": "Invalid users",
      "schema": "CheckedUserTable",
      "schema_name": "CheckedUserTable",
      "severity": "error",
      "source_uri": "file:///project/features/users.feature",
      "source_value": "",
      "step": "the following checked users:",
      "value": ""
    },
    {
      "code": "parser_failed",
      "column": 17,
      "diagnostic_version": 1,
      "feature": "Static checking",
      "field": "age",
      "field_label": "age",
      "field_name": "age",
      "has_item_id": false,
      "has_logical_value": true,
      "has_source_value": true,
      "hint": "Check the cell value or adjust the field parser for this syntax.",
      "item_id": null,
      "logical_value": "old",
      "message": "Field parser failed: invalid literal for int() with base 10: 'old'",
      "path": "features/users.feature",
      "row": 6,
      "scenario": "Invalid users",
      "schema": "CheckedUserTable",
      "schema_name": "CheckedUserTable",
      "severity": "error",
      "source_uri": "file:///project/features/users.feature",
      "source_value": "old",
      "step": "the following checked users:",
      "value": "old"
    }
  ],
  "error_count": 2,
  "format_version": 1,
  "matched_tables": 1,
  "status": "failed",
  "warning_count": 0
}
# --8<-- [end:json-output]

# --8<-- [start:context-factory]
def checking_context():
    return {
        "allowed_roles": {"Admin", "Editor", "Viewer"},
        "strict": True,
    }
# --8<-- [end:context-factory]

# --8<-- [start:context-command]
$ talika check features/users.feature \
>>   --schema app.schemas:CheckedUserTable \
>>   --context-factory app.schemas:checking_context
# --8<-- [end:context-command]

# --8<-- [start:no-match-output]
No matching Gherkin data tables were found.
# --8<-- [end:no-match-output]
