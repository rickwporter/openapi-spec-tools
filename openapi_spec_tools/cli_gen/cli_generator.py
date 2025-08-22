"""Declares the Generator class that is used for most of the CLi generation capability."""
import logging
from typing import Any
from typing import Optional

import yaml

from openapi_spec_tools.base_gen.base_generator import BaseGenerator
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.constants import SEP2
from openapi_spec_tools.base_gen.utils import is_case_sensitive
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.cli_gen._tree import TreeField
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class CliGenerator(BaseGenerator):
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(self, package_name: str, oas: dict[str, Any], logger: Optional[logging.Logger] = None):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
        super().__init__(oas=oas, logger=logger)
        self.package_name = package_name

    def standard_imports(self) -> str:
        """Get the standard imports for all CLI modules."""
        return f"""
from datetime import date  # noqa: F401
from datetime import datetime  # noqa: F401
from enum import Enum  # noqa: F401
from pathlib import Path
from typing import Annotated  # noqa: F401
from typing import Optional  # noqa: F401

import typer

from {self.package_name} import _arguments as _a
from {self.package_name} import _display as _d  # noqa: F401
from {self.package_name} import _exceptions as _e  # noqa: F401
from {self.package_name} import _logging as _l  # noqa: F401
from {self.package_name} import _requests as _r  # noqa: F401
from {self.package_name} import _tree as _t
"""

    def subcommand_imports(self, subcommands: list[LayoutNode]) -> str:
        """Get the imports needed for the subcommands/children."""
        imports = [
            f"from {self.package_name}.{to_snake_case(n.identifier)} import app as {to_snake_case(n.identifier)}"
            for n in subcommands
        ]
        # NOTE: use sorted to avoid issue if user has used unsorted sub-commands
        return NL.join(sorted(imports))

    def app_definition(self, node: LayoutNode) -> str:
        """Get the main typer application/start point, and "overhead" of dealing with children."""
        result = f"""

app = typer.Typer(no_args_is_help=True, help="{simple_escape(node.description)}")
"""
        for child in node.subcommands():
            result += f"""\
app.add_typer({to_snake_case(child.identifier)}, name="{child.command}")
"""
        result += "\n"

        return result

    def main(self) -> str:
        """Get the text for the main function in the CLI file."""
        return """

if __name__ == "__main__":
    app()
"""

    def command_infra_arguments(self, command: LayoutNode) -> list[str]:
        """Get the standard CLI function arguments to the command."""
        args = [
            f'_api_host: _a.ApiHostOption = "{self.default_host}"',
            '_api_key: _a.ApiKeyOption = None',
            '_api_timeout: _a.ApiTimeoutOption = 5',
            '_log_level: _a.LogLevelOption = _a.LogLevel.WARN',
            '_out_fmt: _a.OutputFormatOption = _a.OutputFormat.TABLE',
            '_out_style: _a.OutputStyleOption = _a.OutputStyle.ALL',
        ]
        if command.summary_fields:
            args.append('_details: _a.DetailsOption = False')
        if command.pagination:
            args.append('_max_count: _a.MaxCountOption = None')
        return args

    def property_to_argument(self, prop: dict[str, Any], allow_required: bool) -> str:
        """Convert a property into a typer argument."""
        prop_name = prop.get(OasField.NAME)
        var_name = self.variable_name(prop_name)
        description = prop.get(OasField.DESCRIPTION) or ""
        required = prop.get(OasField.REQUIRED, False)
        deprected = prop.get(OasField.DEPRECATED, False)
        x_deprecated = prop.get(OasField.X_DEPRECATED, None)
        schema_default = prop.get(OasField.DEFAULT)
        collection = COLLECTIONS.get(prop.get(OasField.X_COLLECT))
        enum_values = prop.get(OasField.ENUM)
        py_type = self.get_parameter_pytype(prop)
        if not py_type:
            # log an error and use 'Any'
            self.logger.error(f"Unable to determine Python type for {prop}")
            py_type = 'Any'

        typer_args = []
        if py_type in ("int", "float"):
            schema_min = prop.get(OasField.MIN)
            if schema_min is not None:
                typer_args.append(f"min={schema_min}")
            schema_max = prop.get(OasField.MAX)
            if schema_max is not None:
                typer_args.append(f"max={schema_max}")
        if collection:
            py_type = f"{collection}[{py_type}]"
        if allow_required and required and schema_default is None:
            typer_type = 'typer.Argument'
            typer_args.append('show_default=False')
            arg_default = ""
        else:
            typer_type = 'typer.Option'
            if prop_name.lower() in self.reserved:
                # when the variable name is changed to avoid conflict with builtins, add an option with "original" name
                typer_args.insert(0, quoted(self.option_name(prop_name)))
            if not required:
                py_type = f"Optional[{py_type}]"
            if schema_default is None:
                arg_default = " = None"
                typer_args.append('show_default=False')
            elif collection and not isinstance(schema_default, list):
                arg_default = f" = [{maybe_quoted(schema_default)}]"
            else:
                arg_default = f" = {maybe_quoted(schema_default)}"
        if enum_values:
            case_sensitive = is_case_sensitive(enum_values)
            typer_args.append(f"case_sensitive={case_sensitive}")
        if deprected or x_deprecated:
            typer_args.append("hidden=True")
        if description:
            typer_args.append(f'help="{simple_escape(description)}"')
        comma = ', '

        typer_decl = f"{typer_type}({comma.join(typer_args)}"
        return f'{var_name}: Annotated[{py_type}, {typer_decl})]{arg_default}'

    def op_path_arguments(self, path_params: list[dict[str, Any]]) -> list[str]:
        """Convert all path parameters into typer arguments."""
        args = []
        for param in path_params:
            arg = self.property_to_argument(param, allow_required=True)
            args.append(arg)

        return args

    def op_query_arguments(self, query_params: list[dict[str, Any]]) -> list[str]:
        """Convert query parameters to typer arguments."""
        args = []
        for param in query_params:
            arg = self.property_to_argument(param, allow_required=False)
            args.append(arg)

        return args

    def op_body_arguments(self, body_params: list[dict[str, Any]]) -> list[str]:
        """Convert the body parameters dictionary into a list of CLI function arguments."""
        args = []
        for prop_name, prop_data in body_params.items():
            prop_data[OasField.NAME.value] = prop_name
            arg = self.property_to_argument(prop_data, allow_required=False)
            args.append(arg)

        return args

    def op_check_missing(self, query_params: list[dict[str, Any]], body_params: dict[str, Any]) -> str:
        """Check for missing required parameters."""
        lines = ["[]"]
        lines.append("if _api_key is None:")
        lines.append('    missing.append("--api-key")')

        for param in query_params:
            if param.get(OasField.REQUIRED, False):
                var_name = self.variable_name(param.get(OasField.NAME))
                option = self.option_name(var_name)
                lines.append(f'if {var_name} is None:')
                lines.append(f'    missing.append("{option}")')

        for prop_name, prop_data in body_params.items():
            if prop_data.get(OasField.REQUIRED):
                var_name = self.variable_name(prop_name)
                option = self.option_name(prop_name)
                lines.append(f'if {var_name} is None:')
                lines.append(f'    missing.append("{option}")')

        return SEP1.join(lines)

    def summary_display(self, node: LayoutNode) -> str:
        """Add the call to summarize the return value when there are summary fields."""
        if not node.summary_fields:
            return ""

        lines = ["if not _details:"]
        args = [quoted(v) for v in node.summary_fields]
        lines.append(f"    data = _d.summary(data, [{', '.join(args)}])")
        return SEP2 + SEP2.join(lines)

    def pagination_creation(self, command: LayoutNode) -> str:
        """Create the 'page_info' variable."""
        if not command.pagination:
            return ''
        args = {"max_count": "_max_count"}
        names = command.pagination
        if names.page_size:
            args["page_size_name"] = quoted(names.page_size)
            args["page_size_value"] = self.variable_name(names.page_size)
        if names.page_start:
            args["page_start_name"] = quoted(names.page_start)
            args["page_start_value"] = self.variable_name(names.page_start)
        if names.item_start:
            args["item_start_name"] = quoted(names.item_start)
            args["item_start_value"] = self.variable_name(names.item_start)
        if names.items_property:
            args["items_property_name"] = quoted(names.items_property)
        if names.next_header:
            args["next_header_name"] = quoted(names.next_header)
        if names.next_property:
            args["next_property_name"] = quoted(names.next_property)

        arg_text = ','.join([f"{SEP2}{k}={v}" for k, v in args.items()])
        return f"{SEP1}page_info = _r.PageParams({arg_text},{SEP1})"

    def function_definition(self, node: LayoutNode) -> str:
        """Generate the function text for the provided LayoutNode."""
        op = self.operations.get(node.identifier)
        method = op.get(OasField.X_METHOD).upper()
        path = op.get(OasField.X_PATH)
        path_params = self.op_params(op, "path")
        query_params = self.params_to_settable_properties(self.op_params(op, "query"))
        header_params = self.params_to_settable_properties(self.op_params(op, "header"))
        body_params = self.op_body_settable_properties(op)
        command_args = [quoted(node.command)]

        req_args = []
        if node.pagination:
            req_func = "depaginate"
            req_args.append("page_info")
        else:
            req_func = "request"
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
            command_args.append("hidden=True")
            message = f"{node.identifier} was deprecated in {x_deprecated}, and should not be used."
            deprecation_warning = SEP1 + f'_l.logger().warning("{message}")'
        elif deprecated:
            command_args.append("hidden=True")
            message = f"{node.identifier} is deprecated and should not be used."
            deprecation_warning = SEP1 + f'_l.logger().warning("{message}")'

        func_name = self.function_name(node.identifier)
        func_args = []
        func_args.extend(self.op_path_arguments(path_params))
        func_args.extend(self.op_query_arguments(query_params))
        func_args.extend(self.op_query_arguments(header_params))
        func_args.extend(self.op_body_arguments(body_params))
        func_args.extend(self.command_infra_arguments(node))
        args_str = SEP1 + f",{SEP1}".join(func_args) + "," + NL

        command_args.append(f'short_help="{self.op_short_help(op)}"')
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
@app.command({', '.join(command_args)})
def {func_name}({args_str}) -> None:
    {self.op_doc_string(op)}# handler for {node.identifier}: {method} {path}
    _l.init_logging(_log_level){deprecation_warning}{user_header_init}
    headers = _r.request_headers(_api_key{self.op_content_header(op)}{user_header_arg})
    url = _r.create_url({self.op_url_params(path)}){self.pagination_creation(node)}
    missing = {self.op_check_missing(query_params + header_params, body_params)}
    if missing:
        _e.handle_exceptions(_e.MissingRequiredError(missing))

    params = {self.op_param_formation(query_params)}{self.op_body_formation(body_params)}

    try:
        data = _r.{req_func}({', '.join(req_args)}){self.summary_display(node)}
        _d.display(data, _out_fmt, _out_style)
    except Exception as ex:
        _e.handle_exceptions(ex)

    return
