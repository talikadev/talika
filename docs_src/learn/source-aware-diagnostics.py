# --8<-- [start:bad-table]
Given the users exist
  | name | age | active |
  | Mira | old | maybe  |
# --8<-- [end:bad-table]

# --8<-- [start:error]
Field parser failed: invalid literal for int() with base 10: 'old'
(code=parser_failed, schema=UserTable, field='age', row=2, column=2, value='old').
Hint: Check the cell value or adjust the field parser for this syntax.
# --8<-- [end:error]

# --8<-- [start:collected]
Table contains 2 errors:
  1. Field parser failed: invalid literal for int() with base 10: 'old' (code=parser_failed, schema=UserTable, field='age', row=2, column=2, value='old').
  2. Field parser failed: Expected one of ['0', '1', 'false', 'no', 'off', 'on', 'true', 'yes'] (code=parser_failed, schema=UserTable, field='active', row=2, column=3, value='maybe').
# --8<-- [end:collected]
