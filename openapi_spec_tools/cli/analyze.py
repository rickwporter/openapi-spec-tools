#!/usr/bin/env python3
"""Implement the 'oas analyze' CLI commands."""
import typer

from openapi_spec_tools.cli.content import app as content_app
from openapi_spec_tools.cli.models import app as models_app
from openapi_spec_tools.cli.operations import app as op_app
from openapi_spec_tools.cli.paths import app as path_app
from openapi_spec_tools.cli.tags import app as tag_app

app = typer.Typer(no_args_is_help=True, short_help="Tools for analyzing an OAS file")
app.add_typer(op_app, name="ops")
app.add_typer(path_app, name="paths")
app.add_typer(models_app, name="models")
app.add_typer(tag_app, name="tags")
app.add_typer(content_app, name="content")
