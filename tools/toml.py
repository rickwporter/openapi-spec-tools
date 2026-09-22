#!/usr/bin/env python3
"""CLI utilities for managing dependencies in sub-projects."""
import re
import subprocess
from pathlib import Path
from typing import Annotated
from typing import Any

import tomlkit
import typer

app = typer.Typer(no_args_is_help=True, help="Utilities for managing uv dependencies in projects.")

REQUIREMENT_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*(.*)$")

NL = "\n"
INDENT = "  "
DirectoryArgument = Annotated[str | None, typer.Argument(help="Directory to search for TOML files.")]


def requirement_name_and_spec(item: str) -> tuple[str, str]:
    """Split a PEP 508 requirement into a package name and version specifier."""
    requirement = item.split(";", maxsplit=1)[0].strip()
    match = REQUIREMENT_RE.match(requirement)
    if not match:
        return requirement, ""

    spec = match.group(2).strip()
    if spec.startswith("(") and spec.endswith(")"):
        spec = spec[1:-1].strip()
    return match.group(1), spec


def parse_requirement_list(items: list[Any] | None, sources: dict[str, Any]) -> dict[str, str]:
    """Parse a list of PEP 508 requirements into package name/specifier pairs."""
    result = {}
    for item in items or []:
        if not isinstance(item, str):
            continue
        name, spec = requirement_name_and_spec(item)
        source = sources.get(name, {})
        if isinstance(source, dict) and source.get("path"):
            spec = f"path={source['path']}"
        result[name] = spec

    return result


def parse_dependencies(start_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Parse the dependencies for all the pyproject.toml files in the path."""
    run_deps = {}
    dev_deps = {}
    files = start_path.glob("**/pyproject.toml")
    for fname in files:
        with open(fname) as fp:
            project = tomlkit.load(fp)

        name = str(fname.relative_to(start_path))
        sources = project.get("tool", {}).get("uv", {}).get("sources", {})
        project_table = project.get("project", {})
        groups = project.get("dependency-groups", {})
        run_deps[name] = parse_requirement_list(project_table.get("dependencies", []), sources)
        dev_deps[name] = parse_requirement_list(groups.get("dev", []), sources)

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


def installed_updates(
    toml: dict[str, Any],
    updates: dict[str, str],
) -> dict[str, list[str]]:
    """Create a list of filenames to package updates."""
    result = {}
    for filename, installed in toml.items():
        items = [package for name, package in updates.items() if name in installed]
        if items:
            result[filename] = items

    return result


def uv_add(directory: Path, items: list[str], group: str | None = None) -> None:
    """Run `uv add` for the packages in one dependency group."""
    if not items:
        return

    args = ["uv", "add"]
    if group:
        args.extend(["--group", group])
    args.extend(items)
    print("*" * 50)
    print(f"Updating {directory} via '{' '.join(args)}'")
    subprocess.call(args, cwd=directory.as_posix())


@app.command("update", short_help="Update the specified dependencies")
def update_dependencies(
    directory: DirectoryArgument = None,
    packages: Annotated[
        list[str] | None,
        typer.Option(
            "--package",
            metavar="<package>[==<version>]",
            help="List of dependencies to udpate",
        ),
    ] = None,
    group: Annotated[str | None, typer.Option(show_default=False, help="Group (if forced)")] = None,
    force: Annotated[bool, typer.Option(help="Whether to force adding packages")] = False,
):
    """Perform 'uv add' with each specified package/version.

    Does NOT add dependencies unless they already exist, or given the --force flag.
    """
    if not packages:
        typer.echo("No updates provided")
        raise typer.Exit(1)

    updates = {p.split('=')[0]: p for p in packages}

    path =  Path(directory) if directory else Path.cwd()
    run_deps, dev_deps = parse_dependencies(path)

    run_commands = installed_updates(run_deps, updates)
    dev_commands = installed_updates(dev_deps, updates)

    if force:
        # when forcing, add items not added by other means
        for filename in run_deps.keys():
            target = dev_commands if group == "dev" else run_commands
            items = target.get(filename, [])
            already = set(run_commands.get(filename, [])) | set(dev_commands.get(filename, []))
            for update in updates.values():
                if update not in already:
                    items.append(update)
            target[filename] = items

    filenames = set(run_commands) | set(dev_commands)
    for filename in sorted(filenames):
        project_dir = Path(filename).parent
        uv_add(project_dir, run_commands.get(filename, []))
        uv_add(project_dir, dev_commands.get(filename, []), group="dev")

    typer.echo("Done")


if __name__ == "__main__":
    app()
