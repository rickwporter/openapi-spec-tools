import logging
import os
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli._utils import console_factory
from openapi_spec_tools.cli._utils import layout_tree_with_error_handling
from openapi_spec_tools.cli._utils import open_layout_with_error_handling
from openapi_spec_tools.cli._utils import open_oas_with_error_handling
from tests.helpers import StringIo
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.json", "ERROR: unable to parse", id="bad-json"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad-yaml"),
    ]
)
def test_open_oas(filename, message) -> None:
    logger = logging.getLogger("")
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        open_oas_with_error_handling(asset_filename(filename), logger)

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad"),
    ]
)
def test_open_layout_with_error(filename, message) -> None:
    logger = logging.getLogger("")
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        open_layout_with_error_handling(asset_filename(filename), logger)

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad"),
        pytest.param("pet2.yaml", "ERROR: No start value found for 'start'", id="bad"),
    ]
)
def test_layout_tree_with_error(filename, message) -> None:
    logger = logging.getLogger("")
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        layout_tree_with_error_handling(asset_filename(filename), "start", logger)

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


def test_console_factory() -> None:
    # when running the tests, the PYTEST_VERSION is defined by default
    console = console_factory()
    assert 3000 == console.width

    with mock.patch.dict(os.environ, {"TERMINAL_WIDTH": "12"}):
        console = console_factory()
        assert 12 == console.width

    # using default width for the platform, so it seems to vary
    with mock.patch.dict(os.environ, {}, clear=True):
        console = console_factory()
        assert console.width != 3000
