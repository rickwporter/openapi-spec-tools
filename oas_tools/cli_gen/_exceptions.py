import typer
from requests import HTTPError


def handle_exceptions(ex: Exception) -> None:
    """Process exception and print a more concise error"""
    if isinstance(ex, HTTPError):
        message = str(ex.args[0])
    else:
        message = str(ex)
    typer.echo(f"[red]ERROR:[/red] {message}")
    raise typer.Exit(1)
