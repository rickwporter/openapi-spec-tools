# Copyright 2025
#
# This code was generated by the openapi-spec-tools CLI generator, DO NOT EDIT
#
from io import StringIO
from unittest import mock

import pytest
import typer
from requests import HTTPError

from pets_cli._exceptions import MissingRequiredError
from pets_cli._exceptions import handle_exceptions


@pytest.mark.parametrize(
    ["exception", "message"],
    [
        pytest.param(ValueError("My party"), "My party", id="ValueError"),
        pytest.param(HTTPError("bogus"), "bogus", id="HTTPError"),
    ]
)
def test_handle_exceptions(exception, message):
    with mock.patch('sys.stdout', new_callable=StringIO) as mock_stdout:
        with pytest.raises(typer.Exit) as ex:
            handle_exceptions(exception)
        assert ex.value.exit_code == 1
        assert message in mock_stdout.getvalue()


def test_missing_required():
    items = ["abc", "123"]
    ex = MissingRequiredError(items)
    msg = str(ex)
    assert "Missing required parameters, please provide: abc, 123" == msg
