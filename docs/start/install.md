---
icon: lucide/package
tags:
  - Installation
  - Python
  - pip
  - uv
  - Optional dependencies
---

# Installation

Talika supports Python 3.10 and newer.

The normal install is intentionally small. Core Talika has no runtime
dependencies, so you can use schemas, parsers, validation, Custom DSL, table
transforms, and source-aware errors without pulling in a larger test stack.

We recommend `uv` for new projects. It is fast, creates virtual environments
easily, and keeps dependency changes explicit in your project. If your project
already uses `pip` and `venv`, Talika works there too.

## Virtual Environment

Install Talika inside a virtual environment so your test dependencies stay
separate from your system Python.

Use the `uv` tab if you are starting fresh. Use the `pip` tab if that matches
the rest of your project.


=== ":uv-logo:&nbsp;uv&nbsp;"
    ```bash { .talika-terminal title="Create env with uv" .speed-3}
    $ uv venv

    # Activate the environment:

    For windows
    >> .venv\Scripts\activate.ps1

    For Mac|Linux
    $ source .venv/bin/activate
    ```

=== ":python-pylogo: pip"
    ```bash  { .talika-terminal title="Create env with venv" .speed-3}
    $ python -m venv .venv
        
    # Activate the environment:

    For windows
    >> .venv\Scripts\activate.ps1

    For Mac|Linux
    $ source .venv/bin/activate

    ```

<!-- Then, activate the environment:

=== ":fontawesome-brands-windows:&nbsp;Windows"
    ```bash  { .talika-terminal title="Powershell Activate" .speed-3}
    >> .venv\Scripts\activate.ps1
    ```
=== ":material-apple:&nbsp;macOS&nbsp;&nbsp;|&nbsp;&nbsp;:material-linux: Linux"
    ```bash  { .talika-terminal title="Source Activate" .speed-3}
    $ source .venv/bin/activate
    ``` -->


## Install Talika

For most users, start with the core package.

You can add optional extras later when you need CLI checks or Pydantic output.

=== ":uv-logo:&nbsp;uv&nbsp;"
    ```bash { .talika-terminal title="Install Talika with uv" .speed-3}
    $ uv add talika
    ```

=== ":python-pylogo: pip"
    ```bash  { .talika-terminal title="Install Talika with pip" .speed-3}
    $ pip install talika
    ```

## Optional extras

Install only the integrations you use. The extras are separate so the core
library can stay dependency-free.


=== ":uv-logo:&nbsp;uv&nbsp;"
    ```bash { .talika-terminal title="Install Optional extras with uv" .speed-3}

    $ uv add talika[cli]

    Use this when you want to check `.feature` files without running the full test
    suite. It installs the official Gherkin parser used by `talika check` and
    feature-file discovery.

    This is useful for CI, pre-commit checks, and editor tooling.


    $ uv add talika[pydantic]

    Use this when your schemas should return Pydantic v2 models through
    output_model.

    Talika still owns the table boundary: labels, cell parsing, source locations,
    and table validation. Pydantic owns the final model validation.


    $ uv add talika[test]      

    Use this when you want the dependencies needed for the package tests and
    runnable examples. It includes pytest, pytest-bdd, the CLI dependencies, and
    Pydantic.

    Most application projects do not need this extra unless they are contributing
    to Talika or running the example suite locally.

    ```


=== ":python-pylogo: pip"
    ```bash  { .talika-terminal title="Install Optional extras with pip" .speed-3}


    talika check and feature-file discovery

    Use this when you want to check `.feature` files without running the full test
    suite. It installs the official Gherkin parser used by `talika check` and
    feature-file discovery.


    This is useful for CI, pre-commit checks, and editor tooling.


    $ pip install talika[cli]

    Pydantic v2 output models
    $ pip install talika[pydantic]

    project test dependencies
    $ pip install talika[test] 
    ```

## Verify the install

After installation, import Talika from Python:

```bash { .talika-terminal .speed-3 title="Check Python Import" }
$ python -c "import talika; print(talika.__version__)"
```

If you installed the CLI extra, the command line interface is available as:


```bash { .talika-terminal .speed-3 title="Check CLI Entrypoints" }
$ talika --help
$ python -m talika --help
```

## What gets installed

Core parsing imports only the Python standard library. The official Gherkin
parser is loaded lazily by the CLI and checker APIs, so ordinary schema parsing
does not depend on it.

Use the CLI extra when you want to validate `.feature` files without running
pytest:

```bash { .talika-terminal .speed-3 title="Install CLI Extra" }
$ uv add talika[cli]
```

Use the Pydantic extra only when your parsed records should become Pydantic
models:

```bash { .talika-terminal .speed-3 title="Install Pydantic Extra" }
$ uv add talika[pydantic]
```

If you are unsure, install only `talika` first. You can add an extra later
without changing your schemas.

