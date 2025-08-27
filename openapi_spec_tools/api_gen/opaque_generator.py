"""Declares the OpaqueApiGenerator class."""
from typing import Any

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class OpaqueApiGenerator(ApiGenerator):
    """Generates an API with opaque bodies.

    The body (when present) is handled as a blob, so there are not manipulations to create the
    body -- it is just passed through to the request function (typically a POST).
    """

    def op_body_arguments(self, body_params: dict[str, Any]) -> list[str]:
        """Convert the body parameter dictionary into a list of API function arguments/help."""
        args = []
        if body_params:
            help = body_params.get(OasField.DESCRIPTION)
            reference = body_params.get(OasField.X_REF)
            required_fields = body_params.get(OasField.REQUIRED)
            if help:
                pass
            elif reference:
                help = f"see {reference} for info"
            elif required_fields:
                help = f"required fields: {', '.join(required_fields)}"
            else:
                help = "no info available"
            # default to None, since it may come AFTER option parameters with defaults
            args.append(f"body: Any = None,  # {help}")

        return args


    def function_definition(self, node: LayoutNode) -> str:
        """Generate the function text for the provided LayoutNode."""
        op = self.operations.get(node.identifier)
        method = op.get(OasField.X_METHOD).upper()
        path = op.get(OasField.X_PATH)
        path_params = self.op_params(op, "path")
        query_params = self.params_to_settable_properties(self.op_params(op, "query"))
        header_params = self.params_to_settable_properties(self.op_params(op, "header"))
        _, body_params = self.op_body_schema(op)

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

        self.logger.debug(f"{func_name}({len(path_params)} path, {len(query_params)} query")

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
{self.enum_definitions(path_params, query_params + header_params, {})}
def {func_name}({args_str}) -> Any:
    {self.op_doc_string(op)}# handler for {node.identifier}: {method} {path}
    _l.init_logging(_log_level){deprecation_warning}{user_header_init}
    headers = _r.request_headers(_api_key{self.op_content_header(op)}{user_header_arg})
    url = _r.create_url({self.op_url_params(path)})

    params = {self.op_param_formation(query_params)}

    data = _r.request({', '.join(req_args)})
    return data
"""

