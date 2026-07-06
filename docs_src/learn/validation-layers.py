# --8<-- [start:gherkin]
Given the users exist
  | name | age | email           | manager |
  | Mira | old | mira@example.io |         |
  |      | 29  | mira@example.io | unknown |
# --8<-- [end:gherkin]

# --8<-- [start:field-error]
Field parser failed: invalid literal for int() with base 10: 'old'
(code=parser_failed, field='age', row=2, column=2, value='old')
# --8<-- [end:field-error]

# --8<-- [start:required-error]
Required field has an empty value
(code=empty_required, field='name', row=3, column=1, value='')
# --8<-- [end:required-error]

# --8<-- [start:table-error]
Emails must be unique
(code=table_validation_failed, schema=UserTable)
# --8<-- [end:table-error]

# --8<-- [start:reference-error]
Reference target 'unknown' was not found
(code=reference_failed, field='manager', row=3, column=4, value='unknown')
# --8<-- [end:reference-error]
