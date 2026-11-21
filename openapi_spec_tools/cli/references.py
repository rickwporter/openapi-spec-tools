#!/usr/bin/env python3
"""Implement the 'references' CLI."""
import json
from datetime import datetime
from datetime import timezone
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
from openapi_spec_tools.cli.arguments import UpdatedOpenApiFilenameOption
from openapi_spec_tools.cli.constants import INDENT
from openapi_spec_tools.cli.utils import error_out
from openapi_spec_tools.cli.utils import init_logging
from openapi_spec_tools.cli.utils import open_oas_with_error_handling
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import add_models
from openapi_spec_tools.utils import find_references
from openapi_spec_tools.utils import get_logger
from openapi_spec_tools.utils import map_models
from openapi_spec_tools.utils import replace_references
from openapi_spec_tools.utils import unmap_models
from openapi_spec_tools.utils import write_oas

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


def get_spec_content(url: str, base_dir: Path | None = None) -> bytes:
    """Read external spec data as bytes.

    A relative local path is resolved against ``base_dir`` when that is provided.
    """
    if not is_url(url):
        # if the local file does NOT exist, this is an error
        file = Path(url)
        if base_dir is not None and not file.is_absolute():
            file = base_dir / file
        if not file.exists():
            error_out(f"Local file {url} does not exist!")
        raw = file.read_bytes()
    else:
        try:
            start = datetime.now(tz=timezone.utc)
            result = requests.get(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
            delta = datetime.now(tz=timezone.utc) - start
            logger.info(f"Download of {url} too {delta.total_seconds()} seconds")
            result.raise_for_status()
            raw = result.content
        except requests.RequestException as error:
            error_out(f"Failed to download {url}: {error}")

    return raw


def get_spec_data(url: str, base_dir: Path | None = None) -> dict[str, Any]:
    """Read an external spec and parse it as JSON or YAML.

    The file extension selects the parser. ``.json`` is JSON, and ``.yaml`` or ``.yml`` is YAML.
    A relative local path is resolved against ``base_dir`` when that is provided.
    """
    raw = get_spec_content(url, base_dir)
    suffix = Path(extract_filename(url)).suffix.lower()
    try:
        if suffix == ".json":
            data = json.loads(raw)
        elif suffix in {".yaml", ".yml"}:
            data = yaml.safe_load(raw)
        else:
            error_out(f"Unsupported spec file type for {url}")
    except (json.JSONDecodeError, yaml.YAMLError, UnicodeDecodeError) as error:
        error_out(f"Failed to parse {url}: {error}")

    if not isinstance(data, dict):
        error_out(f"Failed to parse {url}: expected an object")
    return data


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
    base_dir = Path(filename).parent
    for ext_url in sorted(external):
        raw = get_spec_content(ext_url, base_dir)
        file = dir_path / extract_filename(ext_url)
        file.write_bytes(raw)
        typer.echo(f"Wrote {file} for {ext_url}")

    return


@app.command(
    "update",
    short_help="Resolve external references into one OpenAPI spec"
)
def update_references(
    original_filename: OpenApiFilenameArgument,
    updated_filename: UpdatedOpenApiFilenameOption = None,
    log_level: LogLevelOption = "info",
) -> None:
    init_logging(log_level)
    spec = open_oas_with_error_handling(original_filename)
    out_filename = updated_filename or original_filename  # use current file, if new name not provided

    external_refs = get_external_references(spec)
    if not external_refs:
        typer.echo(f"No external references found in {original_filename}")
        return

    base_dir = Path(original_filename).parent
    for ext_url, ext_refs in external_refs.items():
        data = get_spec_data(ext_url, base_dir)
        components = data.pop(OasField.COMPONENTS, {})
        models = map_models(components)

        ext_short_refs = [_.replace("/components/", "") for _ in ext_refs]
        used = {name: data for name, data in models.items() if name in ext_short_refs}
        inner_refs = find_references(used)
        for name in inner_refs:
            extra_ref = models.get(name)
            if not extra_ref:
                logger.warning(f"Failed to find ref for {name}")
                continue
            used[name] = extra_ref

        replacements = {f"{ext_url}#{name}": f"#{name}" for name in ext_refs}
        add_models(spec, unmap_models(used))
        replace_references(spec, replacements)

    write_oas(out_filename, spec)
    return


if __name__ == "__main__":
    app()
