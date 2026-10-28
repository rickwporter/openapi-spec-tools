"""Declares the Generator class that is used for most of the CLi generation capability."""
import logging
import textwrap
from copy import deepcopy
from pathlib import Path
from typing import Any

from openapi_spec_tools.base_gen._logging import init_logging
from openapi_spec_tools.base_gen.config import GeneratorConfig
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.constants import DEFAULT_CONFLICT_SUFFIX
from openapi_spec_tools.base_gen.constants import DEFAULT_COPYRIGHT
from openapi_spec_tools.base_gen.constants import DEFAULT_MAX_HELP_LENGTH
from openapi_spec_tools.base_gen.constants import DEFAULT_RESERVED
from openapi_spec_tools.base_gen.constants import DEFAULT_SUPPORTED_CONTENT
from openapi_spec_tools.base_gen.constants import DEFAULT_VALUE_LOG_LEVEL
from openapi_spec_tools.base_gen.constants import DEFAULT_VALUE_TIMEOUT
from openapi_spec_tools.base_gen.constants import DEFAULT_VAR_HOST
from openapi_spec_tools.base_gen.constants import DEFAULT_VAR_KEY
from openapi_spec_tools.base_gen.constants import DEFAULT_VAR_LOG_LEVEL
from openapi_spec_tools.base_gen.constants import DEFAULT_VAR_TIMEOUT
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.constants import SEP2
from openapi_spec_tools.base_gen.files import copy_and_update
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import replace_special
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.base_gen.utils import to_camel_case
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.constants import NULL_TYPES
from openapi_spec_tools.expand import expand_schema
from openapi_spec_tools.flatten import flatten_schema
from openapi_spec_tools.flatten import is_simple_type
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import _or
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import reference_classname

LOG_CLASS = "base-gen"


