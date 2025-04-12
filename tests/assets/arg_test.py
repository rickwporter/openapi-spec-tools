#!/usr/bin/env python3
import typer

import oas_tools.cli_gen._arguments as _a

app = typer.Typer(no_args_is_help=True, help="Random help")

@app.command("get", help="Get pet")
def get_pet(
    _api_host: _a.ApiHostOption = "http://acme.com",
    _api_key: _a.ApiKeyOption = None,
    _api_timeout: _a.ApiTimeoutOption = 5,
    _log_level: _a.LogLevelOption = _a.LogLevel.INFO,
    _out_fmt: _a.OutputFormatOption = _a.OutputFormat.TABLE,
    _out_style: _a.OutputStyle = _a.OutputStyle.ALL,
):
    """
    This is to show that oas_tools.cli_gen is obliterated.
    """
    print(f"""\
_api_host={_api_host}
_api_key={_api_key}
_api_timeout={_api_timeout}
_log_level={_log_level}
_out_fmt={_out_fmt}
_out_style={_out_style}
""")


if __name__ == "__main__":
    app()
