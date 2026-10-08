# Layout

The layout file is a means of defining the structure of the CLI. It refers to the OpenAPI spec `operationId`'s to fill in the details of the functions. 

In previous jobs, I attempted to infer some of these based on paths. This invariable led me down a path with lots of special case handling. Using this model, there is nothing that is inferred, so the creator of the layout is free to choose names that are completely decoupled from the paths/operations.

The generation of a layout file is covered first, since it is likely most interesting to people. For those that want a more tailored CLI, the layout file can be updated according to the format/schema described in more detail later in this document.

## Generating a Layout File

`layout suggest` writes a starting layout from an OpenAPI specification. Path segments become commands, and each operation becomes a command under that path. Treat the file as a draft: command names can collide, and a path with one operation can leave an extra layer (for example `deploy list` where `deploy` is the command you want). Run `layout check` and edit the file before generating a CLI.

```terminal
layout suggest openapi.yaml layout.yaml --prefix /api/v1 --config layout-config.yaml
```

| Argument | Description |
| --- | --- |
| `OPENAPI` | OpenAPI specification to read. |
| `FILENAME` | Layout file to write. |
| `--prefix` | Path prefix removed before the remaining segments become commands. Path parameters such as `{id}` are dropped. |
| `--config` | YAML file of generator settings. Properties are listed below. |
| `--update` | Merge the new suggestion into the existing output file. Commands already in that file keep their edits. Commands the suggestion no longer includes are removed, and new commands are added. |
| `--indent` | Spaces used to indent each YAML level. Defaults to 4. |

Each remaining path segment is converted to kebab-case and becomes a command or sub-command. A command that has a single operation and no sub-commands is flattened, so the parent command points at that operation.

### Configuration File

`--config` reads a YAML file of `LayoutConfig` properties. Every property is optional. An omitted property uses the built-in default. Pagination names default to empty, so a `pagination` block is written when a configured name matches the operation.

| Field | Description |
| --- | --- |
| `max_help_length` | Maximum length of a generated description before it is truncated. Defaults to 80. |
| `supported_content` | Response content types inspected for pagination body properties. The first type on a successful response that appears in this list is used. Accepted values are `application/json`, `application/yaml`, `application/xml`, `application/pdf`, `application/zip`, and `application/octet-stream`. Defaults to `application/json` and `application/yaml`. |
| `common_operations` | Map of `operationId` segments and HTTP methods to command names. Matching order and the default map are below. |
| `page_size_params` | Query parameter name, or list of names, for the page size. The first name present on the operation is written as `pagination.pageSize`. |
| `page_start_params` | Query parameter name, or list of names, for the starting page. The first match is written as `pagination.pageStart`. |
| `item_start_params` | Query parameter name, or list of names, for the starting item. The first match is written as `pagination.itemStart`. |
| `items_properties` | Response body property name, or list of names, that holds the list of items. The first match is written as `pagination.itemProperty`. |
| `next_properties` | Response body property name, or list of names, that holds the next-page URL. The first match is written as `pagination.nextProperty`. |
| `next_headers` | Response header name, or list of names, that holds the next-page URL. The first match is written as `pagination.nextHeader`. |

`common_operations` is applied in this order:

* An HTTP `put` becomes the command `set`, and an HTTP `patch` becomes `update`.
* Otherwise the `operationId` is converted to snake case and split on `_`. The first segment is looked up, then the last segment, then any other segment.
* If none of those match, the HTTP method is looked up. When the method is absent from the map, the method name is the command.

The default map is:

| Key | Command |
| --- | --- |
| `add`, `create`, `post` | `create` |
| `delete`, `remove` | `delete` |
| `list` | `list` |
| `retrieve`, `get` | `show` |
| `update`, `patch` | `update` |
| `put` | `set` |

```yaml
max_help_length: 80
supported_content:
  - application/json
  - application/yaml
common_operations:
  add: create
  get: show
page_size_params:
  - limit
  - pageSize
page_start_params: page
item_start_params: offset
items_properties:
  - results
  - items
next_properties: next
next_headers: Link
```

## Layout Format

The layout file is really a map of commands/sub-commands to the user operations. The comannd/subcommand identifiers are the top-level keys in the layout, and map to the generated file names.

Let's walk through a quick example with the layout below.

```yaml
main:
  description: My CLI program
  operatons:
  - name: sna
    subcommandId: main_sna
  - name: foo
    subcommandId: foo_main
  - name: bar
    operationId: run_bar

main_sna:
  description: Manage SNA
  operations:
    ...
  
foo_main:
  description: Manage Foo
  operations:
    ...
```

When you generate code for the above, you will have three files -- one for each command/subcommand. 

The default start point is `main`, and you have two sub-commands: `main_sna` and `foo_main`. These top-level keys server as the file/module name. Each will define a `Typer` object named `app` that serves as the focus point for the operations and sub-commands within the module.

In the `main.py`, you will have references to the sub-commands. This uses references to the `Typer` object in each of the sub-modules. It will have one function, `run_bar`, whose arguments are defined by a combination of the layout and OpenAPI specifiction.

## Layout Schema

The two main pieces are the command and operations schemas. The command schema provides the hiearchy, and the operatons schema defines the list of items in the command schema's `operations`.

### Command Schema

The command identifier is used as the file/module name. This is the top-level name, which may be referenced by `subcommandId` values in the operations schema. 

Required:
* `<identifier>` - the name of the command (top-level key)
* `description` - description of this group of commands
* `operations` - list of operations (or references to other sub-commands). More on this in the next section.

Optional:
* `bugIds` - means no code is generated for this sub-command (and below)

### Operations Schema

Required:
* `name` - this is what a user types to access this portion of the CLI
* One of:
  * `operationId` - a reference to an operation from the OAS
  * `subcommandId` - a reference to another command identifier

Optional:
* `bugIds` - means no code is generated for this operation
* `pagination` - properties used to define strategy for retrieving lists of items (see below)
* `summaryFields` - used to display just the listed fields with a `--details` (or `-v`) flag to display all the fields
* `hiddenFields` - used to always remove the listed fields
* `allowedFields` - used to only show the listed fields
* `columns` - used to specify order and columns display in the table. Use `*` to denote all other columns.

#### Pagination Schema

The pagination schema is used to control fetching lists of items. There are many approaches to dividing the response into pages for both client and server reasons. This supports some of the more common approaches, and these parameters tell the depagination function how to approach it.

When any of the pagination elements are specified, a `--max/--max-count` option is added to the CLI command to allow the user to fetch only the specified number of items. This is a local parameter that is not generally sent to the server.

All of the properties should be specified as a name of the query parameter or body property associated with this number.

Here are the pagination schema properties that are all optional:
* `pageSize` - number of elements per page, refers to a query parameter
* `pageStart` - number of starting page, refers to a query parameter
* `itemStart` - number of starting item, refers to a query parameter
* `itemProperty` - used to extract the "real" items from the body
* `nextHeader` - used to get next URL from the specified header
* `nextProperty` - used to the the next URL from the specified body parameter

Here's a simple pagination example:
```yaml
  ...
  operations:
  - name: list
    operationId: widget_list
    pagination:
      pageSize: limit
      itemStart: offset
      nextProperty: next
      itemsProperty: results
```

The `widget_list` function uses `offset` and `limit` query parameters to control the start point (in item count) and number of items per page. It expects the response body to contain `next` and `results` properties (could be more that get ignored, such as `previous` and `totalCount`). The depagination will extract the items from the `results` property and get the URL from the `next` property.