class BaseGenerator:
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(
        self,
        oas: dict[str, Any],
        logger: logging.Logger | None = None,
        config: GeneratorConfig | None = None,
        package_name: str | None = None,
        supported_content: list[ContentType] | None = None,
        max_help_length: int | None = None,
        reserved: set[str] | None = None,
        conflict_suffix: str | None = None,
        copyright: str | Path | None = None,
        infra_files: dict[Path, str] | None = None,
        infra_replacements: dict[str, str] | None = None,
        test_files: dict[Path, str] | None = None,
        test_replacements: dict[str, str] | None = None,
        env_host: str | list[str] | None = None,
        env_key: str | list[str] | None = None,
        env_timeout: str | list[str] | None = None,
        env_log_level: str | list[str] | None = None,
        default_host: str | None = None,
        default_log_level: str | None = None,
        default_timeout: int | None = None,
    ):
        """Initialize with the OpenAPI spec and other data for generating multiple modules.

        When copyright names an existing file, that file's contents are stored as copyright.
        Otherwise the provided value is used as the copyright text. The default header is used
        when copyright is omitted.

        When the default_host is not provided, attempts to read from the OAS servers.

        Default values are as follows (see openapi_spec_tools.base_gen.constants for values):
        * package_name - no default, required
        * supported_content - DEFAULT_SUPPORTED_CONTENT
        * max_help_length - DEFAULT_MAX_HELP_LENGTH
        * reserved - DEFAULT_RESERVED
        * conflict_suffix - DEFAULT_CONFLICT_SUFFIX
        * copyright - DEFAULT_COPYRIGHT
        * infra_<files|replacements> - None, likely specified by derived class methods
        * test_<files|replacements> - None, likely specified by derived class methods
        * env_host - DEFAULT_VAR_HOST
        * env_key - DEFAULT_VAR_KEY
        * env_timeout - DEFAULT_VAR_TIMEOUT
        * env_log_level - DEFAULT_VAR_LOG_LEVEL
        * default_host - empty string
        * default_log_level - DEFAULT_VALUE_LOG_LEVEL
        * default_timeout - DEFAULT_VALUE_TIMEOUT
        """
        config = config or GeneratorConfig()  # reduce logic by creating a default (if no config provided)
        self.operations = map_operations(oas.get(OasField.PATHS, {}))
        self.components = oas.get(OasField.COMPONENTS, {})
        self.logger = logger or init_logging("INFO", LOG_CLASS)

        self.package_name = _or(package_name, config.package_name, ValueError("Missing package_name"))
        self.default_host = _or(default_host, config.default_host, "")
        self.supported = _or(supported_content, config.supported_content, DEFAULT_SUPPORTED_CONTENT)
        self.max_help_length = _or(max_help_length, config.max_help_length, DEFAULT_MAX_HELP_LENGTH)
        self.reserved = _or(reserved, config.reserved, DEFAULT_RESERVED)
        self.conflict_suffix = _or(conflict_suffix, config.conflict_suffix, DEFAULT_CONFLICT_SUFFIX)
        self.copyright = self._resolve_copyright(_or(copyright, config.copyright))
        self.infra_files = _or(infra_files, config.resolve_path_keys(config.infra_files))
        self.infra_replacements = _or(infra_replacements, config.infra_replacements)
        self.test_files = _or(test_files, config.resolve_path_keys(config.test_files))
        self.test_replacements = _or(test_replacements, config.test_replacements)
        self.env_host = _or(env_host, config.env_host, DEFAULT_VAR_HOST)
        self.env_key = _or(env_key, config.env_key, DEFAULT_VAR_KEY)
        self.env_timeout = _or(env_timeout, config.env_timeout, DEFAULT_VAR_TIMEOUT)
        self.env_log_level = _or(env_log_level, config.env_log_level, DEFAULT_VAR_LOG_LEVEL)
        self.default_log = _or(default_log_level, config.default_log_level, DEFAULT_VALUE_LOG_LEVEL)
        self.default_timeout = _or(default_timeout, config.default_timeout, DEFAULT_VALUE_TIMEOUT)

        if not self.default_host:
            servers = oas.get(OasField.SERVERS)
            if servers:
                self.default_host = servers[0].get(OasField.URL, "")


    @staticmethod
    def _resolve_copyright(copyright: str | Path | None) -> str:
        """Load copyright header text from a file, or use the provided text."""
        if copyright is None:
            return DEFAULT_COPYRIGHT

        text = copyright if isinstance(copyright, str) else DEFAULT_COPYRIGHT
        try:
            path = Path(copyright)
            if path.is_file():
                return path.read_text(encoding="utf-8")
        except (TypeError, ValueError, OSError):
            pass

        return text

    def default_infra_files(self) -> dict[Path, str]:
        """Default map of infrastructure files to copy."""
        return {}

    def default_infra_replacements(self) -> dict[str, str]:
        """Default map of infrastructure file line replacements."""
        return {}

    def default_test_files(self) -> dict[Path, str]:
        """Default map of test files to copy."""
        return {}

    def default_test_replacements(self) -> dict[str, str]:
        """Default map of test file line replacements."""
        return {}

    def class_name(self, s: str) -> str:
        """Get the class name for provided string."""
        value = to_camel_case(replace_special(s)).replace("_", "")
        return value[0].upper() + value[1:]

    def function_name(self, s: str) -> str:
        """Get the function name for the provided string."""
        vname = to_snake_case(replace_special(s))
        if vname in self.reserved:
            return f"{vname}{self.conflict_suffix}"

        return vname

    def variable_name(self, s: str) -> str:
        """Get the variable name for the provided string."""
        vname = to_snake_case(replace_special(s))
        if vname in self.reserved:
            return f"{vname}{self.conflict_suffix}"

        return vname

    def option_name(self, s: str) -> str:
        """Get the typer option name for the provided string."""
        value = to_snake_case(replace_special(s))
        return "--" + value.rstrip("_").replace("_", "-")

    def shebang(self) -> str:
        """Get the shebang line that goes at the top of each file."""
        return "#!/usr/bin/env python3\n"

    def op_short_help(self, operation: dict[str, Any]) -> str:
        """Get the short help for the operation."""
        summary = operation.get(OasField.SUMMARY)
        if summary:
            return simple_escape(summary.strip())

        description = operation.get(OasField.DESCRIPTION, "")
        return simple_escape(description.strip().split(". ")[0])

    def op_doc_string(self, operation: dict[str, Any]) -> str:
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

    def op_request_content(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get the `content` (if any) from the `requestBody`."""
        return operation.get(OasField.REQ_BODY, {}).get(OasField.CONTENT, {})

    def op_get_content_type(self, operation: dict[str, Any]) -> str | None:
        """Get the first content-type matching a supported type."""
        content = self.op_request_content(operation)
        for ct in self.supported:
            if ct.value in content:
                return ct.value
        return None

    def op_request_body(self, operation: dict[str, Any]) -> dict[str, Any] | None:
        """Get the first request body matching a supported type."""
        content = self.op_request_content(operation)
        for ct in self.supported:
            body = content.get(ct.value)
            if body:
                return body

        return None

    def model_settable_properties(self, name: str, model: dict[str, Any]) -> dict[str, Any]:
        """Expand the model into a dictionary of properties."""
        expanded = expand_schema(model, self.components, name)
        flattened = flatten_schema(expanded)

        # filter out read-only properties, and complex properties that CLI cannot deal with
        settable = {
            name: data
            for name, data in flattened.get(OasField.PROPS, {}).items()
            if not data.get(OasField.READ_ONLY, False) and is_simple_type(data)
        }

        return settable

    def op_body_schema(self, operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Get the name and schema dictionary."""
        body = self.op_request_body(operation)
        if not body:
            return ("None", {})

        schema = body.get(OasField.SCHEMA, {})
        name = "body"
        ref = schema.get(OasField.REFS)
        if ref:
            name = reference_classname(ref)
            schema = self.get_model(ref)

        return (name, schema)

    def op_body_settable_properties(self, operation: dict[str, Any]) -> dict[str, Any]:
        """Get a dictionary of settable body properties."""
        name, schema = self.op_body_schema(operation)
        if not schema:
            return {}

        # attempt to simplify enum types to a single type to something that matches
        properties = self.model_settable_properties(name, schema)
        for prop_data in properties.values():
            self.update_enum(prop_data)

        return properties

    def schema_to_type(self, schema: str, fmt: str | None) -> str | None:
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

            # find first item from schema this is a non-null type
            item = next((item for item in schema if item in reduced), None)
            if item is not None:
                self.logger.debug(f"Choosing {item} type from {', '.join(schema)}")
                return item

        self.logger.warning(f"Unable to simplify type for {schema}")
        return None


    def schema_to_pytype(self, schema: dict[str, Any]) -> str | None:
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
            name = param_data.get(OasField.X_ENUM) or param_data.get(OasField.NAME)
            return self.class_name(name)

        py_type = self.schema_to_pytype(param_data)
        if py_type:
            return py_type

        oas_type = self.simplify_type(param_data.get(OasField.TYPE))
        if oas_type == "object":
            return "dict[str, Any]"

        return None

    def get_property_pytype(self, prop_name: str, prop_data: dict[str, Any]) -> str | None:
        """Get the "basic" Python type from a property object.

        Each property potentially has 'type' and 'format' fields.
        """
        if prop_data.get(OasField.ENUM):
            base_name = prop_data.get(OasField.X_REF) or prop_name
            pytype = self.class_name(base_name)
        else:
            oas_type = self.simplify_type(prop_data.get(OasField.TYPE))
            if oas_type == "object":
                add_props = prop_data.get(OasField.ADDITIONAL_PROPS)
                if isinstance(add_props, dict):
                    add_prop_type = add_props.get(OasField.TYPE)
                    if add_prop_type:
                        prop_data.update({OasField.TYPE.value: add_prop_type})

            pytype = self.schema_to_pytype(prop_data)
            if not pytype:
                return pytype

        collection = COLLECTIONS.get(prop_data.get(OasField.X_COLLECT))
        if collection:
            pytype = f"{collection}[{pytype}]"
        if not prop_data.get(OasField.REQUIRED):
            pytype = f"{pytype} | None"

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
                item[OasField.X_REF] = reference_classname(ref)
            if item.get(OasField.IN) != location:
                continue

            # promote the schema items into item
            schema = item.pop(OasField.SCHEMA, {})
            item.update(schema)
            params.append(item)
        return params

    def param_to_property(self, param: dict[str, Any]) -> dict[str, Any]:
        """Convert parameter data to property data.

        Resolves parameter data to make it easier to digest (e.g. choosing any oneOf,
        collection information, required).
        """
        expanded = expand_schema(param, self.components)
        flattened = flatten_schema(expanded)
        self.update_enum(flattened)

        # flatten the type, too
        types = flattened.get(OasField.TYPE)
        if types and isinstance(types, list) and not NULL_TYPES.isdisjoint(types):
            # if the item is nullable, then remove the null type(s) and set required=False
            types = [t for t in types if t not in NULL_TYPES]
            flattened[OasField.TYPE.value] = types[0] if len(types) == 1 else types
            flattened[OasField.REQUIRED.value] = False

        return flattened

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
        forced_single = set()
        lineage = []
        for prop_data in body_params.values():
            parents = prop_data.get(OasField.X_PARENTS, [])
            if parents and parents not in lineage:
                lineage.append(parents)

            if prop_data.get(OasField.X_SINGLE):
                forced_single.add(parents[-1])

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
                            rval = self.variable_name(child)
                            if child in forced_single:
                                rval = f"[{rval}]  # convert to list"
                            lines.append(f'if {self.variable_name(child)}:')
                            lines.append(f'    {self.variable_name(parent)}["{child}"] = {rval}')
                        removal.add(parent)

                # remove items that were processed
                for r in removal:
                    depends.pop(r)

        return SEP1 + SEP1.join(lines)

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

    def update_enum(self, prop: dict[str, Any]) -> dict[str, Any]:
        """Update the property when it is an enum.

        In some cases, the type needs updating. And, when the enum type is string, it makes
        sure the possible values and default are strings.
        """
        enum_values = prop.get(OasField.ENUM)
        schema_type = prop.get(OasField.TYPE)
        if enum_values and isinstance(schema_type, list):
            schema_list = self.enum_find_schema(schema_type, enum_values)
            schema_type = schema_list[0]
            prop[OasField.TYPE.value] = schema_type

        # make sure the enumeration and default values align with the type
        if enum_values and schema_type == "string":
            self.enum_stringify(prop)

        return prop

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

            e_name = param_data.get(OasField.X_ENUM) or param_data.get(OasField.NAME)
            e_type = self.schema_to_pytype(param_data) or 'str'
            enums[self.class_name(e_name)] = (e_type, values)

        for name, prop in body_params.items():
            values = prop.get(OasField.ENUM)
            if not values:
                continue
            e_name = prop.get(OasField.X_ENUM) or name
            e_type = self.schema_to_pytype(prop) or 'str'
            enums[self.class_name(e_name)] = (e_type, values)

        if not enums:
            return ""

        # declare all the types
        declarations = []
        for e_name, (e_type, e_values) in enums.items():
            declarations.append(self.enum_declaration(e_name, e_type, e_values))

        return NL + NL.join(declarations)

    def copy_infrastructure_files(self, dst_dir: str) -> None:
        """Iterate over the infra_files and copy from local to dst."""
        dpath = Path(dst_dir)
        files = (
            self.infra_files
            if self.infra_files is not None
            else self.default_infra_files()
        )
        replacements = (
            self.infra_replacements
            if self.infra_replacements is not None
            else self.default_infra_replacements()
        )
        for src, dst in files.items():
            dfile = dpath / dst
            copy_and_update(src.as_posix(), dfile.as_posix(), replacements, self.copyright)

    def copy_test_files(self, dst_dir: str) -> None:
        """Iterate over the test_files and copy from local to dst."""
        dpath = Path(dst_dir)
        files = (
            self.test_files
            if self.test_files is not None
            else self.default_test_files()
        )
        replacements = (
            self.test_replacements
            if self.test_replacements is not None
            else self.default_test_replacements()
        )
        for src, dst in files.items():
            dfile = dpath / dst
            copy_and_update(src.as_posix(), dfile.as_posix(), replacements, self.copyright)

    def add_init_file(self, dst_dir: str, content: str = "", overwrite: bool = False) -> None:
        """Add __init__.py according to parameters."""
        dfile = Path(dst_dir) / "__init__.py"
        if not overwrite and dfile.exists():
            return

        dfile.write_text(content, encoding="utf-8", newline="\n")
