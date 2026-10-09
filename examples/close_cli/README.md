# Close CLI

The Close CLI project is an example of using the openapi-spec-tools to produce a CLI.

The code generated here is a reasonable first pass -- not a perfect end user product. For a more polished product, a person familiar with the service would want to make updates. Specifying optional fields as described in [LAYOUT.md](../../LAYOUT.md#operations-schema) can make the CLI more user friendly.

## Project Initialization

The project was created with `uv init`.

The number of Python dependencies has been kept to a minimum. In this particular context, the dependency versions need to align with those of the larger package -- this would not be a constraint for a standalone project.

The `close.json` is the OpenAPI specification copied from [here](https://api.close.com/api/openapi.json).

The `Makefile` is an update of others in the `examples/` tailored for this project.

Linting rules were manually added to `pyproject.toml`. Ignoring `RUF100` is the curent standard to avoid flagging unused ignores (e.g. `# noqa: F401`). However, the more targeted ignores are due to differences in the OpenAPI specification that hit "limitations" on the code generation.

The `[project.scripts]` section of `pyproject.toml` was modified to align with using a `typer` application.


## Layout

The layout is created using the `layout_config.yaml` which provides standard pagination parameter names. 

The initial layout suggestion is in `suggested.yaml`. It contains a few duplicate commands as shown below:
```shell
close_cli % uv run layout check suggested.yaml
2026-10-07 07:48:21 AM - layout - INFO Opening suggested.yaml took 0.024123 seconds
Duplicate operations in sub-commands:
    membership: set at 3, 4
    send_as: delete at 2, 3
    task: set at 3, 4
close_cli %
```

These were resolved by renaming (and reordering) the commands.

The layout was also updated as further discussed in the next section.


## CLI

The CLI is created using the installed `cli-gen generate` (as seen in `Makefile`). 

Generating the code was an iterative process, since some bugs were found with the generated code -- this is discussed in [Bugs](#bugs).

This code is NOT perfect -- it uses the information available in the OpenAPI specification to generate code. The use of generic `type: object` without additional information about the properties does not provide the necessary data to generate CLI code.

### Bugs

During CLI generation, the `layout.yaml` was updated with `bugIds` to avoid generating broken code. Rather than remove the items from the layout, `bugIds` were added -- this avoids the process where the operation is flagged as something new.

The `tasks_bulk_update` operation has query and body parameters that have the same name. This causes duplicate parameters in the generated function.

The `typer` framework does not currently allow complex parameters (e.g. `list[dict]`, `Any`). So, `email_templates_render` and `smart_views_list` were removed by adding `bugIds`.
