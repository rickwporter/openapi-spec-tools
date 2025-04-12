import importlib.metadata
import json
from datetime import datetime
from typing import Any
from typing import Optional

import requests

from oas_tools.cli_gen._logging import get_logger

GET = "GET"

logger = get_logger()


def create_url(host_or_base_url: str, *args) -> str:
    """
    Creates a URL from the arguements.

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
    """
    Creates a set of request headers based on the arguments.

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
    """On a bad response, attempts to get more details for the exception."""
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
    headers: dict[str, Any] = {},
    params: dict[str, Any] = {},
    body: Optional[dict[str, Any]] = None,
    timeout: Optional[int] = None,
    **kwargs, # allows passing through additional named parameters
) -> Any:
    pretty_url = url + _pretty_params(params)
    logger.debug(f"Requesting {method} {pretty_url}")
    start = datetime.now()
    response = requests.request(method, url, params=params, headers=headers, json=body, timeout=timeout, **kwargs)
    delta = datetime.now() - start
    logger.info(f"Got {response.status_code} response from {method} {pretty_url} in {delta.total_seconds()}")

    raise_for_error(response)

    # now that we've stopped the clock, let's inspect the body before throwing exceptions
    result = None
    if response.content:
        try:
            result = response.json()
            # logger.info(f"{method} {pretty_url} body:\n{json.dump(result, indent=2, sort_keys=False)}")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode {method} {pretty_url} response")

    return result
