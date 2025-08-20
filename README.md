# openapi-spec-tools

This is a collection of tools for using OpenAPI specifications. The OpenAPI community has a plethora of tools, and this is intended to supplement those. The tools here provide functionality that has not been readily available elsewhere.

## Getting started

The project has been published to PyPi, so you should be able to install it with something like one of the following (depending on how you do Python package management):
```terminal
% pip install openapi-spec-tools
% poetry add openapi-spec-tools
```

Generally, there are two intended ways to utilize this package:
* Use `oas` and `cli-gen` as CLI tools to perform actions
* Use the code in the Python modules for your own purpose

The sections below provide a brief description with links to more examples and details.

## OAS

The `oas` script provides a tool for analyzing and modifying an OpenAPI spec. See [OAS.md](OAS.md) for more info.

Here's a trivial example:
```terminal
(.env) % oas analyze models list pet.yaml 
Found 3 models:
    Error
    Pet
    Pets
(.env) % oas analyze models ops pet.yaml Pet
Found Pet is used by 3 operations:
    createPets
    listPets
    showPetById
(.env) % 
```

## CLI Generation

The `cli-gen` tool allows users to create a user-friendly CLI using the OpenAPI spec and a layout file. The layout file provides the CLI structure and refers to the OpenAPI spec for details of operations.  [LAYOUT.md](LAYOUT.md) has more details about the layout file, and the [CLI_GEN.md](CLI_GEN.md) has more info about CLI generation.

Turn a simple layout like:
```YAML
main:
  description: Manage pets
  operations:
    - name: add
      operationId: createPets
```

Into code that produces a CLI that has commands like:
```terminal
% pets add --help
                                                                                                                                                        
 Usage: pets add [OPTIONS]                                             

 Create a pet
 
╭─ Options ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╮
│ --id                 INTEGER                                                                                                                         │
│ --name               TEXT                                                                                                                            │
│ --tag                TEXT                                                                                                                            │
│ --owner              TEXT                                                                                                                            │
│ --api-host           TEXT                              API host address [env var: API_HOST]                                                          │
│ --api-key            TEXT                              API key for authentication [env var: API_KEY]                                                 │
│ --api-timeout        INTEGER                           API request timeout in seconds for a single request [env var: API_TIMEOUT] [default: 5]       │
│ --log                [critical|error|warn|info|debug]  Log level [env var: LOG_LEVEL] [default: warn]                                                │
│ --format             [table|json|yaml]                 Output format style [env var: OUTPUT_FORMAT] [default: table]                                 │
│ --style              [none|bold|all]                   Style for output [env var: OUTPUT_STYLE] [default: all]                                       │
│ --help                                                 Show this message and exit.                                                                   │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
% 
```

See the examples in `examples/` for some more complete works.

## API Generation

The `api-gen` tool allows users to generate API code using the OpenAPI spec. The generated Python code provides type hints and helpful comments, but does no real checking of the arguments and/or return values. The return values are typically dictionaries instead of a data class, such as the models provided in the standard OpenAPI generator.

## Contributing

The [DEVELOPMENT.md](DEVELOPMENT.md) has more information about getting setup as a developer.

The [TODO.md](TODO.md) has some ideas where this project can be improved and expanded -- please add your ideas here, or email Rick directly (rickwporter@gmail.com). 
