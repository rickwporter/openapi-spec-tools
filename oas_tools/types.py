from enum import Enum


class OasField(str, Enum):
    ANY_OF = "anyOf"
    COMPONENTS = "components"
    DESCRIPTION = "description"
    IN = "in"
    NAME = "name"
    NULLABLE = "nullable"
    ONE_OF = "oneOf"
    OP_ID = "operationId"
    PARAMS = "parameters"
    PATHS = "paths"
    PROPS = "properties"
    REFS = "$ref"
    REQUIRED = "required"
    RESPONSES = "responses"
    SCHEMA = "schema"
    SCHEMAS = "schemas"
    SUMMARY = "summary"
    TAGS = "tags"
    TYPE = "type"

    X_METHOD = "x-method"
    X_PATH = "x-path"
    X_PATH_PARAMS = "x-path-params"
