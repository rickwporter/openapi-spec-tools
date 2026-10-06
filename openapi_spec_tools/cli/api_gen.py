#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from enum import Enum
from typing import Annotated

import typer

from openapi_spec_tools.api_gen import FlatApiGenerator
from openapi_spec_tools.api_gen import OpaqueApiGenerator
from openapi_spec_tools.api_gen import PropertyApiGenerator
from openapi_spec_tools.cli.arguments import CodeDirectoryOption
from openapi_spec_tools.cli.arguments import ConfigFileOption
from openapi_spec_tools.cli.arguments import LayoutFilenameOption
from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.arguments import PackageNameOption
from openapi_spec_tools.cli.arguments import PathPrefixOption
from openapi_spec_tools.cli.arguments import StartPointOption
from openapi_spec_tools.cli.utils import gen_config_from_file
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import layout_tree_with_error_handling
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.layout import DEFAULT_START
from openapi_spec_tools.layout import LayoutGenerator

SEP = "\n    "

LOG_CLASS = "api-gen"

class BodyType(str, Enum):
    """Different body types for API generated code."""

    FLAT = "flat"
    PROPERTY = "property"
    OPAQUE = "opaque"


#################################################
# Top-level stuff
app = typer.Typer(
    no_args_is_help=True,
    help="Various operations for API generation."
)


#################################################
# Generate stuff
@app.command("generate", short_help="Generate API code")
def generate_api(
    openapi_file: OpenApiFilenameArgument,
    package_name: PackageNameOption = None,
    config_file: ConfigFileOption = None,
    code_dir: CodeDirectoryOption = None,
    prefix: PathPrefixOption = "",
    layout_file: LayoutFilenameOption = None,
    start: StartPointOption = DEFAULT_START,
    body_type: Annotated[BodyType, typer.Option(help="Request body handling for API functions")] = BodyType.FLAT,
    log_level: LogLevelOption = "info",
) -> None:
    """Generate API code based on the provided parameters.

    The body-type only applies to functions with a request body. It determines the granularity of
    the function arguments, and the amount of work done to form the body.
    """
    logger = init_logging(log_level, LOG_CLASS)

    oas = open_oas_with_error_handling(openapi_file, logger)
    if layout_file:
        commands = layout_tree_with_error_handling(layout_file, start, logger)
    else:
        layout_gen = LayoutGenerator(oas)
        commands = layout_gen.generate(prefix)

    config = gen_config_from_file(config_file)

    if not package_name and not config.package_name:
        typer.echo("Must specify package_name in arguments or configuration.")
        raise typer.Exit(1)

    kwargs = {"package_name": package_name, "oas": oas, "logger": logger, "config": config}
    if body_type == BodyType.FLAT:
        generator = FlatApiGenerator(**kwargs)
    elif body_type == BodyType.PROPERTY:
        generator = PropertyApiGenerator(**kwargs)
    else:
        generator = OpaqueApiGenerator(**kwargs)

    code_dir = code_dir or generator.package_name
    os.makedirs(code_dir, exist_ok=True)

    # copy over the basic infrastructure
    generator.add_init_file(code_dir)
    generator.copy_infrastructure_files(code_dir)
    generator.generate_files(commands, code_dir)

    typer.echo("Generated API files")


if __name__ == "__main__":
    app()
