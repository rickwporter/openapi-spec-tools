import json
from typing import Any
from unittest import mock

import pytest

from oas_tools.cli_gen.requests import _pretty_params
from oas_tools.cli_gen.requests import create_url
from oas_tools.cli_gen.requests import raise_for_error
from oas_tools.cli_gen.requests import request
from oas_tools.cli_gen.requests import request_headers
from requests import HTTPError
from requests import Request
from requests import Response


@pytest.mark.parametrize(
    ["args", "expected"],
    [
        pytest.param(["foo"], "https://foo/", id="host-only"),
        pytest.param(["/foo"], "https://foo/", id="host-slashes"),
        pytest.param(["ftp://foo//"], "ftp://foo/", id="ftp"),
        pytest.param(["http://sna.foo/", "/bar/"], "http://sna.foo/bar/", id="slashes"),
        pytest.param(["foo", 1, "bar"], "https://foo/1/bar/", id="numeric"),
    ]
)
def test_create_url_success(args: list[str], expected: str) -> None:
    assert expected == create_url(*args)


@pytest.mark.parametrize(
    ["args"],
    [
        pytest.param([None], id="none"),
        pytest.param([""], id="empty")
    ]
)
def test_create_url_error(args: list[str]) -> None:
    with pytest.raises(ValueError, match="Missing host"):
        create_url(*args)


UA = "User-Agent"
CT = "Content-Type"
AUTH = "Authorization"
VER = "oas_tools/0.1.0"

@pytest.mark.parametrize(
    ["api_key", "content_type", "kwargs", "expected"],
    [
        pytest.param(None, None, {}, {UA: VER}, id="no-args"),
        pytest.param("foo",  "", {}, {UA: VER, AUTH: "Bearer foo"}, id="key"),
        pytest.param("", "sna", {}, {UA: VER, CT: "sna"}, id="content"),
        pytest.param(None, None, {"extra": "value"}, {UA: VER, "extra": "value"}, id="kwargs"),
        pytest.param("sna",  "foo", {}, {UA: VER, AUTH: "Bearer sna", CT: "foo"}, id="both"),
        pytest.param("sna",  "foo", {"bar": "5pm"}, {UA: VER, AUTH: "Bearer sna", CT: "foo", "bar": "5pm"}, id="all"),
    ]
)
def test_request_headers(api_key, content_type, kwargs, expected) -> None:
    assert expected == request_headers(api_key, content_type, **kwargs)


@pytest.mark.parametrize(
    ["params", "expected"],
    [
        pytest.param(None, "", id="none"),
        pytest.param({}, "", id="empty"),
        pytest.param({"a":"B"}, "?a=B", id="simple"),
        pytest.param({"A": "b", "c": "D"}, "?A=b&c=D", id="multiple"),
        pytest.param({"x y z": 1, "b": True}, "?x y z=1&b=True", id="non-string")
    ]
)
def test_pretty_params(params, expected) -> None:
    assert expected == _pretty_params(params)


def convert_body(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        return bytes(json.dumps(data).encode("utf-8"))
    return bytes(data.encode("utf-8"))


@pytest.mark.parametrize(
    ["status_code", "reason", "body", "expected"],
    [
        pytest.param(403, "Not allowed silly", None, "Not allowed silly \\(403\\)", id="client"),
        pytest.param(500, "Broken Code", None, "Broken Code \\(500\\)", id="server"),
        pytest.param(404, "Not Found", "no-message", "Not Found \\(404\\)", id="no-message"),
        pytest.param(
            499,
            "Unknown error",
            {"message": "not my party"},
            "Unknown error \\(499\\): message: not my party",
            id="single-mesage",
        ),
        pytest.param(
            401,
            "Complex",
            {"code": 303, "text": "something"},
            "Complex \\(401\\): code: 303; text: something",
            id="multi-messages",
        ),
    ],
)
def test_raise_for_error_errors(status_code, reason, body, expected) -> None:
    response = Response()
    response.status_code = status_code
    response.reason = reason
    response.request = Request("GET", "http://dr.com/abc").prepare()
    response._content = convert_body(body)

    with pytest.raises(HTTPError, match=expected):
        raise_for_error(response)


@pytest.mark.parametrize(
    ["status_code"],
    [
        pytest.param(200),
        pytest.param(201),
        pytest.param(202),
        pytest.param(204),
        pytest.param(299),
        pytest.param(300),
    ],
)
def test_raise_for_error_success(status_code) -> None:
    response = Response()
    response.status_code = status_code
    response.request = Request("GET", "http://dr.com/abc").prepare()

    # NOTE: not need to check anything, it just raises an exception
    raise_for_error(response)

@pytest.mark.parametrize(
    ["method", "body", "params", "expected"],
    [
        pytest.param("GET", None, {}, None, id="get-no-body"),
        pytest.param("POST", {}, {}, {}, id="post-empty-body"),
        pytest.param("PATCH", {"message": "done"}, {}, {"message": "done"}, id="patch-body"),
        pytest.param("PUT", "plain-text body", {}, None, id="plaintext"),
    ]
)
def test_request(method, body, params, expected):
    url = "https://foo/path"
    response = Response()
    response.status_code = 200
    response.reason = "OK"
    response._content = convert_body(body)
    response.request = Request(method, url).prepare()
    response.url = url

    prefix = "oas_tools.cli_gen"
    with (
        mock.patch(f"{prefix}.requests.requests.request") as mock_request,
        mock.patch(f"{prefix}.requests.logger.debug") as mock_debug,
        mock.patch(f"{prefix}.requests.logger.info") as mock_info,
        mock.patch(f"{prefix}.requests.raise_for_error") as mock_raise,
    ):
        mock_request.return_value = response

        actual = request(method, url, params=params, body=body)

        # check the underlying Python requests.request() call
        assert mock_request.call_count == 1
        req_args = mock_request.call_args.args
        assert method == req_args[0]
        assert url == req_args[1]
        req_kwargs = mock_request.call_args.kwargs
        assert params == req_kwargs.get("params")
        assert body == req_kwargs.get("json")

        # make sure we're checking for errors
        assert mock_raise.call_count == 1

        # check debug log
        assert mock_debug.call_count == 1
        message = mock_debug.call_args[0][0]
        assert f"Requesting {method} {url}{_pretty_params(params)}" in message

        # check info log
        assert mock_info.call_count == 1
        message = mock_info.call_args[0][0]
        assert f"Got {response.status_code} response from {method} {url}{_pretty_params(params)}" in message

        assert expected == actual
