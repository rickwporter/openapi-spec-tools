"""OpenAPI field names for tests.

Values match ``OasField``. A few names stay short to match existing tests:
``SUM``, ``DESC``, ``DEF``, ``COLLECT``, and ``SINGLE``.
"""

from openapi_spec_tools.types import OasField

ADDITIONAL_PROPS = OasField.ADDITIONAL_PROPS.value
ALL_OF = OasField.ALL_OF.value
ANY_OF = OasField.ANY_OF.value
COMPONENTS = OasField.COMPONENTS.value
CONTENT = OasField.CONTENT.value
DEF = OasField.DEFAULT.value
DEPRECATED = OasField.DEPRECATED.value
DESC = OasField.DESCRIPTION.value
ENUM = OasField.ENUM.value
FORMAT = OasField.FORMAT.value
HEADERS = OasField.HEADERS.value
IN = OasField.IN.value
INFO = OasField.INFO.value
ITEMS = OasField.ITEMS.value
MAX = OasField.MAX.value
MIN = OasField.MIN.value
MIN_ITEMS = OasField.MIN_ITEMS.value
NAME = OasField.NAME.value
NULLABLE = OasField.NULLABLE.value
ONE_OF = OasField.ONE_OF.value
OP_ID = OasField.OP_ID.value
PARAMS = OasField.PARAMS.value
PATHS = OasField.PATHS.value
PROPS = OasField.PROPS.value
READ_ONLY = OasField.READ_ONLY.value
REFS = OasField.REFS.value
REQ_BODY = OasField.REQ_BODY.value
REQUIRED = OasField.REQUIRED.value
RESPONSES = OasField.RESPONSES.value
SCHEMA = OasField.SCHEMA.value
SCHEMAS = OasField.SCHEMAS.value
SERVERS = OasField.SERVERS.value
SUM = OasField.SUMMARY.value
TAGS = OasField.TAGS.value
TYPE = OasField.TYPE.value
URL = OasField.URL.value

COLLECT = OasField.X_COLLECT.value
X_DEPRECATED = OasField.X_DEPRECATED.value
X_ENUM = OasField.X_ENUM.value
X_FIELD = OasField.X_FIELD.value
X_METHOD = OasField.X_METHOD.value
X_PARENTS = OasField.X_PARENTS.value
X_PATH = OasField.X_PATH.value
X_PATH_PARAMS = OasField.X_PATH_PARAMS.value
X_REF = OasField.X_REF.value
SINGLE = OasField.X_SINGLE.value
