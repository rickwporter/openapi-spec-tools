#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Optional

import typer

from openapi_spec_tools.api_gen.files import copy_api_infrastructure
from openapi_spec_tools.api_gen.files import generate_api_node
from openapi_spec_tools.api_gen.flat_generator import FlatApiGenerator
from openapi_spec_tools.api_gen.opaque_generator import OpaqueApiGenerator
from openapi_spec_tools.base_gen.files import set_copyright
from openapi_spec_tools.cli._arguments import CopyrightFileOption
from openapi_spec_tools.cli._arguments import LogLevelOption
from openapi_spec_tools.cli._arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli._arguments import StartPointOption
from openapi_spec_tools.cli._utils import init_logging
from openapi_spec_tools.cli._utils import layout_tree_with_error_handling
from openapi_spec_tools.cli._utils import open_oas_with_error_handling
from openapi_spec_tools.layout.layout_generator import DEFAULT_START
from openapi_spec_tools.layout.layout_generator import LayoutGenerator

SEP = "\n    "

LOG_CLASS = "api-gen"

class BodyType(str, Enum):
    """Different body types for API generated code."""

    FLAT = "flat"
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
    package_name: Annotated[str, typer.Argument(show_default=False, help="Base package name")],
    code_dir: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="Directory for code -- overrides default")
    ] = None,
    copyright_file: CopyrightFileOption = None,
    prefix: Annotated[
        str,
        typer.Option(show_default="", help="Prefix to ignore when using path"),
    ] = "",
    layout_file: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="Layout file name to use (instead of generating layout)")
    ] = None,
    start: StartPointOption = DEFAULT_START,
    body_type: Annotated[BodyType, typer.Option(help="Request body handling for API functions")] = BodyType.FLAT,
    log_level: LogLevelOption = "info",
) -> None:
    """Generate API code based on the provided parameters.

    The body-type only applies to functions with a request body. It determines the granularity of
    the function arguments, and the amount of work done to form the body.
    """
    logger = init_logging(log_level, LOG_CLASS)
    code_dir = code_dir or package_name

    oas = open_oas_with_error_handling(openapi_file, logger)
    if layout_file:
        commands = layout_tree_with_error_handling(layout_file, start, logger)
    else:
        layout_gen = LayoutGenerator()
        commands = layout_gen.generate(oas, prefix)

    if copyright_file:
        text = Path(copyright_file).read_text()
        set_copyright(text)

    os.makedirs(code_dir, exist_ok=True)

    # create the init file
    init_file = os.path.join(code_dir, '__init__.py')
    with open(init_file, "w", encoding="utf-8", newline="\n"):
        # do not bother writing anything to init file
        pass

    # copy over the basic infrastructure
    copy_api_infrastructure(code_dir, package_name)

    if body_type == BodyType.FLAT:
        generator = FlatApiGenerator(package_name, oas, logger)
    else:
        generator = OpaqueApiGenerator(package_name, oas, logger)
    generate_api_node(generator, commands, code_dir)

    typer.echo("Generated API files")


if __name__ == "__main__":
    app()
