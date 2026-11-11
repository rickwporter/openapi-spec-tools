import logging
from enum import Enum

LOG_CLASS = "cli"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %I:%M:%S %p"


class LogLevel(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


def get_logger() -> logging.Logger:
    """Get the logger for LOG_CLASS."""
    return logging.getLogger(name=LOG_CLASS)


def init_logging(level: LogLevel) -> logging.Logger:
    """Initialize the LOG_CLASS logger and sets the level."""
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FMT)
    logger = get_logger()
    logger.setLevel(level.upper())
    return logger
