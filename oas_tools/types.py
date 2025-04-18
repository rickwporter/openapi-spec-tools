from enum import Enum


class OasField(str, Enum):
    ANY_OF = "anyOf"
    COMPONENTS = "components"
    CONTENT = "content"
    DEFAULT = "default"
    DESCRIPTION = "description"
    FORMAT = "format"
    IN = "in"
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

    X_METHOD = "x-method"
    X_PATH = "x-path"
    X_PATH_PARAMS = "x-path-params"


class ContentType(str, Enum):
    APP_JSON = "application/json"
    APP_OCTETS = "application/octet-stream"
    APP_PDF = "application/pdf"
    APP_XML = "application/xml"
    APP_ZIP = "application/zip"
