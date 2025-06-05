# openapi-spec-tools

Welcome to OpenAPI specification (OAS) tools!

This is a collection of tools for using OpenAPI specifications. The OpenAPI community has a plethora of tools, and this is intended to supplement those. The tools here provide functionality that has not been readily available elsewhere.

## OAS

The `oas` script provides a tool for analyzing and modifying an OpenAPI spec. See [OAS.md](OAS.md) for more info.

## CLI Generation

The `cli-gen` tool allows users to create a user-friendly CLI using the OpenAPI spec and a layout file. The layout file provides the CLI structure and refers to the OpenAPI spec for details of operations.  [LAYOUT.md](LAYOUT.md) has more details about the layout file, and the [CLI_GEN.md](CLI_GEN.md) has more info about CLI generation.

See the examples in `examples/` for some more complete works.

## client.mk

The `client.mk` file is an example of a `Makefile` to invoke the [OpenAPI generator](https://github.com/OpenAPITools/openapi-generator) via a container. The file can be copied/modified to be invoked with an OpenAPI specfication (other than `openapi.yaml`) and a real package name. For a more complete list of generator options, look at the [OpenAPI generator usage documentation](https://openapi-generator.tech/docs/usage#generate).

## Contributing

The [DEVELOPMENT.md](DEVELOPMENT.md) has more information about getting setup as a developer.

The [TODO.md](TODO.md) has some ideas where this project can be improved and expanded -- please add your ideas here, or email Rick directly (rickwporter@gmail.com). 
