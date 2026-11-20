#!/usr/bin/env python3
"""Implement the 'references' CLI."""
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Iterable

import requests
import typer
import yaml
from rich_objects import console_factory
from urllib3.util import parse_url

from openapi_spec_tools.cli.arguments import LogLevelOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import get_logger

app = typer.Typer(
    name="references",
    no_args_is_help=True,
    help="Utilities for working with external references (e.g. `$ref` fields) in an OpenAPI spec",
)
logger = get_logger(__name__)
_DOWNLOAD_TIMEOUT_SECONDS = 30

#################################################
# Reference stuff

def get_external_references(spec: dict[str, Any]) -> dict[str, list[str]]:
    """Get map of external references to referred to items in that reference."""
    refs = find_references(spec)
    external = {r for r in refs if not r.startswith("schemas/")}
    if not external:
        return {}

    file_refs = {}
    for ext in external:
        file, separator, item = ext.partition("#")
        if not separator or "#" in item:
            logger.error(f"Invalid reference: {ext}")
            continue
        items = file_refs.get(file, [])
        items.append(item)
        file_refs[file] = items

    return {file: sorted(items) for file, items in file_refs.items()}


def is_url(value: str) -> bool:
    """Return whether ``value`` is a URL.

    urllib3 records a scheme for a URL. A local filename has no scheme.
    """
    return parse_url(value).scheme is not None


def extract_filename(url: str) -> str:
    """Extract the filename from the URL.

    The name is the final segment of the path parsed by urllib3. A value with no path, such as
    ``common.yaml``, is returned as given. Query and fragment are left out.
    """
    parsed = parse_url(url)
    if parsed.path:
        return parsed.path.rsplit("/", maxsplit=1)[-1]
    return parsed.host or ""


def check_duplicate_file_names(urls: Iterable) -> None:
    """Insure there are no duplicate filenames that would cause things to be overwritten."""
    names = [extract_filename(url) for url in urls]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if not duplicates:
        return

    error_out(f"Duplicate filenames for: {', '.join(duplicates)}")


@app.command(
    "find",
    short_help="Look for external references in an OpenAPI spec"
)
def find_external_references(
    filename: OpenApiFilenameArgument,
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level)
    spec = open_oas_with_error_handling(filename)

    external = get_external_references(spec)
    if not external:
        typer.echo(f"No external references found in {filename}")
        return

    console = console_factory()
    console.print(yaml.dump(external, indent=len(INDENT)))
    return


@app.command(
    "download",
    short_help="Download the external references from an OpenAPI spec"
)
def download_references(
    filename: OpenApiFilenameArgument,
    out_dir: Annotated[
        str,
        typer.Option(help="Directory to put the files into"),
    ] = ".",
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level)
    spec = open_oas_with_error_handling(filename)

    external = get_external_references(spec)
    if not external:
        typer.echo(f"No external references found in {filename}")
        return

    check_duplicate_file_names(external.keys())

    dir_path = Path(out_dir)
    dir_path.mkdir(parents=True, exist_ok=True)
    for ext_url in sorted(external):
        if not is_url(ext_url):
            # if the local file does NOT exist, this is an error
            file = dir_path / ext_url
            if not file.exists():
                error_out(f"Local file {ext_url} does not exist!")
            typer.echo(f"{ext_url} is a filename instead of a URL")
            continue
        file = dir_path / extract_filename(ext_url)
        try:
            result = requests.get(ext_url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
            result.raise_for_status()
        except requests.RequestException as error:
            error_out(f"Failed to download {ext_url}: {error}")
        file.write_text(result.text, encoding="utf-8", newline="\n")
        typer.echo(f"Wrote {file} for {ext_url}")

    return


if __name__ == "__main__":
    app()
