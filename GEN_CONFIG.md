# Generator Config

The `BaseGenerator` is the basis for both CLI and API code generation.
It can be configured using a YAML file with properties that help control outputs.

## How it works

The `BaseGenerator` constructor accepts a `GeneratorConfig` object named `config` as an optional parameter.
The `BaseGenerator` constructor initializes most data members with the first non-`None` value in order of:
* passed parameter
* configured parameter
* the default

In both `api-gen` and `cli-gen`, there is a `--config` option where users can specify the configuration file name.

## Configuration Options

Here are the configuration options, and a general idea of their scope.

| Field | Description |
| --- | --- |
| `package_name` | Python package name written into generated imports and copied files. |
| `supported_content` | Content types checked when selecting a request body. The first match is used. |
| `max_help_length` | Maximum length of generated help text before it is truncated. |
| `reserved` | Names that generated functions and variables must not use. |
| `conflict_suffix` | Text appended when a generated name is in `reserved`. |
| `copyright` | Header text written at the top of generated files. A path to an existing file is read as that text. |
| `infra_files` | Source-to-destination map of infrastructure modules copied into the generated package. |
| `infra_replacements` | Text replacements applied while copying infrastructure files. |
| `test_files` | Source-to-destination map of test modules copied into the test directory. |
| `test_replacements` | Text replacements applied while copying test files. |
| `env_host` | Environment variable name, or list of names, for the API host. |
| `env_key` | Environment variable name, or list of names, for the API key. |
| `env_timeout` | Environment variable name, or list of names, for the request timeout. |
| `env_log_level` | Environment variable name, or list of names, for the log level. |
| `default_host` | API host used when the environment variable is unset. The first OpenAPI server URL is used when this is omitted. |
| `default_log_level` | Log level used when the environment variable is unset. |
| `default_timeout` | Request timeout, in seconds, used when the environment variable is unset. |

## Example

Currently, the `examples/cloudtruth-gen-cli/` uses a configuration file ([config.yaml](examples/cloudtruth-gen-cli/config.yaml)) for CLI generation.
