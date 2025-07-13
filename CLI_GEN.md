# CLI Generation

The CLI generation tool helps users create a CLI that talks to their service. The CLI structure is provided in a YAML file, referred to as the layout file. The layout file links the CLI structure into the OpenAPI specification. More details on layout file format are available in [LAYOUT.md](LAYOUT.md).

## Getting Started

Here's an overview of the steps:
1. Create your virtual environment with required dependencies
1. Add OpenAPI specification
1. Create CLI layout file
1. Run code generation tool

The sections below walks through a "widget" service. The `examples/pets-cli` is provided as a more concrete, complete example.

### Creating virtual environment

Poetry is the tool that is being used in this project, but you can use almost any virtual environment.

Here are the steps used for creating a CLI:
```terminal
# creates the main project
poetry new widgets

# adds the runtime dependencies
poetry add typer rich requests

# add the development tools
poetry add --group dev ruff pytest black coverage openapi-spec-tools
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
  - name: update
    operationId: widget_patch
  - name: set
    operationId: widget_put
  - name: show
    operationId: widget_get
```

The `name` fields are the commands that the CLI user will type. The `operationId` tells the generation tool what that command does -- it pulls information about the request body (if any), parameters, and help based on the `operationId`.

More details are provided in [LAYOUT.md](LAYOUT.md).

### Run the CLI generation tool

The CLI generation tools are installed as `cli-gen`. The command to generate the CLI code looks like:
```terminal
cli-gen generate layout.yaml openapi.yaml widgets .
```

This puts all the generated code into `widgets/`, and test code into `tests/`.

The generation tool overwites existing files with new content, so it is expected that you will need to run this many times to get a complete CLI for your service. However, it does NOT delete previously generated files, so just be aware that you will need to manually delete files associated with an old sub-command.

## Background

A CLI is something that many seasoned developers utilize (yeah, old guys like Rick). A CLI is a common tool to use when trying to determine whether there's an issue with the API or the GUI. This tool is leverages learning from a couple jobs where CLI development was being done various ways. This documents some of the design decisions.

### Use of Python

Python is relatively easy to read, write, understand, and debug. It has good frameworks for a CLI, and is Rick's most frequently used language (at the time of writing).

### Use of Typer

The [typer project](https://github.com/fastapi/typer) provides a user friendly product. It also provides a developer friendly interface that makes code generation relatively easy (e.g. help is colocated with the variables).

### Layout File

It is difficult to get a good CLI structure through inference from the OAS. Rather than get it wrong, let the user tell you what the CLI should look like. Hopefully, the layout structure is easy to extend over time. 

### No OpenAPI Models

There were a couple reasons that drove development in the direction of not using output from the [OpenAPI Generator](https://github.com/OpenAPITools/openapi-generator):
1. Runtime performance
1. Service Non-Conformance

The runtime performance suffered when using OpenAPI generated apis/models. The models were loaded from each module which took a lot of time on each user command. As there got to be 500+ operations/models, the load time just to get help from the CLI took upwards of 4 seconds.

Not all services do a good job of adhering to their OpenAPI specification. For example, some provide an integer in cases when the OAS says they will return a string. Failures to parse server responses due to non-conformant data caused a bad users experience (leading users to blame the CLI). The CLI is not the tool to test adherence to the OAS.

### Modules

The modules whose names start with an underscore (`_`) are modules that get "copied" to the projects using the CLI generation. These modules can refer to other modules with the leading underscore in the name, but should not refer to the modules without the leading underscore. 

Here are some quick explanations of the modules:
* `cli` - code for the `cli-gen` commands. This should remain rather thin -- most utility functions should live (and be tested) elsewhere such that other developers can use them
* `constants` - only current use-case is the `cli-gen` log class name (avoids circular dependencies)
* `files` - utilities to create/copy files
* `generator` - contains the `Generator` class with bulk of logic for generating CLI
* `layout_types` - enumeration and data class definitions for layout object
* `layout` - functions for reading `layout.yaml` and parsing into tree of layout objects
* `utils` - small utility functions which should be language agnotstic

### Extension

The `Generator` was done an an object-oriented fashion to allow for easier exentions by others if they decide to fork the repository. Some utility functions were left out of the object-oriented, but those should not be anything where an override is need.

The OpenAPI spec objects are treated as dictionaries to allow for easier extension. This means your additional properties should be forwarded to the point where you can use those in CLI generation.

There are a few `OasField` values that are added to when changing bodies and parameters into a flat list of properties that are used to create the CLI. For example, the `x-path` is added to avoid the need for maintainng the OpenAPI specification hierarchy when creating the CLI. The `*_settable_properties` functions flatten the body/parameter properties and sub-objects into one list of properties -- this avoids all the need to walk the hierachy several times.
