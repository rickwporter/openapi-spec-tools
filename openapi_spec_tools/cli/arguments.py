"""typer argument definitions to improve consistency amongst CLI commands."""
from enum import Enum
from typing import Annotated
from typing import Optional

import typer

DIRECTORY = "DIRECTORY"
FILENAME = "FILENAME"

class LogLevel(str, Enum):
    """Log levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


CodeDirectoryOption = Annotated[
    Optional[str],
    typer.Option("--code-dir", metavar=DIRECTORY, show_default=False, help="Directory for code -- overrides default")
]
CopyrightFileOption = Annotated[
    Optional[str],
    typer.Option(
        "--copyright-file",
        metavar=FILENAME,
        show_default=False,
        help="File name containing copyright message (for non-default)",
    ),
]
IndentOption = Annotated[
    int,
    typer.Option(
        "--indent",
        min=2,
        max=8,
        help="Number of spaces to indent YAML levels",
    )
]
LayoutFilenameArgument = Annotated[
    str,
    typer.Argument(metavar=FILENAME, show_default=False, help="Layout file YAML definition"),
]
LayoutFilenameOption = Annotated[
    Optional[str],
    typer.Option(
        "--layout-file",
        metavar=FILENAME,
        show_default=False,
        help="Layout file name to use (instead of generating layout)",
    )
]
LogLevelOption = Annotated[
    LogLevel,
    typer.Option(
        "--log",
        case_sensitive=False,
        help="Log level",
    ),
]
OpenApiFilenameArgument = Annotated[
    str,
    typer.Argument(metavar=FILENAME, show_default=False, help="OpenAPI specification filename"),
]
PackageNameArgument = Annotated[str, typer.Argument(metavar="PACKAGE", show_default=False, help="Base package name")]
PathPrefixOption = Annotated[
    str,
    typer.Option(metavar="PREFIX", show_default=False, help="Prefix to ignore when using path"),
]
StartPointOption = Annotated[str, typer.Option("--start", metavar="START", help="Start point for CLI in layout file")]
UpdatedOpenApiFilenameOption = Annotated[
    Optional[str],
    typer.Option(
        "--updated-file",
        metavar=FILENAME,
        show_default=False,
        help="Filename for updated OpenAPI spec, overwrites original of not specified.",
    ),
]

