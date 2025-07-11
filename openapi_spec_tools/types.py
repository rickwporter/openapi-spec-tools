"""Collection of types used throughout the project."""
from enum import Enum


class OasField(str, Enum):
    """Collection of OpenAPI specification fields."""

    ALL_OF = "allOf"
    ANY_OF = "anyOf"
    COMPONENTS = "components"
    CONTENT = "content"
    DEFAULT = "default"
    DEPRECATED = "deprecated"
    DESCRIPTION = "description"
    ENUM = "enum"
    FORMAT = "format"
    IN = "in"
    ITEMS = "items"
    MAX = "maximum"
    MIN = "minimum"
    NAME = "name"
    NULLABLE = "nullable"
    ONE_OF = "oneOf"
    OP_ID = "operationId"
    PARAMS = "parameters"
    PATHS = "paths"
    PROPS = "properties"
    READ_ONLY = "readOnly"
    REFS = "$ref"
    REQ_BODY = "requestBody"
    REQUIRED = "required"
    RESPONSES = "responses"
    SCHEMA = "schema"
    SCHEMAS = "schemas"
    SERVERS = "servers"
    SUMMARY = "summary"
    TAGS = "tags"
    TYPE = "type"
    URL = "url"

    X_DEPRECATED = "x-deprecated"
    X_COLLECT = "x-collection"
    X_FIELD = "x-field"
    X_METHOD = "x-method"
    X_PARENT = "x-parent"
    X_PATH = "x-path"
    X_PATH_PARAMS = "x-path-params"
    X_REF = 'x-reference'


class ContentType(str, Enum):
    """Common HTTP content types."""

    APP_JSON = "application/json"
    APP_OCTETS = "application/octet-stream"
    APP_PDF = "application/pdf"
    APP_XML = "application/xml"
    APP_ZIP = "application/zip"
