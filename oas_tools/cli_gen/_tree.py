from enum import Enum
from typing import Optional

INDENT = "  "


class TreeDisplay(str, Enum):
    HELP = "help"
    FUNCTION = "function"
    OPERATION = "operation"
    PATH = "path"
    ALL = "all"


class TreeField(str, Enum):
    OPERATIONS = "operations"
    DESCRIPTION = "description"

    NAME = "name"
    OP_ID = "operationId"
    METHOD = "method"
    HELP = "help"
    PATH = "path"
    SUB_CMD = "subcommandId"
    FUNC = "function"
    MODULE = "module"


class TreeNode:
    def __init__(
        self,
        name: str,
        help: Optional[str] = None,
        operation: Optional[str] = None,
        function: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        children: Optional[list] = None,
    ):
        self._name = name
        self._help = help
        self._operation = operation
        self._function = function
        self._method = method
        self._path = path
        self._children = children or []

    def name(self) -> str:
        return self._name or ''

    def children(self) -> list:
        return self._children

