import logging

import pytest

from openapi_spec_tools.cli_gen._logging import LOG_CLASS
from openapi_spec_tools.cli_gen._logging import LogLevel
from openapi_spec_tools.cli_gen._logging import get_logger
from openapi_spec_tools.cli_gen._logging import init_logging


def test_get_logger() -> None:
    log = get_logger()
    assert log.name == LOG_CLASS

    req_logger = get_logger("requests")
    assert req_logger.name == "requests"


@pytest.mark.parametrize(
    ["level", "expected"],
    [
        pytest.param(LogLevel.CRITICAL, logging.CRITICAL, id="critical"),
        pytest.param(LogLevel.ERROR, logging.ERROR, id="error"),
        pytest.param(LogLevel.WARN, logging.WARN, id="warn"),
        pytest.param(LogLevel.INFO, logging.INFO, id="info"),
        pytest.param(LogLevel.DEBUG, logging.DEBUG, id="debug"),
    ]
)
def test_init_logging(level: LogLevel, expected: int) -> None:
    init_logging(level)
    log = get_logger()
    assert LOG_CLASS == log.name
    assert expected == log.level
