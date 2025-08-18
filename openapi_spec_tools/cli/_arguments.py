from enum import Enum
from typing import Annotated
from typing import Optional

import typer


class LogLevel(str, Enum):
    """Log levels."""

    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


CopyrightFileOption = Annotated[
    Optional[str],
    typer.Option(show_default=False, help="File name containing copyright message (for non-default)"),
]
LayoutFilenameArgument = Annotated[str, typer.Argument(show_default=False , help="Layout file YAML definition")]
LogLevelOption = Annotated[
    LogLevel,
    typer.Option(
        "--log",
        case_sensitive=False,
        help="Log level",
    ),
]
OpenApiFilenameArgument = Annotated[str, typer.Argument(show_default=False, help="OpenAPI specification filename")]
StartPointOption = Annotated[str, typer.Option(help="Start point for CLI in layout file")]


