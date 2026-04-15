#!/usr/bin/env python3
"""Implement the 'oas-history' CLI commands."""
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Annotated
from typing import Any
from typing import Optional

import git
import typer
import yaml
from rich_objects import TableConfig
from rich_objects import console_factory
from rich_objects import display

from openapi_spec_tools.cli.arguments import MaxCountOption
from openapi_spec_tools.cli.arguments import OpenApiFilenameArgument
from openapi_spec_tools.cli.arguments import OutputFormat
from openapi_spec_tools.cli.arguments import OutputFormatOption
from openapi_spec_tools.cli.arguments import OutputStyle
from openapi_spec_tools.cli.arguments import OutputStyleOption
from openapi_spec_tools.utils import find_diffs

app = typer.Typer(name="history", no_args_is_help=True, short_help="Git history of OAS file")
LOG_CLASS = "history"


AuthorOption = Annotated[
    Optional[str],
    typer.Option("--author", show_default=False, help="Name, or partial name, of author or coauthor (case insensitive)")
]
EndDateOption = Annotated[
    Optional[datetime],
    typer.Option("--end", show_default=False, help="Date/time of latest commit.")
]
StartDateOption = Annotated[
    Optional[datetime],
    typer.Option("--start", show_default=False, help="Date/time of first commit.")
]



def _with_timezone(dt: datetime | None) -> datetime | None:
    return dt if not dt or dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _read_data(commit: git.Commit, file: str) -> dict[str, Any]:
    relative_path = Path(file).absolute().relative_to(commit.tree.abspath)
    target_file = commit.tree / relative_path
    data = target_file.data_stream.read().decode("utf-8")
    # NOTE: handles when data is JSON, so no special handling necessary
    return yaml.safe_load(data)


def _author_match(commit: git.Commit, author: str) -> bool:
    needle = author.lower()
    if needle in commit.author.name.lower() or needle in commit.author.email:
        return True

    for coauth in commit.co_authors:  # pragma: no cover
        if needle in coauth.name.lower() or needle in coauth.email:
            return True

    return False


def _find_commits(
    oas_file: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    author: Optional[str] = None,
    max_count: Optional[int] = None,
) -> list[git.Commit]:
    repo = git.Repo(oas_file, search_parent_directories=True)

    commits = list(repo.iter_commits(paths=oas_file))
    if start:
        commits = [_ for _ in commits if _.committed_datetime >= start]
    if end:
        commits = [_ for _ in commits if _.committed_datetime <= end]
    if author:
        commits = [_ for _ in commits if _author_match(_, author=author)]
    if max_count:
        commits = commits[:max_count]

    return commits


@app.command("commits", short_help="Show git history of the specified OAS file.")
def commit_history(
    oas_file: OpenApiFilenameArgument,
    start: StartDateOption = None,
    end: EndDateOption = None,
    author: AuthorOption = None,
    max_count: MaxCountOption = 30,
    out_fmt: OutputFormatOption = OutputFormat.TABLE,
    out_style: OutputStyleOption = OutputStyle.ALL,
):
    """Show git history of the specific OAS file over with the provided search parameters."""
    start = _with_timezone(start)
    end = _with_timezone(end)
    commits = _find_commits(
        oas_file=oas_file,
        start=start,
        end=end,
        author=author,
        max_count=max_count,
    )
    console = console_factory()
    if not commits:
        console.print("No commits found.")
        return

    columns = ["date", "commit", "*"]
    data = [
        {
            "date": _.authored_datetime.date().isoformat(),
            "commit": _.hexsha[:7],
            "author": _.author.name,
            "message": _.message.strip()[:100],
        }
        for _ in commits
    ]
    display(data, fmt=out_fmt, style=out_style, columns=columns, console=console)
    return


@app.command("changes", short_help="Show OAS changes over git history.")
def commit_changes(
    oas_file: OpenApiFilenameArgument,
    start: StartDateOption = None,
    end: EndDateOption = None,
    author: AuthorOption = None,
    max_count: MaxCountOption = 30,
    out_fmt: OutputFormatOption = OutputFormat.TABLE,
    out_style: OutputStyleOption = OutputStyle.ALL,
):
    """Show OAS changes over the history of the provided search. The ."""
    start = _with_timezone(start)
    end = _with_timezone(end)
    # NOTE: do not filter out commits by other authors, or before start, or will get odd comparisons
    commits = _find_commits(
        oas_file=oas_file,
        end=end,
    )
    columns = ["date", "commit", "changes"]
    data = []
    prev_comm = commits[0]
    prev_data = _read_data(prev_comm, oas_file)
    for curr_comm in commits[1:]:
        curr_data = _read_data(curr_comm, oas_file)
        if not author or _author_match(prev_comm, author):
            # because we're walking backward chronologicallly, the prev/curr are different order
            changes = find_diffs(curr_data, prev_data)
            if out_fmt == OutputFormat.TABLE:
                # YAML format is the best looking format for the diffs in a table, so force it
                changes = yaml.dump(changes).strip()
            data.append(
                {
                    "date": prev_comm.authored_datetime.date().isoformat(),
                    "commit": prev_comm.hexsha[:7],
                    "changes": changes,
                }
            )

        # check whether we've hit the last entry
        if len(data) == max_count or (start and curr_comm.authored_datetime < start):
            break

        prev_data = curr_data
        prev_comm = curr_comm

    console = console_factory()
    if not data:
        console.print("No differences found with those parameters.")
        return

    config = TableConfig(value_max_len=1000)
    display(data, fmt=out_fmt, style=out_style, columns=columns, config=config, console=console)
    return


if __name__ == "__main__":
    app()
