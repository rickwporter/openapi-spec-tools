"""Declares the FlatApiGenerator class that produces functions analogous to the CLI.

The bodies are "unrolled" to individual parameters (as best as possible), and passed as
parameters into the functions.
"""
from typing import Any

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class FlatApiGenerator(ApiGenerator):
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

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
