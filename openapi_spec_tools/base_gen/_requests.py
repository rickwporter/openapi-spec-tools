"""Implementation for sending/receiving REST requests.

Uses standard Python requests module, but provids a unfied interface with consistent
logging, etc.
"""
import importlib.metadata
import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Optional

import requests
import yaml

from openapi_spec_tools.base_gen._logging import get_logger

GET = "GET"
EXTENSION_MAP = {
    "application/java-archive": "jar",
    "application/octet-stream": "bin",
    "application/pdf": "pdf",
    "application/xhtml+xml": "xhtml",
    "application/x-shockwave-flash": "swf",
    "application/ld+json": "",
    "application/xml": "xml",
    "application/zip": "zip",
    "audio/mpeg": "mpeg",
    "audio/x-ms-wma": "wma",
    "audio/vnd.rn-realaudio": "ra",
    "audio/x-wav": "wav",
    "image/gif": "gif",
    "image/jpeg": "jpeg",
    "image/png": "png",
    "image/tiff": "tif",
    "image/vnd.microsoft.icon": "ico",
    "image/x-icon": "ico",
    "image/svg+xml": "svg",
    "text/css": "css",
    "text/csv": "csv",
    "text/html": "html",
    "text/javascript": "js",
    "text/xml": "xml",
    "video/mpeg": "mpeg",
    "video/mp4": "mp4",
    "video/quicktime": "qt",
    "video/x-ms-wmv": "wmv",
    "application/vnd.android.package-archive": "apk",
    "application/vnd.oasis.opendocument.text": "txt",
    "application/vnd.ms-excel": "xls",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xls",
    "application/vnd.ms-powerpoint": "ppt",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "xml",
    "application/msword": "doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "doc",
    "application/vnd.mozilla.xul+xml": "xml",
}

logger = get_logger()


@dataclass
class PageParams:
    """Holds optional pagination parameter names and values."""

    # page_size_* dictate the limit per request
    page_size_value: Optional[int] = None
    page_size_name: Optional[str] = None

    # page_start_* dictate the starting point when it is in page increments
    page_start_value: Optional[int] = None
    page_start_name: Optional[str] = None

    # offset_start_* dictate the starting point when it is specified in item increments
    item_start_value: Optional[int] = None
    item_start_name: Optional[str] = None

    # max_count specifies the maximim number of items to fetch
    max_count: Optional[int] = None

    # items property specifies the property name to pull out the data from
    items_property_name: Optional[str] = None

    # locations for next url
    next_header_name: Optional[str] = None
    next_property_name: Optional[str] = None


def create_url(host_or_base_url: str, *args) -> str:
    """Create a URL from the arguements.

    Takes care of the slash manipulations.
    """
    if not host_or_base_url:
        raise ValueError("Missing host")

    if "://" not in host_or_base_url:
        host_or_base_url = "https://" + host_or_base_url.strip("/")

    host_or_base_url = host_or_base_url.rstrip("/")
    parts = [str(x).strip("/") for x in args]
    return "/".join([host_or_base_url] + parts) + "/"


def request_headers(
    api_key: Optional[str] = None,
    content_type: Optional[str] = None,
    **kwargs,
) -> dict[str, str]:
    """Create a set of request headers based on the arguments.

    The API Key and content type are optional, but likely desired.
    """
    module_name = __name__.rsplit(".", 3)[0]
    module_version = importlib.metadata.version(module_name)
    headers = {
        "User-Agent": f"{module_name}/{module_version}"
    }
    if kwargs:
        headers.update(**kwargs)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def raise_for_error(response: requests.Response) -> None:
    """Raise an exception for a bad response.

    Provide meaningful details for the exception.
    """
    if response.ok:
        return

    message = f"{response.reason} ({response.status_code})"
    try:
        details = response.json()
        if details:
            if isinstance(details, dict):
                details = "; ".join(f"{k}: {v}" for k, v in details.items())
            message += f": {details}"
            logger.info(f"{response.request.method} {response.request.url} body:\n{details}")
    except json.JSONDecodeError:
        pass

    raise requests.HTTPError(message, response=response)


