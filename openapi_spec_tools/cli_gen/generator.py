import textwrap
from copy import deepcopy
from typing import Any
from typing import Optional

import yaml

from openapi_spec_tools.cli_gen._logging import logger
from openapi_spec_tools.cli_gen._tree import TreeField
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.cli_gen.layout_types import LayoutNode
from openapi_spec_tools.cli_gen.utils import maybe_quoted
from openapi_spec_tools.cli_gen.utils import quoted
from openapi_spec_tools.cli_gen.utils import set_missing
from openapi_spec_tools.cli_gen.utils import simple_escape
from openapi_spec_tools.cli_gen.utils import to_camel_case
from openapi_spec_tools.cli_gen.utils import to_snake_case
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations

NL = "\n"
SEP1 = "\n    "
SEP2 = "\n        "
SHEBANG = """\
#!/usr/bin/env python3
"""


class Generator:
    def __init__(self, package_name: str, oas: dict[str, Any]):
        self.package_name = package_name
        self.operations = map_operations(oas.get(OasField.PATHS, {}))
        self.components = oas.get(OasField.COMPONENTS, {})
        self.default_host = ""
        servers = oas.get(OasField.SERVERS)
        if servers:
            self.default_host = servers[0].get(OasField.URL, "")
        # ordered list of supported types
        self.supported = [
            ContentType.APP_JSON,
        ]
        self.max_help_length = 120
        self.logger = logger(GENERATOR_LOG_CLASS)

    def shebang(self) -> str:
        """Returns the shebang line that goes at the top of each file."""
        return SHEBANG

    def standard_imports(self) -> str:
        return f"""
from datetime import date  # noqa: F401
from datetime import datetime  # noqa: F401
from enum import Enum  # noqa: F401
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer

from {self.package_name} import _arguments as _a
from {self.package_name} import _display as _d
from {self.package_name} import _exceptions as _e
from {self.package_name} import _logging as _l
from {self.package_name} import _requests as _r
from {self.package_name} import _tree as _t
"""

    def subcommand_imports(self, subcommands: list[LayoutNode]) -> str:
        return NL.join(
            f"from {self.package_name}.{to_snake_case(n.identifier)} import app as {to_snake_case(n.identifier)}"
            for n in subcommands
        )

    def app_definition(self, node: LayoutNode) -> str:
        result = f"""

app = typer.Typer(no_args_is_help=True, help="{simple_escape(node.description)}")
"""
        for child in node.subcommands():
            result += f"""\
app.add_typer({to_snake_case(child.identifier)}, name="{child.command}")
"""

        return result

    def main(self) -> str:
        return """

if __name__ == "__main__":
    app()
"""

    def op_short_help(self, operation: dict[str, Any]) -> str:
        """Gets the short help for the operation."""
        summary = operation.get(OasField.SUMMARY)
        if summary:
            return simple_escape(summary.strip())

        description = operation.get(OasField.DESCRIPTION, "")
        return simple_escape(description.strip().split(". ")[0])

    def op_long_help(self, operation: dict[str, Any]) -> str:
        text = operation.get(OasField.DESCRIPTION) or operation.get(OasField.SUMMARY) or ""
        if not text:
            return text

        lines = [_.rstrip() for _ in text.splitlines()]
        result = "'''"
        for line in lines:
            if not line:
                result += NL
            else:
                inner = textwrap.wrap(line, width=self.max_help_length, replace_whitespace=False)
                result += SEP1 + SEP1.join(inner)
        result += f"{SEP1}'''{SEP1}"
        return result

    def op_request_content(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get the `content` (if any) from the `requestBody`."""
        return operation.get(OasField.REQ_BODY, {}).get(OasField.CONTENT, {})

    def op_get_content_type(self, operation: dict[str, Any]) -> Optional[str]:
        """Get the first content-type matching a supported type."""
        content = self.op_request_content(operation)
        for ct in self.supported:
            if ct.value in content:
                return ct.value
        return None

    def op_get_body(self, operation: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Get the first body matching a supported type."""
        content = self.op_request_content(operation)
        for ct in self.supported:
            body = content.get(ct.value)
            if body:
                return body

        return None

    def _unspecial(self, value: str, replacement: str = '_') -> str:
        """Replaces the "special" characters with the replacement."""
        for v in ['/', '*', '.', '-', '@']:
            value = value.replace(v, replacement)
        return value

    def class_name(self, s: str) -> str:
        """Returns the class name for provided string"""
        value = to_camel_case(self._unspecial(s))
        return value[0].upper() + value[1:]

    def function_name(self, s: str) -> str:
        """Returns the function name for the provided string"""
        return to_snake_case(self._unspecial(s))

    def variable_name(self, s: str) -> str:
        """Returns the variable name for the provided string"""
        return to_snake_case(self._unspecial(s))

    def option_name(self, s: str) -> str:
        """Returns the typer option name for the provided string."""
        value = self.variable_name(s)
        return "--" + value.replace("_", "-")

    def model_is_complex(self, model: dict[str, Any]) -> bool:
        """Determines if the model is complex, such that it would not work well with a list.

        Basically, anything with more than one property is considered complex. This logic is
        not perfect -- it does not expand everything (or wait for "final" answers), but is
        good enough in most cases.
        """
        total_prop_count = 0
        for prop_data in model.get(OasField.PROPS, {}).values():
            if prop_data.get(OasField.READ_ONLY):
                continue

            reference = prop_data.get(OasField.REFS)
            if not reference:
                total_prop_count += 1
            if reference:
                submodel = self.get_model(reference)
                if self.model_is_complex(submodel):
                    return True
                sub_props = submodel.get(OasField.PROPS, {})
                total_prop_count += len(sub_props)

            if total_prop_count > 1:
                return True

        for inherited in model.get(OasField.ALL_OF, []):
            properties = inherited.get(OasField.PROPS, {})
            total_prop_count += len(properties)
            if total_prop_count > 1:
                return True

            reference = inherited.get(OasField.REFS)
            submodel = self.get_model(reference)
            properties = submodel.get(OasField.PROPS, {})
            total_prop_count += len(properties)
            if total_prop_count > 1:
                return True

        return False

    def get_items_model(self, prop_data: dict[str, Any]) -> tuple[str, dict]:
        """Determines if the property data references complex items"""
        items = prop_data.get(OasField.ITEMS, {})
        item_ref = items.get(OasField.REFS, "")
        item_short = self.short_reference_name(item_ref)
        if item_ref:
            item_model = deepcopy(self.get_model(item_ref))
        else:
            item_model = deepcopy(items)

        return item_short, item_model

    def model_collection_type(self, model: str) -> Optional[str]:
        """Determines the collection type (current just an array)"""
        model_type = model.get(OasField.TYPE)
        if model_type == "array":
            return model_type

        for parent in model.get(OasField.ALL_OF) or model.get(OasField.ANY_OF) or []:
            reference = parent.get(OasField.REFS, "")
            if not reference:
                submodel = parent
            else:
                submodel = self.get_model(reference)
            # recursively search through submodels
            sub_collection = self.model_collection_type(submodel)
            if sub_collection:
                return sub_collection

        return None

    def prop_find_reference(self, prop_data: dict[str, Any]) -> str:
        """Properties may have a reference buried inside an anyOf, allOf, or oneOf."""
        reference = prop_data.get(OasField.REFS)
        if reference:
            return reference

        parents = prop_data.get(OasField.ALL_OF, [])
        parents.extend(prop_data.get(OasField.ANY_OF, []))
        parents.extend(prop_data.get(OasField.ONE_OF, []))
        for parent in parents:
            reference = parent.get(OasField.REFS)
            if reference:
                return reference

        return ""

    def model_settable_properties(self, model: dict[str, Any]) -> dict[str, Any]:
        """Expand the model into a dictionary of properties"""
        properties = {}

        # start with the base-classes in allOf
        for parent in model.get(OasField.ALL_OF, []):
            reference = parent.get(OasField.REFS, "")
            short_refname = self.short_reference_name(reference)
            if not reference:
                # this is an unnamed sub-reference
                submodel = deepcopy(parent)
            else:
                submodel = deepcopy(self.get_model(reference))

            if not submodel:
                self.logger.warning(f"Failed to find {short_refname} model")
                continue

            required_sub = submodel.get(OasField.REQUIRED, [])
            sub_properties = self.model_settable_properties(submodel)
            for sub_name, sub_data in sub_properties.items():
                # NOTE: no "name mangling" since using inheritance
                updated = deepcopy(sub_data)
                if short_refname:
                    set_missing(updated, OasField.X_REF.value, short_refname)
                set_missing(updated, OasField.X_FIELD.value, sub_name)
                updated[OasField.REQUIRED.value] = sub_data.get(OasField.REQUIRED.value) and sub_name in required_sub
                properties[sub_name] = updated

        required_props = model.get(OasField.REQUIRED, [])
        # then, copy the individual properties
        for prop_name, prop_data in model.get(OasField.PROPS, {}).items():
            if prop_data.get(OasField.READ_ONLY, False):
                continue

            reference = self.prop_find_reference(prop_data)
            short_refname = self.short_reference_name(reference)
            if not reference:
                submodel = deepcopy(prop_data)
            else:
                submodel = deepcopy(self.get_model(reference))

            if not submodel:
                self.logger.warning(f"Failed to find {short_refname} model")
                continue

            collection_type = self.model_collection_type(submodel)
            if collection_type:
                item_name, item_model = self.get_items_model(submodel)
                if not item_model:
                    self.logger.error(f"Could not find {short_refname}.{prop_name} item model")
                    continue
                if self.model_is_complex(item_model):
                    self.logger.error(f"Ignoring {short_refname}.{prop_name} -- cannot handle lists of complex")
                    continue
                if item_name:
                    set_missing(submodel, OasField.X_REF.value, item_name)
                submodel.pop(OasField.ITEMS.value, None)
                submodel[OasField.X_COLLECT.value] = collection_type
                submodel.update(item_model)

            required_sub = submodel.get(OasField.REQUIRED, [])
            sub_properties = self.model_settable_properties(submodel)
            if not sub_properties:
                updated = deepcopy(submodel)
                if short_refname:
                    set_missing(updated, OasField.X_REF.value, short_refname)
                updated[OasField.REQUIRED.value] = prop_name in required_props
                properties[prop_name] = updated
                continue

            for sub_name, sub_data in sub_properties.items():
                # these properties are "name mangled" to include the parent property name
                full_name = f"{prop_name}.{sub_name}"
                updated = deepcopy(sub_data)
                updated[OasField.REQUIRED.value] = prop_name in required_props and sub_name in required_sub
                if reference:
                    set_missing(updated, OasField.X_REF.value, self.short_reference_name(reference))
                set_missing(updated, OasField.X_FIELD.value, sub_name)
                set_missing(updated, OasField.X_PARENT.value, prop_name)
                properties[full_name] = updated

        return properties

    def op_body_settable_properties(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get a dictionary of settable body properties"""
        body = self.op_get_body(operation)
        if not body:
            return {}

        schema = body.get(OasField.SCHEMA, {})
        ref = schema.get(OasField.REFS)
        if ref:
            schema = self.get_model(ref)
        return self.model_settable_properties(schema)

    def short_reference_name(self, full_name: str) -> str:
        """Transforms the '#/components/schemas/Xxx' to 'Xxx'"""
        return full_name.split('/')[-1]

    def get_model(self, full_name: str) -> dict[str, Any]:
        """Returns the reference"""
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

    def command_infra_arguments(self, command: LayoutNode) -> list[str]:
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

    def schema_to_type(self, schema: str, fmt: Optional[str]) -> Optional[str]:
        """
        Gets the base Python type for simple schema types.

        The fmt is really the "format" field, but renamed to avoid masking builtin.
        """
        if schema == "boolean":
            return "bool"
        if schema == "integer":
            return "int"
        if schema == "numeric":
            return "float"
        if schema == "string":
            if fmt == "date-time":
                return "datetime"
            if fmt == "date":
                return "date"
            # TODO: uuid
            return "str"

        self.logger.error(f"No Python type found for {schema}/{fmt}")
        return None

    def get_parameter_pytype(self, param_data: dict[str, Any]) -> str:
        """
        Gets the "basic" Python type from a parameter object.

        Parameters have a schema sub-object that contains the 'type' and 'format' fields.
        """
        schema = param_data.get(OasField.SCHEMA, {})
        values = schema.get(OasField.ENUM)
        if values:
            name = self.short_reference_name(schema.get(OasField.REFS, "")) or param_data.get(OasField.NAME)
            return self.class_name(name)

        return self.schema_to_type(schema.get(OasField.TYPE), schema.get(OasField.FORMAT))

    def get_property_pytype(self, prop_name: str, prop_data: dict[str, Any]) -> Optional[str]:
        """
        Gets the "basic" Python type from a property object.

        Each property potentially has 'type' and 'format' fields.
        """
        if prop_data.get(OasField.ENUM):
            pytype = self.class_name(prop_data.get(OasField.X_REF) or prop_name)
        else:
            pytype = self.schema_to_type(prop_data.get(OasField.TYPE), prop_data.get(OasField.FORMAT))
            if not pytype:
                return pytype

        if prop_data.get(OasField.X_COLLECT) == "array":
            pytype = f"list[{pytype}]"
        if not prop_data.get(OasField.REQUIRED):
            pytype = f"Optional[{pytype}]"

        return pytype

    def op_params(self, operation: dict[str, Any], location: str) -> list[dict[str, Any]]:
        """
        Gets a complete list of operation parameters matching location.
        """
        params = []
        # NOTE: start with "higher level" path params, since they're more likely to be required
        total_params = (operation.get(OasField.X_PATH_PARAMS) or []) + (operation.get(OasField.PARAMS) or [])
        for item in total_params:
            ref = item.get(OasField.REFS, "")
            model = self.get_model(ref)
            if model:
                item = deepcopy(model)
                item[OasField.X_REF] = self.short_reference_name(ref)
            if item.get(OasField.IN) != location:
                continue
            params.append(item)
        return params

    def op_param_to_argument(self, param: dict[str, Any], allow_required: bool) -> str:
        """
        Converts a parameter into a typer argument.
        """
        var_name = self.variable_name(param.get(OasField.NAME))
        description = param.get(OasField.DESCRIPTION) or ""
        required = param.get(OasField.REQUIRED, False)
        deprected = param.get(OasField.DEPRECATED, False)
        x_deprecated = param.get(OasField.X_DEPRECATED, None)
        schema = param.get(OasField.SCHEMA, {})
        schema_default = schema.get(OasField.DEFAULT)
        arg_type = self.get_parameter_pytype(param)
        if not arg_type:
            # log an error and use 'Any'
            self.logger.error(f"Unable to determine Python type for {param}")
            arg_type = 'Any'

        typer_args = []
        if arg_type in ("int", "float"):
            schema_min = schema.get(OasField.MIN)
            if schema_min is not None:
                typer_args.append(f"min={schema_min}")
            schema_max = schema.get(OasField.MAX)
            if schema_max is not None:
                typer_args.append(f"max={schema_max}")
        if allow_required and required and schema_default is None:
            typer_type = 'typer.Argument'
            typer_args.append('show_default=False')
            arg_default = ""
        else:
            typer_type = 'typer.Option'
            if schema_default is None:
                arg_type = f"Optional[{arg_type}]"
                arg_default = " = None"
                typer_args.append('show_default=False')
            else:
                if arg_type in ("str", "datetime"):
                    arg_default = f' = "{schema_default}"'
                else:
                    arg_default = f" = {schema_default}"
        is_enum = bool(schema.get(OasField.ENUM))
        if is_enum:
            typer_args.append("case_sensitive=False")
        if deprected or x_deprecated:
            typer_args.append("hidden=True")
        typer_args.append(f'help="{simple_escape(description)}"')
        comma = ', '

        return f'{var_name}: Annotated[{arg_type}, {typer_type}({comma.join(typer_args)})]{arg_default}'

    def op_path_arguments(self, path_params: list[dict[str, Any]]) -> list[str]:
        """
        Converts all path parameters into typer arguments.
        """
        args = []
        for param in path_params:
            arg = self.op_param_to_argument(param, allow_required=True)
            args.append(arg)

        return args

    def op_query_arguments(self, query_params: list[dict[str, Any]]) -> list[str]:
        """
        Converts query parameters to typer arguments
        """
        args = []
        for param in query_params:
            arg = self.op_param_to_argument(param, allow_required=False)
            args.append(arg)

        return args

    def op_body_arguments(self, body_params: list[dict[str, Any]]) -> list[str]:
        args = []
        for prop_name, prop_data in body_params.items():
            py_type = self.get_property_pytype(prop_name, prop_data)
            if not py_type:
                # log an error and use 'Any'
                self.logger.error(f"Unable to determine Python type for {prop_name}={prop_data}")
                py_type = 'Any'

            t_args = {}
            def_val = maybe_quoted(prop_data.get(OasField.DEFAULT))
            if def_val is not None:
                t_args["show_default"] = False
            is_enum = bool(prop_data.get(OasField.ENUM))
            if is_enum:
                t_args["case_sensitive"] = False
            deprected = prop_data.get(OasField.DEPRECATED, False)
            x_deprecated = prop_data.get(OasField.X_DEPRECATED, None)
            if deprected or x_deprecated:
                t_args["hidden"] = True
            help = prop_data.get(OasField.DESCRIPTION)
            if help:
                t_args['help'] = f'"{simple_escape(help)}"'
            t_decl = f"typer.Option({', '.join([f'{k}={v}' for k, v in t_args.items()])})"
            arg = f"{self.variable_name(prop_name)}: Annotated[{py_type}, {t_decl}] = {def_val}"
            args.append(arg)

        return args

    def op_url_params(self, path: str) -> str:
        """Parse the X-PATH to list the parameters that go into the URL formation."""
        parts = path.split("/")
        items = []
        last = None
        for p in parts:
            if "{" in p:
                if last:
                    items.append(f'"{last}"')
                items.append(self.variable_name(p.replace("{", "").replace("}", "")))
                last = None
            elif not last:
                last = p
            else:
                last += "/" + p
        if last:
            items.append(f'"{last}"')

        return f"_api_host, {', '.join(items)}"

    def op_param_formation(self, query_params: list[dict[str, Any]]) -> str:
        """Create the query parameters that go into the request"""
        result = "{}"
        for param in query_params:
            param_name = param.get(OasField.NAME)
            var_name = self.variable_name(param_name)
            option = self.option_name(param_name)
            deprecated = param.get(OasField.DEPRECATED, False)
            x_deprecated = param.get(OasField.X_DEPRECATED, None)
            dep_warning = ""
            if x_deprecated:
                dep_warning = f'_l.logger().warning("{option} was deprecated in {x_deprecated}"){SEP2}'
            elif deprecated:
                dep_warning = f'_l.logger().warning("{option} is deprecated"){SEP2}'
            if param.get(OasField.REQUIRED, False):
                result += f'{SEP1}params[{quoted(param_name)}] = {var_name}'
            else:
                result += f'{SEP1}if {var_name} is not None:'
                result += f'{SEP2}{dep_warning}params[{quoted(param_name)}] = {var_name}'
        return result

    def op_content_header(self, operation: dict[str, Any]) -> str:
        """Returns the content-type with variable name prefix (when appropriate)"""
        content_type = self.op_get_content_type(operation)
        if not content_type:
            return ""
        return f', content_type="{content_type}"'

    def op_body_formation(self, body_params: dict[str, Any]) -> str:
        """Creates a body parameter and poulates it when there are body paramters."""
        if not body_params:
            return ""

        lines = ["body = {}"]
        for prop_name, prop_data in body_params.items():
            var_name = self.variable_name(prop_name)
            option = self.option_name(prop_name)
            deprecated = prop_data.get(OasField.DEPRECATED, False)
            x_deprecated = prop_data.get(OasField.X_DEPRECATED, None)
            dep_msg = ""
            if x_deprecated:
                dep_msg = f"{option} was deprecated in {x_deprecated} and should not be used"
            elif deprecated:
                dep_msg = f"{option} is deprecated and should not be used"
            if prop_data.get(OasField.REQUIRED):
                lines.append(f'body["{prop_name}"] = {var_name}')
            else:
                lines.append(f'if {var_name} is not None:')
                if dep_msg:
                    lines.append(f'    _l.logger().warning("{dep_msg}")')
                lines.append(f'    body["{prop_name}"] = {var_name}')

        return SEP1 + SEP1.join(lines)

    def op_check_missing(self, query_params: list[dict[str, Any]], body_params: dict[str, Any]) -> str:
        """Checks for missing required parameters"""
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
        if not node.summary_fields:
            return ""

        lines = ["if not _details:"]
        args = [quoted(v) for v in node.summary_fields]
        lines.append(f"    data = summary(data, [{', '.join(args)}])")
        return SEP2 + SEP2.join(lines)

    def pagination_creation(self, command: LayoutNode) -> str:
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
            args["item_property_name"] = quoted(names.items_property)
        if names.next_header:
            args["next_header_name"] = quoted(names.next_header)
        if names.next_property:
            args["next_property_name"] = quoted(names.next_property)

        arg_text = ', '.join([f"{k}={v}" for k, v in args.items()])
        return f"{SEP1}page_info = _r.PageParams({arg_text})"

    def enum_declaration(self, name: str, enum_type: str, values: list[Any]) -> str:
        """Turns data into an enum declation"""
        prefix = "" if enum_type == "str" else "VALUE_"
        declarations = [
            f"{prefix}{to_snake_case(str(v)).upper()} = {maybe_quoted(v)}"
            for v in values
        ]
        # NOTE: the noqa is due to potentially same definition ahead of multiple functions
        return f"class {name}({enum_type}, Enum):  # noqa: F811{SEP1}{SEP1.join(declarations)}{NL * 2}"

    def enum_definitions(
        self,
        path_params: list[dict[str, Any]],
        query_params: list[dict[str, Any]],
        body_params: dict[str, Any],
    ) -> str:
        """Creates enum class definitions need to support the provided"""

        # collect all the enum types (mapped by name to avoid duplicates)
        enums = {}
        for param_data in path_params + query_params:
            schema = param_data.get(OasField.SCHEMA, {})
            values = schema.get(OasField.ENUM)
            if not values:
                continue

            e_name = self.short_reference_name(schema.get(OasField.REFS, "")) or param_data.get(OasField.NAME)
            e_type = self.schema_to_type(schema.get(OasField.TYPE), schema.get(OasField.FORMAT)) or 'str'
            enums[self.class_name(e_name)] = (e_type, values)

        for name, prop in body_params.items():
            values = prop.get(OasField.ENUM)
            if not values:
                continue
            e_name = prop.get(OasField.X_REF) or name
            e_type = self.schema_to_type(prop.get(OasField.TYPE), prop.get(OasField.FORMAT)) or 'str'
            enums[self.class_name(e_name)] = (e_type, values)

        if not enums:
            return ""

        # declare all the types
        declarations = []
        for e_name, (e_type, e_values) in enums.items():
            declarations.append(self.enum_declaration(e_name, e_type, e_values))

        return NL + NL.join(declarations)

    def function_definition(self, node: LayoutNode) -> str:
        op = self.operations.get(node.identifier)
        method = op.get(OasField.X_METHOD).upper()
        path = op.get(OasField.X_PATH)
        path_params = self.op_params(op, "path")
        query_params = self.op_params(op, "query")
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
        if self.op_get_content_type(op):
            req_args.append("body=body")
        req_args.append("timemout=_api_timeout")

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
        func_args.extend(self.op_body_arguments(body_params))
        func_args.extend(self.command_infra_arguments(node))
        args_str = SEP1 + f",{SEP1}".join(func_args) + "," + NL

        command_args.append(f'short_help="{self.op_short_help(op)}"')
        self.logger.debug(f"{func_name}({len(path_params)} path, {len(query_params)} query, {len(body_params)} body)")

        return f"""
{self.enum_definitions(path_params, query_params, body_params)}
@app.command({', '.join(command_args)})
def {func_name}({args_str}) -> None:
    {self.op_long_help(op)}# handler for {node.identifier}: {method} {path}
    _l.init_logging(_log_level){deprecation_warning}
    headers = _r.request_headers(_api_key{self.op_content_header(op)})
    url = _r.create_url({self.op_url_params(path)}){self.pagination_creation(node)}
    missing = {self.op_check_missing(query_params, body_params)}
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
        """Gets the tree data for the specifed node"""
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
        """Gets the tree data in a "flat" format for more readable representation in file"""
        result = {node.identifier: self.tree_data(node)}
        for sub in node.subcommands():
            result.update(self.get_tree_map(sub))
        return result

    def get_tree_yaml(self, node: LayoutNode) -> str:
        """Gets the layout YAML text for the node (including children)"""
        data = self.get_tree_map(node)
        return yaml.dump(data, indent=2, sort_keys=True)

    def tree_function(self, node: LayoutNode) -> str:
        """Generates the function to show subcommands"""
        return f"""
@app.command("commands", short_help="Display commands tree for sub-commands")
def show_commands(
    display: _a.TreeDisplayOption = _a.TreeDisplay.HELP,
    depth: _a.MaxDepthOption = 5,
) -> None:
    path = Path(__file__).parent / "tree.yaml"
    _t.tree(path.as_posix(), "{node.identifier}", display, depth)
    return
"""
