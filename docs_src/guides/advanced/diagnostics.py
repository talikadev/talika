# --8<-- [start:feature-users]
Given the users exist
  | name  | Age |
  | Alice | bad |
# --8<-- [end:feature-users]

# --8<-- [start:schema]
from talika import RowTable, field, integer


class UserTable(RowTable):
    name = field("name", required=True)
    age = field("Age", parser=integer())
# --8<-- [end:schema]

# --8<-- [start:datatable]
datatable = [
    ["name", "Age"],
    ["Alice", "bad"],
]
# --8<-- [end:datatable]

# --8<-- [start:raising-api]
records = UserTable.parse(datatable)
# --8<-- [end:raising-api]

# --8<-- [start:validate-api]
result = UserTable.validate(datatable)

if result.valid:
    records = result.records
else:
    for diagnostic in result.errors:
        print(diagnostic.code, diagnostic.row, diagnostic.column)
# --8<-- [end:validate-api]

# --8<-- [start:validation-output]
>> result.valid
False

>> result.records
()

>> [(error.code, error.row, error.column) for error in result.errors]
[('parser_failed', 2, 2)]
# --8<-- [end:validation-output]

# --8<-- [start:functional-api]
from talika import validate_table


result = validate_table(
    UserTable,
    datatable,
    context={"locale": "en"},
)

# Inside a pytest-bdd step, the talika fixture offers the same operation:
result = talika.validate(
    datatable,
    schema=UserTable,
    context={"locale": "en"},
)
# --8<-- [end:functional-api]

# --8<-- [start:invalid-result]
result = UserTable.validate(
    [["name", "Age"], ["Alice", "bad"]]
)

assert not result.valid
assert result.records == ()
assert result.errors[0].code == "parser_failed"
# --8<-- [end:invalid-result]

# --8<-- [start:warning-schema]
from talika import DiagnosticSeverity, TableError


class ReviewTable(RowTable):
    name = field("name", required=True)

    def validate_record(self, context):
        if self.name == "legacy":
            raise TableError(
                "Replace the legacy display name when practical",
                code="legacy_name",
                severity=DiagnosticSeverity.WARNING,
            )
# --8<-- [end:warning-schema]

# --8<-- [start:warning-validate]
warning_result = ReviewTable.validate(
    [["name"], ["legacy"]]
)
# --8<-- [end:warning-validate]

# --8<-- [start:warning-output]
>> warning_result.valid
True

>> [record.name for record in warning_result.records]
['legacy']

>> [warning.code for warning in warning_result.warnings]
['legacy_name']
# --8<-- [end:warning-output]

# --8<-- [start:inspect-diagnostic]
diagnostic = result.diagnostics[0]

details = {
    "version": diagnostic.diagnostic_version,
    "severity": diagnostic.severity.value,
    "code": diagnostic.code,
    "schema": diagnostic.schema_name,
    "field": diagnostic.field_name,
    "label": diagnostic.field_label,
    "location": (diagnostic.row, diagnostic.column),
    "source": diagnostic.source_value,
}
# --8<-- [end:inspect-diagnostic]

# --8<-- [start:diagnostic-output]
>> details
{'version': 1, 'severity': 'error', 'code': 'parser_failed', 'schema': 'UserTable', 'field': 'age', 'label': 'Age', 'location': (2, 2), 'source': 'bad'}
# --8<-- [end:diagnostic-output]

# --8<-- [start:presence-flags]
if diagnostic.has_source_value:
    print("authored:", diagnostic.source_value)
if diagnostic.has_logical_value:
    print("logical:", diagnostic.logical_value)
# --8<-- [end:presence-flags]

# --8<-- [start:project-diagnostic]
from talika import TableError


def project_code(value, context):
    if not value.startswith("USR-"):
        raise TableError(
            "User code must start with USR-",
            code="project_user_code",
            schema=context.schema,
            field_name=context.field_name,
            field_label=context.field_label,
            source_uri=context.source_uri,
            row=context.row,
            column=context.column,
            source_value=context.source_value,
        )
    return value


class ProjectUserTable(RowTable):
    code = field("Code", parser=project_code)
# --8<-- [end:project-diagnostic]
