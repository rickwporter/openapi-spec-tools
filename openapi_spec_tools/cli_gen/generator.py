"""Declares the Generator class that is used for most of the CLi generation capability."""
import textwrap
from copy import deepcopy
from typing import Any
from typing import Optional

import yaml

from openapi_spec_tools.cli_gen._logging import get_logger
from openapi_spec_tools.cli_gen._tree import TreeField
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.cli_gen.layout_types import LayoutNode
from openapi_spec_tools.cli_gen.utils import is_case_sensitive
from openapi_spec_tools.cli_gen.utils import maybe_quoted
from openapi_spec_tools.cli_gen.utils import prepend
from openapi_spec_tools.cli_gen.utils import quoted
from openapi_spec_tools.cli_gen.utils import replace_special
from openapi_spec_tools.cli_gen.utils import set_missing
from openapi_spec_tools.cli_gen.utils import shallow
from openapi_spec_tools.cli_gen.utils import simple_escape
from openapi_spec_tools.cli_gen.utils import to_camel_case
from openapi_spec_tools.cli_gen.utils import to_snake_case
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import NULL_TYPES
from openapi_spec_tools.utils import map_operations

NL = "\n"
SEP1 = "\n    "
SEP2 = "\n        "
SHEBANG = """\
#!/usr/bin/env python3
"""
# map of supported collections to their Python types
COLLECTIONS = {
    "array": "list",
}

# This is an incomplete list of Python builtins that should avoided in variable names
RESERVED = {
    "all",
    "any",
    "bool",
    "breakpoint",
    "class",
    "continue",
    "dict",
    "except",
    "float",
    "for",
    "format",
    "in",
    "input",
    "int",
    "list",
    "max",
    "min",
    "print",
    "set",
    "type",
    "try",
    "while",
}
CONFLICT_SUFFIX = "_"


