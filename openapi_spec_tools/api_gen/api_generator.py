"""Declares the Generator class that is used for most of the CLi generation capability."""
from typing import Any

from openapi_spec_tools.base_gen.base_generator import BaseGenerator
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class ApiGenerator(BaseGenerator):
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(self, package_name: str, oas: dict[str, Any]):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
        super().__init__(oas)
        self.package_name = package_name
        self.env_host = "API_HOST"
        self.env_key = "API_KEY"
        self.env_timeout = "API_TIMEOUT"
        self.env_log_level = "API_LOG_LEVEL"

    def property_help(self, prop: dict[str, Any]) -> str:
        """Get the short help string for the specified property."""
        text = prop.get(OasField.SUMMARY) or prop.get(OasField.DESCRIPTION)
        if not text:
            return ""

        if len(text) > self.max_help_length:
            text = text.split(". ")[0].strip()[:self.max_help_length]

        return f"  # {simple_escape(text)}"

    def standard_imports(self) -> str:
        """Get the standard imports for all CLI modules."""
        return f"""
from datetime import date  # noqa: F401
from datetime import datetime  # noqa: F401
from enum import Enum  # noqa: F401
from typing import Any
from typing import Optional  # noqa: F401

from {self.package_name} import _environment as _e  # noqa: F401
from {self.package_name} import _logging as _l  # noqa: F401
from {self.package_name} import _requests as _r  # noqa: F401
"""

    def command_infra_arguments(self, command: LayoutNode) -> list[str]:
        """Get the standard CLI function arguments to the command."""
        args = [
            f'_api_host: str = _e.env_str({quoted(self.env_host)}, {quoted(self.default_host)}),  # host URL',
            f'_api_key: str = _e.env_str({quoted(self.env_key)}),  # API key for bearer authentication',
            f'_api_timeout: int = _e.env({quoted(self.env_timeout)}, 5),  # timeout for operation',
            f'_log_level: str = _e.env({quoted(self.env_log_level)}, "info"),  # log level',
        ]
        return args

    def property_to_argument(self, prop: dict[str, Any], allow_required: bool) -> str:
        """Convert a property into a argument."""
        prop_name = prop.get(OasField.NAME)
        var_name = self.variable_name(prop_name)
        required = prop.get(OasField.REQUIRED, False)
        schema_default = prop.get(OasField.DEFAULT)
        collection = COLLECTIONS.get(prop.get(OasField.X_COLLECT))
        py_type = self.get_parameter_pytype(prop)
        if not py_type:
            # log an error and use 'Any'
            self.logger.error(f"Unable to determine Python type for {prop}")
            py_type = 'Any'

        if collection:
            py_type = f"{collection}[{py_type}]"
        if allow_required and required and schema_default is None:
            arg_default = ""
        else:
            if not required:
                py_type = f"Optional[{py_type}]"
            if schema_default is None:
                arg_default = " = None"
            elif collection and not isinstance(schema_default, list):
                arg_default = f" = [{maybe_quoted(schema_default)}]"
            else:
                arg_default = f" = {maybe_quoted(schema_default)}"

        help = self.property_help(prop)

        return f'{var_name}: {py_type}{arg_default},{help}'

    def op_path_arguments(self, path_params: list[dict[str, Any]]) -> list[str]:
        """Convert all path parameters into a tuple of argument and help."""
        args = []
        for param in path_params:
            arg = self.property_to_argument(param, allow_required=True)
            args.append(arg)

        return args

    def op_query_arguments(self, query_params: list[dict[str, Any]]) -> list[str]:
        """Convert query parameters to a tuple of argument and help."""
        args = []
        for param in query_params:
            arg = self.property_to_argument(param, allow_required=False)
            args.append(arg)

        return args

    def op_body_arguments(self, body_params: list[dict[str, Any]]) -> list[str]:
        """Convert the body parameters dictionary into a list of API function arguments/help."""
        args = []
        for prop_name, prop_data in body_params.items():
            prop_data[OasField.NAME.value] = prop_name
            arg = self.property_to_argument(prop_data, allow_required=False)
            args.append(arg)

        return args


    def function_definition(self, node: LayoutNode) -> str:
        """Generate the function text for the provided LayoutNode."""
        op = self.operations.get(node.identifier)
        method = op.get(OasField.X_METHOD).upper()
        path = op.get(OasField.X_PATH)
        path_params = self.op_params(op, "path")
        query_params = self.params_to_settable_properties(self.op_params(op, "query"))
        header_params = self.params_to_settable_properties(self.op_params(op, "header"))
        body_params = self.op_body_settable_properties(op)

        req_args = []
        req_args.append(quoted(method))
        req_args.extend([
            "url",
            "headers=headers",
            "params=params",
        ])
        if body_params:
            req_args.append("body=body")
        req_args.append("timeout=_api_timeout")

        deprecation_warning = ""
        deprecated = op.get(OasField.DEPRECATED, False)
        x_deprecated = op.get(OasField.X_DEPRECATED, None)
        if x_deprecated:
            message = f"{node.identifier} was deprecated in {x_deprecated}, and should not be used."
            deprecation_warning = SEP1 + f'_l.logger().warning("{message}")'
        elif deprecated:
            message = f"{node.identifier} is deprecated and should not be used."
            deprecation_warning = SEP1 + f'_l.logger().warning("{message}")'

        func_name = self.function_name(node.identifier)
        func_args = []
        func_args.extend(self.op_path_arguments(path_params))
        func_args.extend(self.op_query_arguments(query_params))
        func_args.extend(self.op_query_arguments(header_params))
        func_args.extend(self.op_body_arguments(body_params))
        func_args.extend(self.command_infra_arguments(node))
        args_str = SEP1 + SEP1.join(func_args) + NL

        self.logger.debug(f"{func_name}({len(path_params)} path, {len(query_params)} query, {len(body_params)} body)")

        user_header_init = ""
        user_header_arg = ""
        if header_params:
            user_header_arg = ", **user_headers"
            lines = ["user_headers = {}"]
            for p in header_params:
                name = p.get(OasField.NAME)
                var_name = self.variable_name(name)
                lines.append(f"if {var_name} is not None:")
                lines.append(f"    user_headers[{quoted(name)}] = {var_name}")
            user_header_init = NL + SEP1 + SEP1.join(lines) + NL

        return f"""
{self.enum_definitions(path_params, query_params + header_params, body_params)}
def {func_name}({args_str}) -> Any:
    {self.op_doc_string(op)}# handler for {node.identifier}: {method} {path}
    _l.init_logging(_log_level){deprecation_warning}{user_header_init}
    headers = _r.request_headers(_api_key{self.op_content_header(op)}{user_header_arg})
    url = _r.create_url({self.op_url_params(path)})

    params = {self.op_param_formation(query_params)}{self.op_body_formation(body_params)}

    data = _r.request({', '.join(req_args)})
    return data
"""

