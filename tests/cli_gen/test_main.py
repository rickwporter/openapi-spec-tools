import os
from unittest import mock

import pytest
import typer
from rich_objects import to_ascii
from typer.testing import CliRunner

from tests.assets.arg_test import app as program

MAX_WIDTH = 1000

@pytest.fixture
def terminal_width_env():
    env = {
        "TERMINAL_WIDTH": str(MAX_WIDTH),
    }
    with mock.patch.dict(os.environ, env, clear=True):
         yield


@pytest.mark.usefixtures("terminal_width_env")
def test_main_help():
    runner = CliRunner(charset="ascii")
    app = typer.Typer()
    app.add_typer(program)
    result = runner.invoke(app, ["--help"], terminal_width=MAX_WIDTH)
    assert result.exit_code == 0
    help = to_ascii(result.stdout)
    assert "--install-completion" in help
    assert "--show-completion" in help
    # NOTE: this is not updated with the "actual" parent name, so it is shorter than would be nice
    assert "Display commands tree for " in help


@pytest.mark.usefixtures("terminal_width_env")
def test_main_commands():
    runner = CliRunner(charset="ascii")
    app = typer.Typer()
    app.add_typer(program)
    result = runner.invoke(app, ["commands", "--help"], terminal_width=MAX_WIDTH)

    assert result.exit_code == 0
    help = to_ascii(result.stdout)
    assert "Details of the CLI" in help
    assert "--max-depth" in help

    result = runner.invoke(app, ["commands", "--depth", 0], terminal_width=MAX_WIDTH)
    assert result.exit_code == 0
    text = to_ascii(result.stdout)
    assert "Command Tree" in text
