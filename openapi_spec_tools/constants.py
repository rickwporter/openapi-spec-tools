"""Collection of common constants used in multiple files."""

from openapi_spec_tools.types import ContentType

LOG_CLASS = "oas"

NULL_TYPES = {'null', '"null"', "'null'"}
# NOTE: the 'integer' and 'float' values are not standard anymore, but were used a long time ago
SIMPLE_TYPES = {'string', 'boolean', 'number', 'integer', 'float'}
DEFAULT_SUPPORTED_CONTENT = [
    ContentType.APP_JSON,
    ContentType.APP_VJSON,
    ContentType.APP_YAML,
]
