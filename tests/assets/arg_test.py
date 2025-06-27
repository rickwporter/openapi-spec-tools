#!/usr/bin/env python3
from pathlib import Path

import typer

import openapi_spec_tools.cli_gen._arguments as _a
import openapi_spec_tools.cli_gen._tree as _t

app = typer.Typer(no_args_is_help=True, help="Random help")


@app.command("commands", short_help="Display commands tree for sub-commands")
def show_commands(
    display: _a.TreeDisplayOption = _a.TreeDisplay.HELP,
    depth: _a.MaxDepthOption = 5,
) -> None:
    path = Path(__file__).parent / "tree_pets.yaml"
    _t.tree(path.as_posix(), "main", display, depth)
    return


@app.command("get", help="Get pet")
def get_pet(
    _api_host: _a.ApiHostOption = "http://acme.com",
    _api_key: _a.ApiKeyOption = None,
    _api_timeout: _a.ApiTimeoutOption = 5,
    _log_level: _a.LogLevelOption = _a.LogLevel.INFO,
    _out_fmt: _a.OutputFormatOption = _a.OutputFormat.TABLE,
    _out_style: _a.OutputStyle = _a.OutputStyle.ALL,
    _details: _a.DetailsOption = False,
    _max_count: _a.MaxCountOption = None,
):
    """This is to show that openapi_spec_tools.cli_gen is obliterated."""
    print(f"""\
_api_host={_api_host}
_api_key={_api_key}
_api_timeout={_api_timeout}
_log_level={_log_level}
_out_fmt={_out_fmt}
_out_style={_out_style}
_details={_details}
_max_count={_max_count}
""")


if __name__ == "__main__":
    app()
