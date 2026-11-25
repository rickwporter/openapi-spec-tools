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
4. Manually modify `layout.yaml` to remove duplicates (or add `bugIds`).
    * Inspect the file and remove duplicates by renaming at least one of the duplicates. This did require re-ordering operations to allow `make layout-lint` to succeed.
5. Updated `layout.yaml` to avoid generating functions with duplicate arguments.
    * Based on feedback below, added `bugIds` to those operations.
```terminal
2026-11-19 01:22:34 PM - oas.cli_gen.cli_generator - INFO Generating users_flags module
2026-11-19 01:22:34 PM - oas.cli_gen.cli_generator - INFO Generating webhooks module
ERROR: Duplicate arguments for searchContexts: continuation_token, filter, limit, sort
ERROR: Duplicate arguments for postWorkflow: template_key
make: *** [cli-gen] Error 1
```
