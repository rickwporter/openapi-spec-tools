"""Declares the PropertyApiGenerator class."""
from copy import deepcopy
from typing import Any

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import shallow
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class PropertyApiGenerator(ApiGenerator):
    """Generates an API with body expanded to the first level of properties."""

    def op_body_top_properties(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get a list of top-level properties for the operation."""
        name, schema = self.op_body_schema(operation)
        if not schema:
            return {}

        return self.model_properties(name, schema)

    def model_properties(self, name: str, schema: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0912
        """Get a list of settable model properties."""
        model = deepcopy(schema)
        body_props = {}

        # start with the base-classes in allOf
        for parent in model.get(OasField.ALL_OF, []):
            reference = parent.get(OasField.REFS, "")
            if reference:
                sub_model = self.get_model(reference)
            else:
                sub_model = deepcopy(parent)
            required_sub = sub_model.get(OasField.REQUIRED, [])
            for sub_name, _sub_data in sub_model.get(OasField.PROPS, {}).items():
                if _sub_data.get(OasField.READ_ONLY):
                    continue

                sub_data = self.update_one_of(sub_name, deepcopy(_sub_data))
                sub_data = self.update_collection(sub_data)
                sub_data = self.update_reference(sub_data)
                sub_data[OasField.REQUIRED.value] = sub_data.get(OasField.REQUIRED) or sub_name in required_sub
                body_props[sub_name] = self.update_enum(sub_data)

        any_of = model.pop(OasField.ANY_OF, None)
        if any_of:
            if len(any_of) != 1:
                self.logger.info(f"Grabbing anyOf[0] item from {name}")
                self.logger.debug(f"{name} anyOf selected: {shallow(any_of[0])}")
            # just grab the first one... not sure this is the best choice, but need to do something
            updated = self.update_one_of(name, deepcopy(any_of[0]))
            updated = self.update_collection(updated)
            updated = self.update_reference(updated)
            model.update(self.update_enum(updated))

        model = self.update_one_of(name, model)
        model = self.update_collection(model)
        model = self.update_reference(model)
        required_props = model.get(OasField.REQUIRED, [])

        # copy the individual properties
        for prop_name, _prop_data in model.get(OasField.PROPS, {}).items():
            if _prop_data.get(OasField.READ_ONLY, False):
                continue

            prop_data = deepcopy(_prop_data)
            prop_data[OasField.REQUIRED.value] = prop_name in required_props
            prop_data = self.update_one_of(prop_name, prop_data)
            prop_data = self.update_collection(prop_data)
            prop_data = self.update_reference(prop_data)

            body_props[prop_name] = self.update_enum(prop_data)

        return body_props

    def op_body_formation(self, properties: dict[str, Any]) -> str:
        """Create body parameter and poulates it when there are body paramters."""
        if not properties:
            return ""

        lines = ["body = {}"]
        for prop_name, prop_data in properties.items():
            var_name = self.variable_name(prop_name)
            deprecated = prop_data.get(OasField.DEPRECATED, False)
            x_deprecated = prop_data.get(OasField.X_DEPRECATED, None)
            dep_msg = ""
            if x_deprecated:
                dep_msg = f"{var_name} was deprecated in {x_deprecated} and should not be used"
            elif deprecated:
                dep_msg = f"{var_name} is deprecated and should not be used"

            if prop_data.get(OasField.REQUIRED):
                lines.append(f'body["{prop_name}"] = {var_name}')
            else:
                lines.append(f'if {var_name} is not None:')
                if dep_msg:
                    lines.append(f'    _l.logger().warning("{dep_msg}")')
                lines.append(f'    body["{prop_name}"] = {var_name}')

        return SEP1 + SEP1.join(lines)

    def function_definition(self, node: LayoutNode) -> str:
        """Generate the function text for the provided LayoutNode."""
        op = self.operations.get(node.identifier)
        method = op.get(OasField.X_METHOD).upper()
        path = op.get(OasField.X_PATH)
        path_params = self.op_params(op, "path")
        query_params = self.params_to_settable_properties(self.op_params(op, "query"))
        header_params = self.params_to_settable_properties(self.op_params(op, "header"))
        body_params = self.op_body_top_properties(op)

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
{self.enum_definitions(path_params, query_params + header_params, body_params)}
def {func_name}({args_str}) -> Any:
    {self.op_doc_string(op)}# handler for {node.identifier}: {method} {path}
    {self.init_infra_args(op)}

    _l.init_logging(_log_level){deprecation_warning}{user_header_init}
    headers = _r.request_headers(_api_key{self.op_content_header(op)}{user_header_arg})
    url = _r.create_url({self.op_url_params(path)})

    params = {self.op_param_formation(query_params)}{self.op_body_formation(body_params)}

    data = _r.request({', '.join(req_args)})
    return data
"""