def _pretty_params(params: Optional[dict[str, Any]]) -> str:
    if not params:
        return ""

    return "?" + "&".join(f"{k}={v}" for k, v in params.items())


def request(
    method: str,
    url: str,
    headers: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    body: Optional[dict[str, Any]] = None,
    timeout: Optional[int] = None,
    **kwargs,  # allows passing through additional named parameters
) -> Any:
    """Perform the specified REST request."""
    headers = headers or {}
    params = params or {}
    pretty_url = url + _pretty_params(params)
    logger.debug(f"Requesting {method} {pretty_url}")
    start = datetime.now()
    response = requests.request(method, url, params=params, headers=headers, json=body, timeout=timeout, **kwargs)
    delta = datetime.now() - start
    logger.info(f"Got {response.status_code} response from {method} {pretty_url} in {delta.total_seconds()}")

    raise_for_error(response)

    if not response.content:
        return None

    encoding = response.encoding or "utf-8"
    content_type = response.headers.get("Content-type", "application/json")
    if content_type == "application/json":
        try:
            return response.json()
        except json.JSONDecodeError:
            logger.error(f"Failed to decode {method} {pretty_url} response")
            return None

    if content_type == "application/yaml":
        try:
            content = response.content.decode(encoding=encoding, errors="ignore")
            return yaml.safe_load(content)
        except Exception as ex:
            logger.error(f"Failed to decode {method} {pretty_url} response: {ex}")
            return None

    if content_type == "text/plain":
        return response.content.decode(encoding=encoding, errors="ignore")

    extension = EXTENSION_MAP.get(content_type)
    if extension:
        filename = f"output.{extension}"
        with open(filename, "wb") as fp:
            fp.write(response.content)
        return f"Wrote content to {filename}"

    logger.error(f"Unhandled content-type={content_type}")
    return None


def depaginate(
    page_params: PageParams,
    url: str,
    headers: Optional[dict[str, Any]] = None,
    params: Optional[dict[str, Any]] = None,
    timeout: Optional[int] = None,
) -> Any:
    """Get a list of items that may be chunked across several pages."""
    items = []
    total_time = timedelta()
    _url = url
    _params = deepcopy(params or {})
    _headers = deepcopy(headers or {})
    pretty_url = None
    next_url = None

    page_start = page_params.page_start_value or 0
    page_count = 0
    item_start = page_params.item_start_value or 0
    item_count = 0
    page_size = page_params.page_size_value or 0
    max_count = page_params.max_count
    if max_count:
        page_size = min(page_size, max_count)

    if page_params.page_size_name and page_params.page_size_value is not None:
        _params[page_params.page_size_name] = page_size

    while _url:
        if next_url:
            pretty_url = next_url
            _params = {}
        else:
            if page_params.page_start_name:
                _params[page_params.page_start_name] = page_start + page_count
            if page_params.item_start_name:
                _params[page_params.item_start_name] = item_start + item_count
            pretty_url = _url + _pretty_params(_params)

        logger.debug(f"Requesting {GET} {pretty_url} count={page_count + 1}")
        start = datetime.now()
        response = requests.get(_url, params=deepcopy(_params), headers=_headers, timeout=timeout)
        delta = datetime.now() - start

        raise_for_error(response)

        # update list with current items from the response
        current = response.json()
        if page_params.items_property_name:
            current = current.get(page_params.items_property_name)
        items.extend(current)

        # update the URL from the provided info
        if page_params.next_header_name:
            _url = response.headers.get(page_params.next_header_name)
            next_url = _url
        elif page_params.next_property_name:
            _url = response.json().get(page_params.next_property_name)
            next_url = _url

        # some book-keeping
        curr_len = len(current)
        total_time += delta
        page_count += 1
        item_count += curr_len
        logger.debug(f"Got {curr_len} items in {delta.total_seconds()}")

        if (
            curr_len == 0  # no items provided (even when no page size or max count)
            or (page_size and curr_len < page_size)  # did not get a full page
            or (max_count and item_count >= max_count)  # reached max items
        ):
            break

    logger.info(f"Got {len(items)} items using {page_count} requests in {total_time.total_seconds()}")
    return items
