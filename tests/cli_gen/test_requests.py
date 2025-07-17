import importlib.metadata
import json
import os
from tempfile import TemporaryDirectory
from typing import Any
from unittest import mock

import pytest
import yaml
from requests import HTTPError
from requests import Request
from requests import Response

from openapi_spec_tools.cli_gen._requests import PageParams
from openapi_spec_tools.cli_gen._requests import _pretty_params
from openapi_spec_tools.cli_gen._requests import create_url
from openapi_spec_tools.cli_gen._requests import depaginate
from openapi_spec_tools.cli_gen._requests import raise_for_error
from openapi_spec_tools.cli_gen._requests import request
from openapi_spec_tools.cli_gen._requests import request_headers

APP_JSON = "application/json"
APP_YAML = "application/yaml"
TEXT_PLAIN = "text/plain"
IMAGE_PNG = "image/png"


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


def _find_version() -> str:
    """Leverage one of the objects to get the module name"""
    module_name = PageParams.__module__.split(".")[0]
    module_version = importlib.metadata.version(module_name)
    return f"{module_name}/{module_version}"


UA = "User-Agent"
CT = "Content-Type"
AUTH = "Authorization"
VER = _find_version()


@pytest.mark.parametrize(
    ["api_key", "content_type", "kwargs", "expected"],
    [
        pytest.param(None, None, {}, {UA: VER}, id="no-args"),
        pytest.param("foo", "", {}, {UA: VER, AUTH: "Bearer foo"}, id="key"),
        pytest.param("", "sna", {}, {UA: VER, CT: "sna"}, id="content"),
        pytest.param(None, None, {"extra": "value"}, {UA: VER, "extra": "value"}, id="kwargs"),
        pytest.param("sna", "foo", {}, {UA: VER, AUTH: "Bearer sna", CT: "foo"}, id="both"),
        pytest.param("sna", "foo", {"bar": "5pm"}, {UA: VER, AUTH: "Bearer sna", CT: "foo", "bar": "5pm"}, id="all"),
    ]
)
def test_request_headers(api_key, content_type, kwargs, expected) -> None:
    assert expected == request_headers(api_key, content_type, **kwargs)


@pytest.mark.parametrize(
    ["params", "expected"],
    [
        pytest.param(None, "", id="none"),
        pytest.param({}, "", id="empty"),
        pytest.param({"a": "B"}, "?a=B", id="simple"),
        pytest.param({"A": "b", "c": "D"}, "?A=b&c=D", id="multiple"),
        pytest.param({"x y z": 1, "b": True}, "?x y z=1&b=True", id="non-string")
    ]
)
def test_pretty_params(params, expected) -> None:
    assert expected == _pretty_params(params)


def convert_body(data: Any, content_type: str) -> Any:
    if data is None:
        return None
    if isinstance(data, (dict, list)):
        if content_type == APP_JSON:
            return bytes(json.dumps(data).encode("utf-8"))
        if content_type == APP_YAML:
            return bytes(yaml.dump(data).encode("utf-8"))
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
    response._content = convert_body(body, APP_JSON)

    with pytest.raises(HTTPError, match=expected):
        raise_for_error(response)


def success_response(
    method: str = "GET",
    url: str = "http://localhost",
    status_code: int = 200,
    body: Any = None,
    headers: Any = None,
    content_type: str = APP_JSON,
) -> Response:
    """Convenience method to set some fields."""
    response = Response()
    response.url = url
    response.status_code = status_code
    response.request = Request(method, url).prepare()
    response._content = convert_body(body, content_type)
    if headers:
        response.headers.update(headers)

    return response


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
    response = success_response(status_code=status_code)

    # NOTE: not need to check anything, it just raises an exception
    raise_for_error(response)


