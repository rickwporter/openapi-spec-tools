import logging

import pytest

from oas_tools.cli_gen.logging import LOG_CLASS
from oas_tools.cli_gen.logging import LogLevel
from oas_tools.cli_gen.logging import get_logger
from oas_tools.cli_gen.logging import init_logging


def test_get_logger() -> None:
    logger = get_logger()
    assert logger.name == LOG_CLASS

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
    logger = get_logger()
    assert LOG_CLASS == logger.name
    assert expected == logger.level
