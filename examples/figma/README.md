# Figma CLI

This package is generated using the OpenAPI specifications tools using the [Figma OpenAPI spec](https://github.com/figma/rest-api-spec).

## Usage

The CLI is generated from the OpenAPI spec and a layout file. The main entrypoint is the `figma` script that gets installed when installing the package. The most common means of using the CLI is to add your application API key to the environment as `API_KEY`, so you do NOT need to enter it each time.

Here's the current top-level help:
```terminal
% figma
                                                                                      
 Usage: figma [OPTIONS] COMMAND [ARGS]...                                             
                                                                                      
 This is the OpenAPI specification for the [Figma REST API](https://www.figma.com...  
                                                                                      
╭─ Options ──────────────────────────────────────────────────────────────────────────╮
│ --install-completion          Install completion for the current shell.            │
│ --show-completion             Show completion for the current shell, to copy it or │
│                               customize the installation.                          │
│ --help                        Show this message and exit.                          │
╰────────────────────────────────────────────────────────────────────────────────────╯
╭─ Commands ─────────────────────────────────────────────────────────────────────────╮
│ commands        Display commands tree for main sub-commands                        │
│ activity-logs   Get activity logs                                                  │
│ component-sets  Get component set                                                  │
│ components      Get component                                                      │
│ images          Render images of file nodes                                        │
│ me              Get current user                                                   │
│ payments        Get payments                                                       │
│ projects        Get files in a project                                             │
│ styles          Get style                                                          │
│ analytics       Manage analytics libraries                                         │
│ dev-resources   Manage dev-resources                                               │
│ files           Manage files                                                       │
│ teams           Manage teams                                                       │
│ webhooks        Manage webhooks                                                    │
╰────────────────────────────────────────────────────────────────────────────────────╯
%
```

Several common options are available on commands or sub-commands:
* `--api-host` - sets host for working with different host
* `--api-key` - sets API key for authentication purposes
* `--log` - logging expose URLs and request timing info
* `--format` - controls output format for JSON or YAML output instead of table
* `--style` - controls various highlighting for output

The `commands` sub-command allows you to see all the commands beneath the current command. Using the `--details`, you can see various help, URL, or operationIds.


## Development

This project is managed with Poetry. It is used to generate and update the `pyproject.toml` and `poetry.lock`.

The `Makefile` is used to provide a means of running several different tools. It provides help for developers, so they do NOT need to recall the most useful commands.

### Main Components

The CLI is generated based on a layout file. For this project, an initial suggested file is included. But, that was hand-edited to be the layout file used for CLI generation.

* `openapi.yaml` - Figma OpenAPI spec
* `suggested.yaml` - initial layout suggestions based solely on OpenAPI spec
* `layout.yaml` - edited layout that provides structure to CLI generation tool and references to the OpenAPI spec 
* `figma_cil/` - directory with the generated code
