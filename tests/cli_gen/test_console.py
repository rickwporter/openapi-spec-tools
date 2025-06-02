import os
from unittest import mock

from openapi_spec_tools.cli_gen._console import TEST_TERMINAL_WIDTH
from openapi_spec_tools.cli_gen._console import console_factory


def test_console_factory_width_arg():
    with mock.patch.dict(os.environ, {"TERMINAL_WIDTH": "33"}):
        console = console_factory(width=23)
    assert console.width == 23


def test_console_factory_env_arg():
    with mock.patch.dict(os.environ, {"TERMINAL_WIDTH": "33"}):
        console = console_factory()
    assert console.width == 33


def test_console_factory_pytest():
    console = console_factory()
    assert console.width == TEST_TERMINAL_WIDTH


def test_console_factory_unspecified():
    with mock.patch.dict(os.environ, {}, clear=True):
        console = console_factory()
    # not really a hard value -- it is just something other than the test
    assert console.width != TEST_TERMINAL_WIDTH
