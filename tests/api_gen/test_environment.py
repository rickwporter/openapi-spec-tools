import os
from unittest import mock

import pytest

from openapi_spec_tools.api_gen._environment import env_int
from openapi_spec_tools.api_gen._environment import env_string


@pytest.mark.parametrize(
    ["alternate", "args", "expected"],
    [
        pytest.param({"FOO": "sna"}, ["FOO", "bar"], "sna", id="env"),
        pytest.param({}, ["FOO", "bar"], "bar", id="default"),
        pytest.param({}, ["FOO"], None, id="none"),
    ]
)
def test_env_string_success(alternate, args, expected):
    with mock.patch.dict(os.environ, alternate, clear=True):
        assert expected == env_string(*args)


def test_env_string_missing():
    alternate = {}
    with (
        mock.patch.dict(os.environ, alternate, clear=True),
        pytest.raises(ValueError, match="Missing FOO value"),
    ):
        env_string("FOO", "bar", True)


@pytest.mark.parametrize(
    ["alternate", "args", "expected"],
    [
        pytest.param({"FOO": "17"}, ["FOO", 25], 17, id="env"),
        pytest.param({}, ["FOO", 23], 23, id="default"),
        pytest.param({}, ["FOO"], None, id="none"),
    ]
)
def test_env_int_success(alternate, args, expected):
    with mock.patch.dict(os.environ, alternate, clear=True):
        assert expected == env_int(*args)


def test_env_int_missing():
    alternate = {}
    with (
        mock.patch.dict(os.environ, alternate, clear=True),
        pytest.raises(ValueError, match="Missing FOO value"),
    ):
        env_int("FOO", 5, True)


def test_env_int_bad_value():
    alternate = {"FOO": "silly"}
    with (
        mock.patch.dict(os.environ, alternate, clear=True),
        pytest.raises(ValueError),
    ):
        env_int("FOO", 55, True)
