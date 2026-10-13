# Trains

This example comes from the API defined at [train-travel-api](https://github.com/bump-sh-examples/train-travel-api).

## Getting started

Here are some notes about how this project came to the current state.

### Setting up Python project

Install uv and create the project.

### Creating the layout

To get started, the layout file was generated without a configuration using the command captured in `make layout-suggest`. This creates the `suggested.yaml` which was copied to `layout.yaml` before being modified.

The suggested layout was not quite as streamlined as desired. It had a couple top-level commands (e.g. `stations`, and `trips`) with only a `show` option. So, those operations were moved up into `main`. Analogously, the original `bookings_payment` only had a `create`, so it was moved directly into the `bookings` command.

Initially, `pagination` parameters were manually added to the three items that take list query parameters and provide data back in a list. More recently, a `layout_config.yaml` was added to allow the `layout suggest` step finds the pagination parameters.

### Generate code

The `make cli-gen` captures the command used to generate the CLI code. You can use the `cli-regen` target to delete the directory and start over.