class Generator:
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(self, package_name: str, oas: dict[str, Any]):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
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
        self.logger = get_logger(GENERATOR_LOG_CLASS)

    def shebang(self) -> str:
        """Get the shebang line that goes at the top of each file."""
        return SHEBANG

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

    def op_short_help(self, operation: dict[str, Any]) -> str:
        """Get the short help for the operation."""
        summary = operation.get(OasField.SUMMARY)
        if summary:
            return simple_escape(summary.strip())

        description = operation.get(OasField.DESCRIPTION, "")
        return simple_escape(description.strip().split(". ")[0])

    def op_long_help(self, operation: dict[str, Any]) -> str:
        """Get the docstring for the CLI function.

        This is the summary/description that gets reformatted to be a bit more readable, and
        adds the triple quotes.
        """
        text = operation.get(OasField.DESCRIPTION) or operation.get(OasField.SUMMARY) or ""
        if not text:
            return text

        lines = [_.rstrip() for _ in text.splitlines()]
        # remove leading blank lines
        while lines and not lines[0]:
            lines.pop(0)
        # remove trailing blank lines
        while lines and not lines[-1]:
            lines.pop()
        if not lines:
            return ""

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

    def class_name(self, s: str) -> str:
        """Get the class name for provided string."""
        value = to_camel_case(replace_special(s)).replace("_", "")
        return value[0].upper() + value[1:]

    def function_name(self, s: str) -> str:
        """Get the function name for the provided string."""
        vname = to_snake_case(replace_special(s))
        if vname in RESERVED:
            return f"{vname}{CONFLICT_SUFFIX}"

        return vname

    def variable_name(self, s: str) -> str:
        """Get the variable name for the provided string."""
        vname = to_snake_case(replace_special(s))
        if vname in RESERVED:
            return f"{vname}{CONFLICT_SUFFIX}"

        return vname

    def option_name(self, s: str) -> str:
        """Get the typer option name for the provided string."""
        value = to_snake_case(replace_special(s))
        return "--" + value.replace("_", "-")

    def model_is_complex(self, model: dict[str, Any]) -> bool:
        """Determine if the model is complex, such that it would not work well with a list.

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

    def model_collection_type(self, model: str) -> Optional[str]:
        """Determine the collection type (current just an array)."""
        model_type = self.simplify_type(model.get(OasField.TYPE))
        if model_type in COLLECTIONS.keys():
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

    def expand_references(self, model: dict[str, Any]) -> dict[str, Any]:
        """Expand all the references.

        This is a brute force method to recursively look for any `$ref` keys, and update
        those dictionaries in place.
        """
        # start at this level
        updated = deepcopy(model)

        full_ref = model.get(OasField.REFS)
        if full_ref:
            updated[OasField.X_REF.value] = self.short_reference_name(full_ref)
            submodel = self.get_model(full_ref)
            if not submodel:
                self.logger.warning(f"Unable to find model for {full_ref}")
                return {}

            updated.update(submodel)

        # then, loop thru all the sub-items
        result = {}
        for key, value in updated.items():
            if isinstance(value, dict):
                # recursively update
                resolved = self.expand_references(value)
                if resolved:
                    result[key] = resolved
            elif isinstance(value, list):
                items = [
                    self.expand_references(v) if isinstance(v, dict) else v
                    for v in value
                ]
                if items:
                    result[key] = items
            else:
                result[key] = value

        return result

    def expanded_settable_properties(self, name: str, model: dict[str, Any]) -> dict[str, Any]:
        """Turn an expanded model (all references expanded) into a dictionary of properties."""
        properties = {}

        # start with the base-classes in allOf
        for index, parent in enumerate(model.get(OasField.ALL_OF, [])):
            required_sub = parent.get(OasField.REQUIRED, [])
            reference = parent.get(OasField.REFS, "")
            short_refname = self.short_reference_name(reference)
            sub_properties = self.expanded_settable_properties(f"{name}.anyOf[{index}]", parent)
            for sub_name, sub_data in sub_properties.items():
                if short_refname:
                    set_missing(sub_data, OasField.X_REF.value, short_refname)
                set_missing(sub_data, OasField.X_FIELD.value, sub_name)
                sub_data[OasField.REQUIRED.value] = sub_data.get(OasField.REQUIRED.value) and sub_name in required_sub
                properties[sub_name] = sub_data

        any_of = model.get(OasField.ANY_OF)
        if any_of:
            if len(any_of) != 1:
                self.logger.info(f"Grabbing anyOf[0] item from {name}")
                self.logger.debug(f"{name} anyOf selected: {shallow(any_of[0])}")
            # just grab the first one... not sure this is the best choice, but need to do something
            model.update(any_of[0])

        one_of = model.get(OasField.ONE_OF)
        if one_of:
            updated = self.condense_one_of(one_of)
            if len(updated) != 1:
                self.logger.info(f"Grabbing oneOf[0] item from {name}")
                self.logger.debug(f"{name} oneOf selected: {shallow(updated[0])}")
            # just grab the first one... not sure this is the best choice, but need to do something
            model.update(updated[0])

        reference = model.get(OasField.REFS, "")
        short_refname = self.short_reference_name(reference)
        required_props = model.get(OasField.REQUIRED, [])

        # copy the individual properties
        for prop_name, prop_data in model.get(OasField.PROPS, {}).items():
            if prop_data.get(OasField.READ_ONLY, False):
                continue

            collection_type = self.model_collection_type(prop_data)
            if collection_type:
                collect_name = f"{short_refname}." if short_refname else "" + prop_name
                item_model = prop_data.get(OasField.ITEMS, {})
                if not item_model:
                    self.logger.error(f"Could not find {collect_name} item model")
                    continue
                if self.model_is_complex(item_model):
                    self.logger.error(f"Ignoring {collect_name} -- cannot handle lists of complex")
                    continue
                prop_data.pop(OasField.ITEMS.value, None)
                prop_data[OasField.X_COLLECT.value] = collection_type
                prop_data.update(item_model)

            required_sub = prop_data.get(OasField.REQUIRED, [])
            sub_properties = self.expanded_settable_properties(f"{name}.{prop_name}", prop_data)
            if not sub_properties:
                # kind of a corner case where an enum has no properties
                for key in (OasField.ALL_OF, OasField.ANY_OF, OasField.ONE_OF):
                    items = prop_data.pop(key, None)
                    if not items:
                        continue
                    prop_data.update(items[0])

                pytype = self.get_property_pytype(prop_name, prop_data)
                if not pytype:
                    self.logger.warning(f"Unable to determine pytype for {name}.{prop_name}")
                    continue

                if short_refname:
                    set_missing(prop_data, OasField.X_REF.value, short_refname)
                prop_data[OasField.REQUIRED.value] = prop_name in required_props
                properties[prop_name] = prop_data
                continue

            for sub_name, sub_data in sub_properties.items():
                # these properties are "name mangled" to include the parent property name
                full_name = f"{prop_name}.{sub_name}"
                sub_data[OasField.REQUIRED.value] = prop_name in required_props and sub_name in required_sub
                if reference:
                    set_missing(sub_data, OasField.X_REF.value, self.short_reference_name(reference))
                set_missing(sub_data, OasField.X_FIELD.value, sub_name)
                prepend(sub_data, OasField.X_PARENTS.value, prop_name)
                properties[full_name] = sub_data

        return properties

    def model_settable_properties(self, name: str, model: dict[str, Any]) -> dict[str, Any]:
        """Expand the model into a dictionary of properties."""
        expanded = self.expand_references(model)

        return self.expanded_settable_properties(name, expanded)

    def op_body_settable_properties(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get a dictionary of settable body properties."""
        body = self.op_get_body(operation)
        if not body:
            return {}

        schema = body.get(OasField.SCHEMA, {})
        name = "body"
        ref = schema.get(OasField.REFS)
        if ref:
            name = self.short_reference_name(ref)
            schema = self.get_model(ref)

        # attempt to simplify enum types to a single type to something that matches
        properties = self.model_settable_properties(name, schema)
        for prop_data in properties.values():
            enum_values = prop_data.get(OasField.ENUM)
            schema_type = prop_data.get(OasField.TYPE)
            if enum_values and isinstance(schema_type, list):
                schema_list = self.enum_find_schema(schema_type, enum_values)
                schema_type = schema_list[0]
                prop_data[OasField.TYPE.value] = schema_type
            # make sure the enumeration and default values align with the type
            if enum_values and schema_type == "string":
                self.enum_stringify(prop_data)

        return properties

    def short_reference_name(self, full_name: str) -> str:
        """Transform the '#/components/schemas/Xxx' to 'Xxx'."""
        return full_name.split('/')[-1]

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

    def schema_to_type(self, schema: str, fmt: Optional[str]) -> Optional[str]:
        """Get the base Python type for simple schema types.

        The fmt is really the "format" field, but renamed to avoid masking builtin.
        """
        if schema == "boolean":
            return "bool"
        if schema == "integer":
            return "int"
        if schema in ("numeric", "number"):
            return "float"
        if schema == "string":
            if fmt == "date-time":
                return "datetime"
            if fmt == "date":
                return "date"
            # TODO: uuid
            return "str"

        return None

    def simplify_type(self, schema: Any) -> Any:
        """Simplfy the schema type.

        In OAS 3.1, the 'type' can be a list. When it is a nullable object, the 'null' value is one of the
        items in the list.
        """
        if schema is None:
            return None
        if isinstance(schema, (str, dict)):
            return schema
        if isinstance(schema, list):
            reduced = set(schema) - NULL_TYPES
            if len(reduced) == 1:
                return reduced.pop()
            # loop through to find the items from the ordered schema
            for item in schema:
                if item in reduced:
                    self.logger.debug(f"Choosing {item} type from {', '.join(schema)}")
                    return item

        self.logger.warning(f"Unable to simplify type for {schema}")
        return None


    def schema_to_pytype(self, schema: dict[str, Any]) -> Optional[str]:
        """Determine the basic Python type from the schema object."""
        oas_type = self.simplify_type(schema.get(OasField.TYPE))
        oas_format = schema.get(OasField.FORMAT)
        return self.schema_to_type(oas_type, oas_format)

    def get_parameter_pytype(self, param_data: dict[str, Any]) -> str:
        """Get the "basic" Python type from a parameter object.

        Parameters have a schema sub-object that contains the 'type' and 'format' fields.
        """
        values = param_data.get(OasField.ENUM)
        if values:
            name = param_data.get(OasField.NAME)
            return self.class_name(name)

        return self.schema_to_pytype(param_data)

    def get_property_pytype(self, prop_name: str, prop_data: dict[str, Any]) -> Optional[str]:
        """Get the "basic" Python type from a property object.

        Each property potentially has 'type' and 'format' fields.
        """
        if prop_data.get(OasField.ENUM):
            pytype = self.class_name(prop_name)
        else:
            pytype = self.schema_to_pytype(prop_data)
            if not pytype:
                return pytype

        collection = COLLECTIONS.get(prop_data.get(OasField.X_COLLECT))
        if collection:
            pytype = f"{collection}[{pytype}]"
        if not prop_data.get(OasField.REQUIRED):
            pytype = f"Optional[{pytype}]"

        return pytype

    def op_params(self, operation: dict[str, Any], location: str) -> list[dict[str, Any]]:
        """Get a complete list of operation parameters matching location."""
        params = []
        # NOTE: start with "higher level" path params, since they're more likely to be required
        total_params = (operation.get(OasField.X_PATH_PARAMS) or []) + (operation.get(OasField.PARAMS) or [])
        for _item in total_params:
            item = deepcopy(_item)
            ref = item.get(OasField.REFS, "")
            model = self.get_model(ref)
            if model:
                item = deepcopy(model)
                item[OasField.X_REF] = self.short_reference_name(ref)
            if item.get(OasField.IN) != location:
                continue

            # promote the schema items into item
            schema = item.pop(OasField.SCHEMA, {})
            item.update(schema)
            params.append(item)
        return params

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
            if prop_name.lower() in RESERVED:
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

    def condense_one_of(self, one_of: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Remove "duplicate" collection elements, and adds X_COLLECT to the schema."""
        condensed = []
        for outer in one_of:
            item = deepcopy(outer)
            found = False
            for inner in one_of:
                if item.get(OasField.ITEMS) == inner:
                    found = True
                    break
                if inner.get(OasField.ITEMS) == item:
                    item[OasField.X_COLLECT.value] = inner.get(OasField.TYPE)
            if not found:
                condensed.append(item)

        return condensed

    def param_to_property(self, param: dict[str, Any]) -> dict[str, Any]:
        """Convert parameter data to property data.

        Resolves parameter data to make it easier to digest (e.g. choosing any oneOf,
        collection information, required).
        """
        prop = deepcopy(param)

        one_of = prop.pop(OasField.ONE_OF, [])
        if one_of:
            updated = self.condense_one_of(one_of)
            if len(updated) == 1:
                prop.update(updated[0])
            else:
                # just grab the first one... not sure this is the best choice, but need to do something
                self.logger.warning(f"Grabbing oneOf[0] item from {shallow(updated[0])}")
                prop.update(updated[0])

        any_of = prop.pop(OasField.ANY_OF, [])
        if any_of:
            # just grab the first one...
            self.logger.warning(f"Grabbing anyOf[0] item from {shallow(any_of[0])}")
            prop.update(any_of[0])

        nullable = False
        schema_type = prop.get(OasField.TYPE)
        if isinstance(schema_type, list):
            nullable = any(nt in schema_type for nt in NULL_TYPES)
            schema_list = [v for v in schema_type if v not in NULL_TYPES]
            nullable = schema_type != schema_list
            if len(schema_list) == 1:
                schema_type = schema_list[0]
            else:
                schema_type = schema_list
            prop[OasField.TYPE.value] = schema_type

        if isinstance(schema_type, str) and schema_type in COLLECTIONS.keys():
            items = prop.pop(OasField.ITEMS, {})
            prop.update(items)
            prop[OasField.X_COLLECT.value] = schema_type
            schema_type = items.get(OasField.TYPE)

        enum_values = prop.get(OasField.ENUM)
        if enum_values and isinstance(schema_type, list):
            schema_list = self.enum_find_schema(schema_type, enum_values)
            schema_type = schema_list[0]
            prop[OasField.TYPE.value] = schema_type

        # make sure the enumeration and default values align with the type
        if enum_values and schema_type == "string":
            self.enum_stringify(prop)

        schema = self.simplify_type(prop)
        if schema:
            prop.update(schema)
        if nullable:
            prop[OasField.REQUIRED.value] = False

        return prop

    def params_to_settable_properties(self, parameters: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Get a dictionary of settable parameter properties.

        This expands the parameters into more basic types that allows for complex parameters.
        """
        properties = []
        for param in parameters:
            items = param.get(OasField.ITEMS, {})
            ref = param.get(OasField.REFS) or items.get(OasField.REFS)
            if not ref:
                properties.append(self.param_to_property(param))
                continue

            model = deepcopy(self.get_model(ref))
            if not model.get(OasField.PROPS):
                param.update(model)
                properties.append(param)
                continue

            param_name = param.get(OasField.NAME)
            settable = self.model_settable_properties(param_name, model)
            for prop_name, prop_data in settable.items():
                prop_data[OasField.NAME.value] = f"{param_name}.{prop_name}"
                schema = self.param_to_property(prop_data)
                prop_data.update(schema)
                properties.append(prop_data)

        return properties

    def op_body_arguments(self, body_params: list[dict[str, Any]]) -> list[str]:
        """Convert the body parameters dictionary into a list of CLI function arguments."""
        args = []
        for prop_name, prop_data in body_params.items():
            prop_data[OasField.NAME.value] = prop_name
            arg = self.property_to_argument(prop_data, allow_required=False)
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
        """Create the query parameters that go into the request."""
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
        """Content-type with variable name prefix (when appropriate)."""
        content_type = self.op_get_content_type(operation)
        if not content_type:
            return ""
        return f', content_type="{content_type}"'

    def op_body_formation(self, body_params: dict[str, Any]) -> str:
        """Create body parameter and poulates it when there are body paramters."""
        if not body_params:
            return ""

        # initialize all "parent" objects
        lines = ["body = {}"]
        found = set()
        lineage = []
        for prop_data in body_params.values():
            parents = prop_data.get(OasField.X_PARENTS, [])
            if parents and parents not in lineage:
                lineage.append(parents)

            for parent in parents:
                if parent not in found:
                    lines.append(f"{self.variable_name(parent)} = {{}}")
                    found.add(parent)

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

            obj_name = "body"
            field = prop_name
            parents = prop_data.get(OasField.X_PARENTS)
            if parents:
                obj_name = self.variable_name(parents[-1])
            x_field = prop_data.get(OasField.X_FIELD)
            if x_field:
                field = x_field
            if prop_data.get(OasField.REQUIRED):
                lines.append(f'{obj_name}["{field}"] = {var_name}')
            else:
                lines.append(f'if {var_name} is not None:')
                if dep_msg:
                    lines.append(f'    _l.logger().warning("{dep_msg}")')
                lines.append(f'    {obj_name}["{field}"] = {var_name}')

        if lineage:
            lines.append('# stitch together the sub-objects')
            depends = {}  # name to set of items
            for parents in lineage:
                prev = "body"
                for curr in parents:
                    items = depends.get(prev, [])
                    if curr not in items:
                        items.append(curr)
                    depends[prev] = items
                    prev = curr

            while depends:
                # this walks the tree backwards, so sub-objects get populated before
                # being checked if there's data in them
                removal = set()
                for parent, dependents in depends.items():
                    # look for a parent whose's dependents don't have any dependents
                    if all(d not in depends for d in dependents):
                        for child in dependents:
                            lines.append(f'if {self.variable_name(child)}:')
                            lines.append(f'    {self.variable_name(parent)}["{child}"] = {self.variable_name(child)}')
                        removal.add(parent)

                # remove items that were processed
                for r in removal:
                    depends.pop(r)

        return SEP1 + SEP1.join(lines)

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

    def clean_enum_name(self, value: str) -> bool:
        """Check to see if value can be directly used as a variable name."""
        if not isinstance(value, str):
            return False
        try:
            float(value)
            return False
        except ValueError:
            pass

        return True

    def enum_values_match_type(self, enum_type: str, values: list[Any]) -> bool:
        """Check if all values align with the proposed enum_type."""
        if enum_type in ('str', 'string'):
            return True  # everything can be expressed as a string

        supported = str
        if enum_type == 'integer':
            supported = int
        elif enum_type in ('numeric', 'number'):
            supported = (float, int)
        elif enum_type == 'boolean':
            supported = bool

        return all(isinstance(v, supported) for v in values)

    def enum_find_schema(self, schema_types: list[str], enum_values: list[Any]) -> list[str]:
        """Resolve to single schema type (if possible)."""
        # take the first schema_type item where the values match the type
        return [
            enum_type for enum_type in schema_types if self.enum_values_match_type(enum_type, enum_values)
        ]

    def enum_stringify(self, schema: dict[str, Any]) -> None:
        """Update the schema to have string values for enum and default values."""
        enum_values = schema.get(OasField.ENUM)
        if isinstance(enum_values, list):
            enum_values = [str(v) for v in enum_values]
        schema[OasField.ENUM.value] = enum_values

        def_val = schema.get(OasField.DEFAULT)
        if isinstance(def_val, list):
            def_val = [str(v) for v in def_val]
        elif def_val is not None:
            def_val = str(def_val)
        schema[OasField.DEFAULT.value] = def_val

        return

    def enum_declaration(self, name: str, enum_type: str, values: list[Any]) -> str:
        """Turn data into an enum declation."""
        prefix = "" if enum_type == "str" else "VALUE_"
        if not all(self.clean_enum_name(v) for v in values):
            prefix = "VALUE_"

        names = [self.variable_name(str(v)).upper() for v in values]
        duplicates = {x for x in names if names.count(x) > 1}
        dup_counts = dict.fromkeys(duplicates, 0)
        declarations = []
        for v in values:
            base_name = self.variable_name(str(v)).upper()
            suffix = ""
            if base_name in dup_counts:
                suffix = dup_counts[base_name]
                dup_counts[base_name] = suffix + 1
            item_name = f"{prefix}{base_name}{suffix}"
            value = quoted(str(v)) if enum_type == "str" else maybe_quoted(v)
            declarations.append(f"{item_name} = {value}")

        # NOTE: the noqa is due to potentially same definition ahead of multiple functions
        return f"class {name}({enum_type}, Enum):  # noqa: F811{SEP1}{SEP1.join(declarations)}{NL * 2}"

    def enum_definitions(
        self,
        path_params: list[dict[str, Any]],
        query_params: list[dict[str, Any]],
        body_params: dict[str, Any],
    ) -> str:
        """Create enum class definitions need to support the provided."""
        # collect all the enum types (mapped by name to avoid duplicates)
        enums = {}
        for param_data in path_params + query_params:
            values = param_data.get(OasField.ENUM)
            if not values:
                continue

            e_name = param_data.get(OasField.NAME)
            e_type = self.schema_to_pytype(param_data) or 'str'
            enums[self.class_name(e_name)] = (e_type, values)

        for name, prop in body_params.items():
            values = prop.get(OasField.ENUM)
            if not values:
                continue
            e_type = self.schema_to_pytype(prop) or 'str'
            enums[self.class_name(name)] = (e_type, values)

        if not enums:
            return ""

        # declare all the types
        declarations = []
        for e_name, (e_type, e_values) in enums.items():
            declarations.append(self.enum_declaration(e_name, e_type, e_values))

        return NL + NL.join(declarations)

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
    {self.op_long_help(op)}# handler for {node.identifier}: {method} {path}
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
