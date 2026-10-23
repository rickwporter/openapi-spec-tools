# openapi-spec-tools Tools

This directory contains a collection of items which can be used in local development.
These tools are NOT part of the main project, but included for reference and use.

Here's a quick breakdown of what is here:
* `toml.py` - used for keeping sub-project `pyproject.toml` and `uv.lock` files in agreement
* `client/` - sample project, primarily Makefile, for using the OpenAPI generator to generate client code
* `pets_server/` - project to create FastAPI server which can be used to test code in `examples/pets-cli/`
