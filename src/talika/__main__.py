"""Module entry point for ``python -m talika``.

Running the package as a module delegates to the same CLI entry point as the
``talika`` console script.

!!! example
    ```bash
    python -m talika describe tests/support/schemas.py:UserTable
    ```
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