"""

    def tree_data(self, node: LayoutNode) -> dict[str, Any]:
        """Get the tree data for the specifed node."""
        data = {
            TreeField.NAME.value: node.command,
            TreeField.DESCRIPTION.value: node.description
        }

        operations = []
        for item in node.operations():
            op = self.operations.get(item.identifier)
            child = {
                TreeField.NAME.value: item.command,
                TreeField.OP_ID.value: item.identifier,
                TreeField.FUNC.value: self.function_name(item.identifier),
                TreeField.METHOD.value: op.get(OasField.X_METHOD).upper(),
                TreeField.PATH.value: op.get(OasField.X_PATH),
                TreeField.HELP.value: self.op_short_help(op),
            }
            operations.append(child)

        for item in node.subcommands():
            operations.append({TreeField.NAME.value: item.command, TreeField.SUB_CMD.value: item.identifier})

        data[TreeField.OPERATIONS.value] = operations

        return data

    def get_tree_map(self, node: LayoutNode) -> dict[str, Any]:
        """Get the tree data in a "flat" format for more readable representation in file."""
        result = {node.identifier: self.tree_data(node)}
        for sub in node.subcommands():
            result.update(self.get_tree_map(sub))
        return result

    def get_tree_yaml(self, node: LayoutNode) -> str:
        """Get the layout YAML text for the node (including children)."""
        data = self.get_tree_map(node)
        return yaml.dump(data, indent=2, sort_keys=True)

    def tree_function(self, node: LayoutNode) -> str:
        """Generate the function to show subcommands."""
        return f'''
@app.command("commands", short_help="Display commands tree for {node.command} sub-commands")
def show_commands(
    display: _a.TreeDisplayOption = _a.TreeDisplay.HELP,
    depth: _a.MaxDepthOption = 5,
) -> None:
    """Show {node.command} sub-commands.

    The '*' denotes a sub-command with other sub-commands, but no direct actions.
    """
    path = Path(__file__).parent / "tree.yaml"
    _t.tree(path.as_posix(), "{node.identifier}", display, depth)
    return
'''
