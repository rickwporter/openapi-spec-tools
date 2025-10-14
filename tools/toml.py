#!/usr/bin/env python3
"""CLI utilities for managing dependencies in sub-projects."""
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Optional

import tomlkit
import typer

app = typer.Typer(no_args_is_help=True, help="Utilities for managing Poetry dependencies in projects.")

NL = "\n"
INDENT = "  "
DirectoryArgument = Annotated[Optional[str], typer.Argument(help="Directory to search for TOML files.")]

def parse_dependencies(start_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse the dependencies for all the pyproject.toml files in the path."""
    run_deps = {}
    dev_deps = {}
    files = start_path.glob("**/pyproject.toml")
    for fname in files:
        with open(fname) as fp:
            project = tomlkit.load(fp)

        name = str(fname.relative_to(start_path))
        tools = project["tool"]["poetry"]
        run_deps[name] = tools["dependencies"]
        dev_deps[name] = tools["group"]["dev"]["dependencies"]

    return (run_deps, dev_deps)


def pivot(by_file: dict[str, Any]) -> dict[str, Any]:
    """Pivot from a per-file dictionary to a per-package dictionary."""
    dependencies = {}
    for fname, deps in by_file.items():
        for dname, dver_ in deps.items():
            package = dependencies.get(dname, {})
            dver = str(dver_)
            versions = package.get(dver, [])
            versions.append(fname)
            package[dver] = versions
            dependencies[dname] = package

    return dependencies


def multiple_versions(dependencies: dict[str, Any]) -> dict[str, Any]:
    """Find dependencies with multiple versions."""
    multiple = {}
    for pkg, versions in dependencies.items():
        if len(versions) > 1:
            multiple[pkg] = versions

    return multiple


def render_full_dependencies(description: str, dependencies: dict[str, Any]) -> str:
    """Render the dependencies into a single string that includes file names."""
    message = f"{description}:"
    for pkg, versions in dependencies.items():
        message += f"{NL}{INDENT}{pkg}:"
        for version, files in versions.items():
            message += f"{NL}{INDENT * 2}{version}:{NL}{INDENT * 3}{f',{NL}{INDENT * 3}'.join(files)}"

    return message + NL


def render_short_dependencies(description: str, dependencies: dict[str, Any]) -> str:
    """Render the dependencies into a single string without file names."""
    message = f"{description}:"
    for pkg, versions in dependencies.items():
        message += f"{NL}{INDENT}{pkg}: {', '.join(versions.keys())}"

    return message + NL


@app.command("check", short_help="Checks to make sure all dependencies use the same versions.")
def check(
    directory: DirectoryArgument = None,
) -> None:
    """Check all toml files are using same dependencies."""
    path = Path(directory) if directory else Path.cwd()
    run_deps, dev_deps = parse_dependencies(path)

    run_deps = pivot(run_deps)
    dev_deps = pivot(dev_deps)

    run_deps = multiple_versions(run_deps)
    dev_deps = multiple_versions(dev_deps)
    if not run_deps and not dev_deps:
        typer.echo("Using consistent versions.")
        return

    message = ""
    if run_deps:
        message += render_full_dependencies("dependencies", run_deps)
    if dev_deps:
        message += render_full_dependencies("development", dev_deps)

    typer.echo(message)
    raise typer.Exit(1)


@app.command("show", short_help="Shows dependencies in the pyproject.toml files.")
def show(
    directory: DirectoryArgument = None,
    verbose: Annotated[bool, typer.Option(help="List files")] = False,
) -> None:
    """Show all the dependencies in the pyproject.toml files."""
    path = Path(directory) if directory else Path.cwd()
    run_deps, dev_deps = parse_dependencies(path)

    run_deps = pivot(run_deps)
    dev_deps = pivot(dev_deps)

    message = ""
    if verbose:
        if run_deps:
            message += render_full_dependencies("dependencies", run_deps)
        if dev_deps:
            message += render_full_dependencies("development", dev_deps)
    else:
        if run_deps:
            message += render_short_dependencies("dependencies", run_deps)
        if dev_deps:
            message += render_short_dependencies("development", dev_deps)

    typer.echo(message)


if __name__ == "__main__":
    app()
