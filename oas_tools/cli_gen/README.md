# CLI Generation

The CLI generation tool helps users create a CLI that talks to their service. The CLI structure is provided in a YAML file, referred to as the layout file. The layout file links the CLI structure into the OpenAPI specification.

## Getting Started

Here's an overview of the steps:
1. Create your virtual environment with required dependencies
1. Add OpenAPI specification
1. Create CLI layout file
1. Run code generation tool

The sections below walks through a "widget" service. The `examples/pets-cli` is provided as a more concrete example.

### Creating virtual environment

Poetry is the tool that is being used in this project, but you can use almost any virtual environment.

Here are the steps used for creating a CLI:
```terminal
# creates the main project
poetry new widgets

# adds the runtime dependencies
poetry add typer rich requests

# add the development tools
poetry add --group dev ruff pytest black coverage oas-tools
```

Add an entry to `tools.poetry.scripts` that installs a script to directly run the CLI program.

Add the `tools.ruff*` sections to help check formatting.

### Add OpenAPI specification

The OpenAPI specification (OAS) defines the interface for talking to your service. The layout file creates a link between the CLI and the OAS using the `operationId` from the specification.

### Create CLI layout file

The CLI layout file provides the structure to the CLI, and refers to the OAS for the details. A short example of a `widget` sevice is provided below. The idea is that your OAS would define the operations referred to by `operationId`.

```yaml
main:
  description: Manage widgets
  operations:
  - name: add
    operationId: widget_create
  - name: delete
    operationId: widget_delete
  - name: list
    operationId: widget_list
    pagination:
      pageSize: limit
      nextProperty: next
      itemsProperty: results
  - name: update
    operationId: widget_patch
  - name: set
    operationId: widget_put
  - name: show
    operationId: widget_get
```

The `name` fields are the commands that the CLI user will type. The `operationId` tells the generation tool what that command does -- it pulls information about the request body (if any), parameters, and help based on the `operationId`.

More details are provided in the Layout Format section.

### Run the CLI generation tool

The CLI generation tools are installed as `cli-gen`. The command to generate the CLI code looks like:
```terminal
cli-gen generate layout.yaml openapi.yaml widgets widgets
```

This puts all the generated code into `widgets/`.

The generation tool overwites existing files with new content, so it is expected that you will need to run this many times to get a complete CLI for your service.


## Layout Format

The layout file contains the structure for your command line interface (CLI). The `operationId` fields provide the link to the OAS that allows for code generation using the latest OAS information.

```yaml
cli:
  description: My program does this!
  operations:
  # The operations are a reference to the OAS
  - name: version
    operationId: getAppVersion
  - name: info
    operationId: getInfo
  subcommands:
  - name: resources
    subcommandId: resources_subcommand

resources_subcommand:
  description: Manage your resources
  operations:
  - name: list
    operationId: listResources
    pagination:
      pageSize: pageSize
      itemStart: offset
  subcommands:
  - name: containers
    subcommandId: resources_containers
  - name: memory
    subcommandId: resources_memory


resources_containers:
  description: Manager your containers
  operations:
  - name: list
    operationId: containers_list
    pagination:
      pageSize: size
      pageStart: page

resources_memory:
  description: Managed the cluster memory
  oprations:
  - name: by-container
    operatonId: memory_by_container
  - name: total
    operationId: memory_summary
```
