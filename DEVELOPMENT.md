# openapi-spec-tools Development

Thanks for thinking about contributing to the openapi-spec-tools project.

## Getting Started

There are many resources on cloning a repository, so that is not repeated here. 

This project uses Python as the programming language, and `poetry` for managing packages. Here are some steps to setup the virtual environment.

Create your virtual environment (using your chosen version of Python)
```terminal
% python3.9 -m venv .env
% source .env/bin/activate
(.env) % python -m pip install poetry
Collecting poetry
  Downloading poetry-2.1.3-py3-none-any.whl.metadata (7.1 kB)
Collecting build<2.0.0,>=1.2.1 (from poetry)
  Downloading build-1.2.2.post1-py3-none-any.whl.metadata (6.5 kB)
Collecting cachecontrol<0.15.0,>=0.14.0 (from cachecontrol[filecache]<0.15.0,>=0.14.0->poetry)
  Downloading cachecontrol-0.14.3-py3-none-any.whl.metadata (3.1 kB)

...

[notice] A new release of pip is available: 24.3.1 -> 25.1.1
[notice] To update, run: pip install --upgrade pip
(.env) %
```

Now, install the `openapi-spec-tools` package with all the dependencies (incinding the development tools).

```terminal
(.env) % make install
poetry install --with dev
Installing dependencies from lock file

Package operations: 15 installs, 0 updates, 0 removals

  - Installing mdurl (0.1.2)
  - Installing markdown-it-py (3.0.0)
  - Installing pygments (2.19.1)
  - Installing click (8.1.8)
  - Installing iniconfig (2.1.0)
  - Installing mypy-extensions (1.1.0)
  - Installing pathspec (0.12.1)
  - Installing pluggy (1.5.0)
  - Installing rich (13.9.4)
  - Installing black (24.10.0)
  - Installing coverage (7.8.0)
  - Installing pytest (8.3.5)
  - Installing pyyaml (6.0.2)
  - Installing ruff (0.9.10)
  - Installing typer (0.15.3)

Installing the current project: openapi-spec-tools (0.1.0)
(.env) % 
```

Now, your development environment is ready for coding and testing.

## Workflow Hints

The project has been setup with `make` as a driver for most commands a develop may want. The `make help` is intended to provide a quick reference for those commands. Close variants of many of these commands are used in the CI pipeline.

The `make` targets will likely change, but here's a snapshot of the help. 

```terminal
(.env) % make help
====================
 Available Commands
====================

Usage:
  make 
  help             This message

General
  all              Complete cycle: generate/lint/test everything
  clean            Remove build/test artifacts
  poetry-update    Update poetry in top-level, and then all examples (part of release)

Build
  wheel            Build the wheel file
  install          Install package(s) and development tools
  uncommitted      Check for uncommitted changes

Lint
  lint             Check code formatting
  delint           Fix formatting issues

Test
  test             Run unit tests (use TEST_TARGET to scope)
  cov              Run unit tests with code coverage measurments (use TEST_TARGET to scope)

Examples
  example          Complete cycle on all examples
  example-gen      Generate example code (no tests)
(.env) % 
```

The `make` command allows users to see the command that is run by design. This allows developers to run the `make` command and see what it is doing, so you can copy/modify the command if you want. The test commands have an overridable `TEST_TARGET` so you can do more focused testing. For example, if you only cared about measuring the `_console.py` test coverage, you could do something like:

```terminal
(.env) % TEST_TARGET=tests/cli_gen/test_console.py make cov
poetry run coverage run -m pytest -v tests/cli_gen/test_console.py
=============== test session starts ===============
platform darwin -- Python 3.9.21, pytest-8.3.5, pluggy-1.5.0 -- /Users/rick/temp/openapi-spec-tools/.env/bin/python
cachedir: .pytest_cache
rootdir: /Users/rick/temp/openapi-spec-tools
configfile: pyproject.toml
plugins: anyio-4.9.0
collected 4 items

tests/cli_gen/test_console.py::test_console_factory_width_arg PASSED                 [ 25%]
tests/cli_gen/test_console.py::test_console_factory_env_arg PASSED                   [ 50%]
tests/cli_gen/test_console.py::test_console_factory_pytest PASSED                    [ 75%]
tests/cli_gen/test_console.py::test_console_factory_unspecified PASSED               [100%]

================ 4 passed in 0.19s ================
poetry run coverage report -m
Name                            Stmts   Miss  Cover   Missing
-------------------------------------------------------------
openapi_spec_tools/__init__.py              10      0   100%
openapi_spec_tools/_typer.py                 7      7     0%   5-16
openapi_spec_tools/cli_gen/_console.py      14      0   100%
openapi_spec_tools/oas.py                  364    364     0%   2-634
openapi_spec_tools/types.py                 47      0   100%
openapi_spec_tools/utils.py                236    210    11%   18-19, 44-51, 60-69, 76-81, 88-90, 102-158, 167-182, 189-190, 198, 206-209, 216-224, 276-287, 294-308, 319-333, 339-357, 406-420, 435-495, 500-513
-------------------------------------------------------------
TOTAL                             678    581    14%
poetry run coverage html
Wrote HTML report to htmlcov/index.html
(.env) % 
```

## Formatting

The project uses Python's `ruff` for formatting. The `make delint` attempts to correct formatting violations, but does not fix everything. The CI pipeline has a `Lint` job that verifies you comply with the formatting the same way the `make lint` checks.

## Testing

Testing and test coverage are very important aspects to maintain a package that works. It is expected that any code changes will have corresponding test changes, and possibly new/updated test assets. The `make cov` should be available in your local environment to allow for measuring code coverage. When making changes, it is often desirable to run a more targeted test using the command directly (e.g. `poetry run pytest -vv --pdb tests/cli_gen/test_console.py -k unspecified`)

The files in `tests/assets/` are where all the YAML files (or others) should be put. The layout files should have a `layout_` prefix to distinguish them from the OpenAPI specifications.

## Submitting Code

The project has been setup with CI pipelines to help verify that coding and testing standards are adhered to. However, all the things that are done in the CI pipelines should be repeatable in a local development environment.

## Releasing

So far, the `openapi-spec-tools` version has been updated just prior to the release. When updating the version in `pyproject.toml`, the example projects need update, too! It is also a good time to udpate the project dependencies. After update the project version, run `make poetry-update` to update the main and example projects.

Creating a new release is done using the Releases page from GitHub. The best way to generate release notes is using the button to do so. Upon creating a new release, it is automatically published to PyPi for consumption by others.