@pytest.mark.parametrize(
    ["method", "content_type", "body", "params", "expected"],
    [
        pytest.param("GET", APP_JSON, None, {}, None, id="get-no-body"),
        pytest.param("POST", APP_JSON, {}, {}, {}, id="post-empty-body"),
        pytest.param("PATCH", APP_JSON, {"message": "done"}, {}, {"message": "done"}, id="patch-body"),
        pytest.param("PUT", APP_JSON, "plain-text body", {}, None, id="json-plain"),
        pytest.param("PUT", TEXT_PLAIN, "plain-text body", {}, "plain-text body", id="text-plain"),
        pytest.param("PATCH", APP_YAML, {"message": "done"}, {}, {"message": "done"}, id="good-yaml"),
        pytest.param("PATCH", APP_YAML, "message:\n  other:\n bad:", {}, None, id="bad-yaml"),
        pytest.param("GET", "text/csv", "a,b,c\n1,2,3\n", {}, "Wrote content to output.csv", id="save-csv"),
        pytest.param("GET", "application/unknown", "content include, not returned", {}, None, id="unhandled")
    ]
)
def test_request(method, content_type, body, params, expected):
    url = "https://foo/path"
    headers = {"Content-type": content_type}
    response = success_response(url=url, body=body, headers=headers, content_type=content_type)
    directory = TemporaryDirectory()
    os.chdir(directory.name)

    prefix = "openapi_spec_tools.cli_gen"
    with (
        mock.patch(f"{prefix}._requests.requests.request") as mock_request,
        mock.patch(f"{prefix}._requests.logger.debug") as mock_debug,
        mock.patch(f"{prefix}._requests.logger.info") as mock_info,
        mock.patch(f"{prefix}._requests.raise_for_error") as mock_raise,
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


ITEMS = [
    {"a": 1, "b": True, "c": "some str", "d": None},
    {"a": 2, "b": False, "c": "", "d": False},
    {"a": 3, "b": True, "c": "anoterh", "d": 3},
]


@pytest.mark.parametrize(
    ["page_params", "resp_body", "expected"],
    [
        pytest.param(PageParams(), {}, [], id="empty-dict"),
        pytest.param(PageParams(), [], [], id="empty-list"),
        pytest.param(PageParams(page_size_value=10), ITEMS, ITEMS, id="page-size"),
        pytest.param(PageParams(max_count=3), ITEMS, ITEMS, id="max-count"),
        pytest.param(PageParams(next_header_name="foo"), ITEMS, ITEMS, id="next-header"),
        pytest.param(
            PageParams(next_property_name="foo", items_property_name="bar"),
            {"bar": ITEMS},
            ITEMS,
            id="next-prop",
        ),
        pytest.param(
            PageParams(page_size_name="foo", page_size_value=5),
            ITEMS,
            ITEMS,
            id="page-name",
        ),
        pytest.param(
            PageParams(item_start_name="foo", item_start_value=7, max_count=2),
            ITEMS,
            ITEMS,
            id="item-start",
        ),
        pytest.param(
            PageParams(page_start_name="foo", page_start_value=7, max_count=2),
            ITEMS,
            ITEMS,
            id="page-start",
            ),
    ]
)
def test_depaginate_single_success(page_params, resp_body, expected):
    url = "http://localhost/foo/bar"
    response = success_response(method="GET", url=url, body=resp_body)

    with (
        mock.patch("openapi_spec_tools.cli_gen._requests.requests.get", return_value=response) as mock_get,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.info") as mock_info,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.debug") as mock_debug,
    ):
        # start with the results
        items = depaginate(page_params, url)
        assert expected == items

        # check the requests call
        assert 1 == mock_get.call_count
        assert url == mock_get.call_args[0][0]

        # look at info logging
        assert 1 == mock_info.call_count
        imsg = mock_info.call_args[0][0]
        assert f"Got {len(items)} items using" in imsg

        # look at debug logging
        assert 2 == mock_debug.call_count
        dmsg = mock_debug.call_args_list[0][0][0]
        assert f"Requesting GET {url}" in dmsg
        dmsg = mock_debug.call_args_list[1][0][0]
        assert "items in" in dmsg


def test_depagination_next_header():
    url = "http://localhost/foo/bar"
    next_url = "http://localhost/items/"
    next_header = "next-response-location"
    resp1 = success_response(body=ITEMS, headers={next_header: next_url})
    resp2 = success_response(body=ITEMS)

    page_params = PageParams(next_header_name=next_header)

    with (
        mock.patch("openapi_spec_tools.cli_gen._requests.requests.get") as mock_get,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.info") as mock_info,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.debug") as mock_debug,
    ):
        mock_get.side_effect = [resp1, resp2]

        # start with the results
        items = depaginate(page_params, url)
        assert ITEMS + ITEMS == items

        # check the requests calls
        assert 2 == mock_get.call_count
        assert url == mock_get.call_args_list[0][0][0]
        assert next_url == mock_get.call_args_list[1][0][0]

        # look at info logging
        assert 1 == mock_info.call_count
        imsg = mock_info.call_args[0][0]
        assert f"Got {len(items)} items using" in imsg

        # look at debug logging
        assert 4 == mock_debug.call_count
        dmsg = mock_debug.call_args_list[0][0][0]
        assert f"Requesting GET {url}" in dmsg
        dmsg = mock_debug.call_args_list[2][0][0]
        assert f"Requesting GET {next_url}" in dmsg


def test_depagination_next_property():
    url = "http://localhost/sna/foo"
    next_url = "http://localhost/foo/bar/"
    item_prop = "items"
    next_prop = "some-prop"
    resp1 = success_response(body={item_prop: ITEMS, next_prop: next_url})
    resp2 = success_response(body={item_prop: ITEMS})

    page_params = PageParams(items_property_name=item_prop, next_property_name=next_prop)

    with (
        mock.patch("openapi_spec_tools.cli_gen._requests.requests.get") as mock_get,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.info") as mock_info,
        mock.patch("openapi_spec_tools.cli_gen._requests.logger.debug") as mock_debug,
    ):
        mock_get.side_effect = [resp1, resp2]

        # start with the results
        items = depaginate(page_params, url)
        assert ITEMS + ITEMS == items

        # check the requests calls
        assert 2 == mock_get.call_count
        assert url == mock_get.call_args_list[0][0][0]
        assert next_url == mock_get.call_args_list[1][0][0]

        # look at info logging
        assert 1 == mock_info.call_count
        imsg = mock_info.call_args[0][0]
        assert f"Got {len(items)} items using" in imsg

        # look at debug logging
        assert 4 == mock_debug.call_count
        dmsg = mock_debug.call_args_list[0][0][0]
        assert f"Requesting GET {url}" in dmsg
        dmsg = mock_debug.call_args_list[2][0][0]
        assert f"Requesting GET {next_url}" in dmsg
