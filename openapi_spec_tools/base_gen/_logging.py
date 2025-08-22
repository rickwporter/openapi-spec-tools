import logging
from enum import Enum
from typing import Optional

LOG_CLASS = "cli"
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s %(message)s"
LOG_DATE_FMT = "%Y-%m-%d %I:%M:%S %p"


class LogLevel(str, Enum):
    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"


def get_logger(name: Optional[str] = LOG_CLASS) -> logging.Logger:
    return logging.getLogger(name=name)


def init_logging(level: LogLevel, name: Optional[str] = LOG_CLASS) -> logging.Logger:
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATE_FMT)
    logger = get_logger(name)
    logger.setLevel(level.upper())
    return logger
