"""Declares the LayoutGenerator for inferring a layout from an OpenAPI specification."""
from typing import Any
from typing import Optional

from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
from openapi_spec_tools.layout.utils import DEFAULT_START
from openapi_spec_tools.types import OasField

CREATE = "create"
DELETE = "delete"
LIST = "list"
SET = "set"
SHOW = "show"
UPDATE = "update"


class LayoutGenerator:
    """Generates a layout from the OpenAPI spec."""

    def __init__(self):
        """Initialize the generator with internal values."""
        self.common_ops = {
            "add": CREATE,
            "create": CREATE,
            "post": CREATE,
            "delete": DELETE,
            "remove": DELETE,
            "list": LIST,
            "retrieve": SHOW,
            "get": SHOW,
            "update": UPDATE,
            "patch": UPDATE,
            "put": SET,
        }

    @staticmethod
    def path_to_parts(path_name: str, prefix: str) -> list[str]:
        """Break the path string into parts, and removes the parameterized values."""
        shortened = path_name if not path_name.startswith(prefix) else path_name.replace(prefix, "", 1)
        parts = [
            item.strip()
            for item in shortened.split('/')
            if item.strip() and '{' not in item  # ignore parameters
        ]
        return parts

    @staticmethod
    def parts_to_commands(path_parts: list[str]) -> list[str]:
        """Convert list of path parts to list of commands."""
        return [to_snake_case(part).replace("_", "-") for part in path_parts]

    @staticmethod
    def commands_to_identifier(commands: list[str]) -> str:
        """Convert the list of commands into an identifier."""
        return "_".join([to_snake_case(x).replace("-", "_") for x in commands])

    def suggest_command(self, method: str, op_id: str) -> str:
        """Suggest a command based on the method and operationId."""
        # the patch/put methods often have similar operationId's so handle those first
        _method = method.lower()
        if _method == "put":
            return SET
        if _method == "patch":
            return UPDATE

        operation = to_snake_case(op_id).split('_')
        begin = operation[0]
        if begin in self.common_ops:
            return self.common_ops.get(begin)
        end = operation[-1]
        if end in self.common_ops:
            return self.common_ops.get(end)

        # default to using the method... last resort because get single-item and list use same
        return self.common_ops.get(_method, _method)

    def get_or_create_node_with_parents(self, node: LayoutNode, commands: list[str]) -> LayoutNode:
        """Create the node for the current commands and any required parents."""
        if not commands:
            return node

        existing = node.find(*commands)
        if existing:
            return existing

        current = node
        for cmd_len in range(1, len(commands)):
            parent_cmds = commands[:cmd_len]
            command = parent_cmds[cmd_len - 1]
            child = current.find(command)
            if not child:
                description = "Manage " + " ".join(parent_cmds)
                child = LayoutNode(command, self.commands_to_identifier(parent_cmds), description=description)
                current.children.append(child)
            current = child

        identifier = self.commands_to_identifier(commands)
        description = "Manage " + " ".join(commands)
        path_node = LayoutNode(command=commands[-1], identifier=identifier, description=description)
        current.children.append(path_node)
        return path_node

    def get_pagination(self, op_data: dict[str, Any]) -> Optional[PaginationNames]:
        """Determine pagination parameters from the operation data.

        Intended to be overridden if you want your suggested layout to contain pagination parameters.
        """
        return None

    def generate(self, oas: dict[str, Any], prefix: str) -> LayoutNode:
        """Create a suggested layout for the provided OpenAPI spec."""
        main = LayoutNode(DEFAULT_START, DEFAULT_START, description="CLI to manage your application")

        paths = oas.get(OasField.PATHS, {})
        for path_name, path_data in paths.items():
            path_parts = self.path_to_parts(path_name, prefix)
            commands = self.parts_to_commands(path_parts)

            for method, op_data in path_data.items():
                if method == OasField.PARAMS:
                    continue

                path_node = self.get_or_create_node_with_parents(main, commands)
                op_id = op_data.get(OasField.OP_ID)
                command = self.suggest_command(method, op_id)
                pagination = self.get_pagination(op_data)
                path_node.children.append(
                    LayoutNode(command=command, identifier=op_id, pagination=pagination)
                )
                # sort the children to match layout linting
                path_node.children = sorted(path_node.children, key=lambda x: x.command)

        return main
