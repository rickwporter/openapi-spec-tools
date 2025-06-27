import typer
from requests import HTTPError

from openapi_spec_tools.cli_gen._console import console_factory


class MissingRequiredError(Exception):
    """Short wrapper to provde feedback about missing required options."""

    def __init__(self, names: list[str]):
        message = f"Missing required parameters, please provide: {', '.join(names)}"
        super().__init__(message)


def handle_exceptions(ex: Exception) -> None:
    """Process exception and print a more concise error."""
    if isinstance(ex, HTTPError):
        message = str(ex.args[0])
    else:
        message = str(ex)
    console = console_factory()
    console.print(f"[red]ERROR:[/red] {message}")
    raise typer.Exit(1)
