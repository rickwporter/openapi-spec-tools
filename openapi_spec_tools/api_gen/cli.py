#!/usr/bin/env python3
"""Implementation of the CLI generation CLI."""
import os
from enum import Enum
from pathlib import Path
from typing import Annotated
from typing import Optional

import typer

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.api_gen.files import copy_api_infrastructure
from openapi_spec_tools.api_gen.files import generate_api_node
from openapi_spec_tools.base_gen._logging import get_logger
from openapi_spec_tools.base_gen._logging import init_logging
from openapi_spec_tools.base_gen.files import open_oas_with_error_handling
from openapi_spec_tools.base_gen.files import set_copyright
from openapi_spec_tools.layout.layout_generator import LayoutGenerator

SEP = "\n    "

class LogLevel(str, Enum):
    """Log levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


OpenApiFilenameArgument = Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")]
LogLevelOption = Annotated[
    LogLevel,
    typer.Option(
        "--log",
        case_sensitive=False,
        help="Log level",
    ),
]


GENERATOR_LOG_CLASS = "api-gen"

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
    copyright_file: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="File name containing copyright message (for non-default)"),
    ] = None,
    prefix: Annotated[
        str,
        typer.Option(show_default="", help="Prefix to ignore"),
    ] = "",
    log_level: LogLevelOption = "info",
) -> None:
    """Generate API code based on the provided parameters."""
    init_logging(log_level, GENERATOR_LOG_CLASS)
    code_dir = code_dir or package_name

    oas = open_oas_with_error_handling(openapi_file, get_logger(GENERATOR_LOG_CLASS))
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

    generator = ApiGenerator(package_name, oas)
    generate_api_node(generator, commands, code_dir)

    typer.echo("Generated API files")


if __name__ == "__main__":
    app()
