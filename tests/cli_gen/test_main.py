import typer
from typer.testing import CliRunner

from tests.assets.arg_test import app as program
from tests.cli_gen.helpers import to_ascii

runner = CliRunner(charset="ascii")


def test_main_help():
    app = typer.Typer()
    app.add_typer(program)
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    help = to_ascii(result.stdout)
    # assert "--install-completion" in help
    # assert "--show-completion" in help
    # NOTE: this is not updated with the "actual" parent name, so it is shorter than would be nice
    assert "Display commands tree for " in help


def test_main_commands():
    app = typer.Typer()
    app.add_typer(program)
    result = runner.invoke(app, ["commands", "--help"])
    assert result.exit_code == 0
    help = to_ascii(result.stdout)
    assert "Details of the CLI" in help
    # assert "--max-depth" in help

    result = runner.invoke(app, ["commands", "--depth", 1])
    assert result.exit_code == 0
    text = to_ascii(result.stdout)
    assert "Command Tree" in text
