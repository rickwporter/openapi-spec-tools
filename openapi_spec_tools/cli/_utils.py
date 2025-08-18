"""Common extensions to Typer for local CLI use."""
import logging
from datetime import datetime
from enum import Enum
from typing import Any

import typer
from rich import print

from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.layout.utils import open_layout
from openapi_spec_tools.utils import open_oas

# Common argument definition
LOG_CLASS = "cli"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %I:%M:%S %p"


class LogLevel(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


def get_logger(name: str) -> logging.Logger:
    """Fetch the logger for the specified log class name."""
    return logging.getLogger(name=name)


def init_logging(level: LogLevel, name: str) -> logging.Logger:
    """Initialize logging."""
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FMT)
    logger = get_logger(name)
    logger.setLevel(level.upper())
    return logger


def error_out(message: str, exit_code: int = 1) -> None:
    """Print provided error message (with red ERROR prefix) and exit."""
    print(f"[red]ERROR:[/red] {message}")
    raise typer.Exit(exit_code)


def open_oas_with_error_handling(filename: str, logger: logging.Logger) -> Any:
    """Perform error handling around opening an OpenAPI spec.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        data = open_oas(filename)
        delta = datetime.now() - starttime
        logger.info(f"Opening {filename} took {delta.total_seconds()} seconds")
        return data
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


def open_layout_with_error_handling(filename: str, logger: logging.Logger) -> Any:
    """Perform error handling around opening a layout file.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        data = open_layout(filename)
        delta = datetime.now() - starttime
        logger.info(f"Opening {filename} took {delta.total_seconds()} seconds")
        return data
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


def layout_tree_with_error_handling(filename: str, start: str, logger: logging.Logger) -> LayoutNode:
    """Perform error handling around opening a layout file.

    Avoids the standard Typer error handling that is quite verbose.
    """
    try:
        starttime = datetime.now()
        tree = file_to_tree(filename, start)
        delta = datetime.now() - starttime
        logger.info(f"Parsing {filename} into tree took {delta.total_seconds()} seconds")
        return tree
    except FileNotFoundError:
        message = f"failed to find {filename}"
    except ValueError as ex:
        message = str(ex)
    except Exception as ex:
        message = f"unable to parse {filename}: {ex}"

    typer.echo(f"ERROR: {message}")
    raise typer.Exit(1)


