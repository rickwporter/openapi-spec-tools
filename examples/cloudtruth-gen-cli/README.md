# CloudTruth Generated CLI

This is an experimental project to use OAS tools to generate a CLI.

## Configuration Files

This project uses configuration files for both layout and CLI code generation.

The `layout_config.yaml` sets the names that are used to search for parameters/properties used for pagination.

The `gen_config.yaml` sets some parameters that get reflected in the code generation. The `package_name` is the only critical piece, but could alternatively be set via the `cli-gen generate` command. The other parameters provide examples of how this can be used.
