# LaunchDarkly CLI

This is an example of using `openapi-spec-tools` to generate a CLI.

## Development

This example is to demonstrate using the tools to provide an example of how to develop. 

## History

This is a brief summary of the history. It includes steps taken in the initial PR which will be flattened when the PR merges.

1. Initial commit with rudimentary suggested.yaml.
    * Running `uv run layout check suggested.yaml` reveals issues with duplicates, plus other oddities (e.g. api, and v2 are nested commands) can be seen when inspecting the suggested layout.
2. Added `layout_config.yaml` used in `make layout-suggest` with a `prefix` specified.
    * This removes a couple levels of CLI command, and shortens subcommand names and descriptions.
    * Running `uv run layout check suggested.yaml` still reveals issues with duplicates.
3. Updated `layout_config.yaml` to specify pagination parameters to help distinguish `list` from `show` commands.
    * This reduces the duplicates to a more managable level, so the `suggested.yaml` was copied to `layout.yaml`
