"""Declares the LayoutGenerator for inferring a layout from an OpenAPI specification."""
from typing import Any
from typing import Optional
from typing import Union

from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames
from openapi_spec_tools.layout.utils import DEFAULT_START
from openapi_spec_tools.layout.utils import path_to_parts
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField

CREATE = "create"
DELETE = "delete"
LIST = "list"
SET = "set"
SHOW = "show"
UPDATE = "update"

DEFAULT_HELP = "CLI to manage your application"
DEFAULT_MAX_HELP_LENGTH = 80
DEFAULT_SUPPORTED_CONTENT = [
    ContentType.APP_JSON,
    ContentType.APP_YAML,
]
DEFAULT_OPERATION_MAP = {
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


def _to_list(data: Union[None, str, list[str]]) -> list[str]:
    """Convert the data (either a str or list[str]) to a list[str]."""
    if not data:
        return []
    return [data] if isinstance(data, str) else data


class LayoutGenerator:
    """Generates a layout from the OpenAPI spec."""

    def __init__(
        self,
        oas: dict[str, Any],
        max_help_length: int = DEFAULT_MAX_HELP_LENGTH,
        supported_content: list[ContentType] = DEFAULT_SUPPORTED_CONTENT,
        common_operations: dict[str, str] = DEFAULT_OPERATION_MAP,
        page_size_params: Union[None, str, list[str]] = None,
        page_start_params: Union[None, str, list[str]] = None,
        item_start_params: Union[None, str, list[str]] = None,
        items_properties: Union[None, str, list[str]] = None,
        next_properties: Union[None, str, list[str]] = None,
        next_headers: Union[None, str, list[str]] = None,
    ):
        """Initialize the generator with internal values."""
        self.paths = oas.get(OasField.PATHS, {})
        self.components = oas.get(OasField.COMPONENTS, {})
        self.description = oas.get(OasField.INFO, {}).get(OasField.DESCRIPTION)
        self.max_help_length = max_help_length
        self.supported_response_content = supported_content
        self.common_ops = common_operations

        self.page_size_params = _to_list(page_size_params)
        self.page_start_params = _to_list(page_start_params)
        self.item_start_params = _to_list(item_start_params)
        self.items_properties = _to_list(items_properties)
        self.next_properties = _to_list(next_properties)
        self.next_headers = _to_list(next_headers)

    @staticmethod
    def parts_to_commands(path_parts: list[str]) -> list[str]:
        """Convert list of path parts to list of commands."""
        return [to_snake_case(part).replace("_", "-") for part in path_parts]

    @staticmethod
    def commands_to_identifier(commands: list[str]) -> str:
        """Convert the list of commands into an identifier."""
        return "_".join([to_snake_case(x).replace("-", "_") for x in commands])

    @staticmethod
    def find_parameter(params: list[dict[str, Any]], name: str) -> Optional[dict[str, Any]]:
        """Find the parameter matching the provided name (if possible)."""
        for p in params:
            if p.get(OasField.NAME) == name:
                return p
        return None

    def short_help(self, help: str) -> str:
        """Shortens a long help string into something more managable."""
        if len(help) > self.max_help_length:
            help = help.split(". ")[0].strip()[:self.max_help_length] + '...'
        return simple_escape(help)

    def get_model(self, full_name: str) -> dict[str, Any]:
        """Get the model from reference name."""
        keys = [
            item for item in full_name.split('/')
            if item and item not in ['#', OasField.COMPONENTS.value]
        ]
        if not keys:
            return None

        value = self.components
        for k in keys:
            value = value.get(k)
            if not value:
                return None

        return value

    def get_response_headers(self, op_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Get the response headers (if any)."""
        responses = op_data.get(OasField.RESPONSES, {})
        for code, data in responses.items():
            # only look at successful responses
            if not code.startswith("2"):
                continue

            headers = data.get(OasField.HEADERS)
            if headers:
                return headers

        return None

    def get_response_body(self, op_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Get the response body data (if any)."""
        responses = op_data.get(OasField.RESPONSES, {})
        for code, data in responses.items():
            # only look at successful responses
            if not code.startswith("2"):
                continue

            content_data = data.get(OasField.CONTENT, {})
            for content_type, content_details in content_data.items():
                if content_type not in self.supported_response_content:
                    continue

                schema = content_details.get(OasField.SCHEMA)

                # the info is directly in the schema
                if set(schema.keys()) != {OasField.REFS.value}:
                    return schema

                model = self.get_model(schema.get(OasField.REFS))
                return model

        return None

    def suggest_command(self, op_data: dict[str, Any]) -> str:
        """Suggest a command based on the method and operationId."""
        # the patch/put methods often have similar operationId's so handle those first
        op_id = op_data.get(OasField.OP_ID)
        _method = op_data.get(OasField.X_METHOD).lower()
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
                child = LayoutNode(
                    command=command,
                    identifier=self.commands_to_identifier(parent_cmds),
                    description=description,
                )
                current.children.append(child)
            current = child

        identifier = self.commands_to_identifier(commands)
        description = "Manage " + " ".join(commands)
        path_node = LayoutNode(command=commands[-1], identifier=identifier, description=description)
        current.children.append(path_node)
        return path_node

    def get_pagination(self, op_data: dict[str, Any]) -> Optional[PaginationNames]:
        """Determine pagination parameters from the operation data."""
        args = {}
        params = op_data.get(OasField.PARAMS, [])

        def _param_args(arg_name: str, param_names: list[str]) -> None:
            for name in param_names:
                if self.find_parameter(params, name):
                    args[arg_name] = name
                    return
            return

        _param_args('page_size', self.page_size_params)
        _param_args('page_start', self.page_start_params)
        _param_args('item_start', self.item_start_params)

        body = self.get_response_body(op_data) or {}
        properties = body.get(OasField.PROPS, {})

        def _prop_args(arg_name: str, prop_names: list[str]) -> None:
            for name in prop_names:
                if name in properties:
                    args[arg_name] = name
                    return
            return

        _prop_args('items_property', self.items_properties)
        _prop_args('next_property', self.next_properties)

        headers = self.get_response_headers(op_data) or {}
        for name in self.next_headers:
            if name in headers:
                args['next_header'] = name
                break

        if not args:
            return None

        return PaginationNames(**args)

    def generate(self, prefix: str, description: Optional[str] = None) -> LayoutNode:
        """Create a suggested layout for the provided OpenAPI spec."""
        help = self.short_help(description or self.description or DEFAULT_HELP)
        main = LayoutNode(command=DEFAULT_START, identifier=DEFAULT_START, description=help)

        for path_name, path_data in self.paths.items():
            path_parts = path_to_parts(path_name, prefix)
            commands = self.parts_to_commands(path_parts)

            for method, op_data in path_data.items():
                if method == OasField.PARAMS:
                    continue

                path_node = self.get_or_create_node_with_parents(main, commands)
                op_id = op_data.get(OasField.OP_ID)
                op_data.update({OasField.X_METHOD.value: method})
                command = self.suggest_command(op_data)
                pagination = self.get_pagination(op_data)
                path_node.children.append(
                    LayoutNode(command=command, identifier=op_id, pagination=pagination)
                )
                # sort the children to match layout linting
                path_node.children = sorted(path_node.children, key=lambda x: x.command)

        # finally, sort the main children
        main.children = sorted(main.children, key=lambda x: x.command)

        return main
