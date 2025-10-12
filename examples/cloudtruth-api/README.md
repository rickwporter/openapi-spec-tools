# CloudTruth API

This is an example project used to demonstrate different aspects of API code generation.

## Getting started

Sections below outline how this project was setup.

### Setup Python project

```shell
poetry init --name cloudtruth-api
```

This prompted for relevant information that gets added to the `pyproject.toml`. The dependencies were not done interactively, but were done as described here.

Add dependencies (e.g. `poetry add`) for the following that are needed at runtime:
* typer
* rich
* requests
* pyyaml

Add development dependencies (e.g. `poetry add --group dev`) for the following:
* ruff
* black
* openapi-spec-tools

The `openapi-spec-tools` was done using the path instead of the package name since it is a sub-project. If creating a standalone project, you should use the package name.

Copy the linting/formatting rules for checking the code from another `pyproject.toml`.

Add the `README.md` that was filled in later.

### Create Makefile

The `Makefile` is not necessary, but provides a common way of running commands across projects.
It captures the commands and arguments that avoid the need to remember for different projects.

### Generate Code

The scope was limited to avoid repetition that did not show differences in the generated APIs. Generally, you would want to generate the code for all API interfaces, so you would not need to generate the layout file and choose a start point.

1. Copy the OpenAPI spec (`ct.yaml`) into place.
2. Generate the suggested layout file (e.g. `poetry run layout suggest ct.yaml layout.yaml --prefix /api/v1`)
3. Generate the code using `make regen`

In this project, all three body types are put into the same Python package. This does result in some duplicate infrastructure, but keeps things modular.
