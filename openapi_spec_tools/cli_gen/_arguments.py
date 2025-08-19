from typing import Annotated
from typing import Optional

import typer

from openapi_spec_tools.base_gen._logging import LogLevel
from openapi_spec_tools.cli_gen._display import OutputFormat
from openapi_spec_tools.cli_gen._display import OutputStyle
from openapi_spec_tools.cli_gen._tree import TreeDisplay

ENV_API_HOST = "API_HOST"
ENV_API_KEY = "API_KEY"
ENV_API_TIME = "API_TIMEOUT"
ENV_LOG_LEVEL = "LOG_LEVEL"
ENV_OUT_FORMAT = "OUTPUT_FORMAT"
ENV_OUT_STYLE = "OUTPUT_STYLE"

ApiKeyOption = Annotated[
    str,
    typer.Option(
        "--api-key",
        show_default=False,
        envvar=ENV_API_KEY,
        help="API key for authentication",
    ),
]
ApiHostOption = Annotated[
    str,
    typer.Option(
        "--api-host",
        show_default=False,
        envvar=ENV_API_HOST,
        help="API host address",
    ),
]
ApiTimeoutOption = Annotated[
    int,
    typer.Option(
        "--api-timeout",
        envvar=ENV_API_TIME,
        help="API request timeout in seconds for a single request",
    ),
]
DetailsOption = Annotated[
    bool,
    typer.Option(
        "--details/--summary",
        "-v",
        help="Display the full details or a summary."
    ),
]
LogLevelOption = Annotated[
    LogLevel,
    typer.Option(
        "--log",
        case_sensitive=False,
        envvar=ENV_LOG_LEVEL,
        help="Log level",
    ),
]
MaxDepthOption = Annotated[
    int,
    typer.Option(
        "--depth",
        "--max-depth",
        help="Maximum depth of tree to display."
    ),
]
MaxCountOption = Annotated[
    Optional[int],
    typer.Option(
        "--max",
        "--max-count",
        help="Maximum number of items to get (if any)."
    )
]
OutputFormatOption = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        case_sensitive=False,
        envvar=ENV_OUT_FORMAT,
        help="Output format style",
    ),
]
OutputStyleOption = Annotated[
    OutputStyle,
    typer.Option(
        "--style",
        case_sensitive=False,
        envvar=ENV_OUT_STYLE,
        help="Style for output",
    ),
]
TreeDisplayOption = Annotated[
    TreeDisplay,
    typer.Option(
        case_sensitive=False,
        help="Details of the CLI command tree to show."
    ),
]
