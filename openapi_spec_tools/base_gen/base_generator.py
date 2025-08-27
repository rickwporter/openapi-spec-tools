"""Declares the Generator class that is used for most of the CLi generation capability."""
import logging
import textwrap
from copy import deepcopy
from typing import Any
from typing import Optional

from openapi_spec_tools.base_gen._logging import init_logging
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.constants import NL
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.constants import SEP2
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import prepend
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import replace_special
from openapi_spec_tools.base_gen.utils import set_missing
from openapi_spec_tools.base_gen.utils import shallow
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.base_gen.utils import to_camel_case
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.types import ContentType
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import NULL_TYPES
from openapi_spec_tools.utils import map_operations

LOG_CLASS = "base-gen"

class BaseGenerator:
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(self, oas: dict[str, Any], logger: Optional[logging.Logger] = None):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
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
        self.logger = logger or init_logging("INFO", LOG_CLASS)

        # This is an incomplete list of Python builtins that should avoided in variable names
        self.reserved = {
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
        self.conflict_suffix = "_"

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
        return "--" + value.replace("_", "-")

    def short_reference_name(self, full_name: str) -> str:
        """Transform the '#/components/schemas/Xxx' to 'Xxx'."""
        return full_name.split('/')[-1]

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

    def op_body_schema(self, operation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        """Get the name and schema dictionary."""
        body = self.op_get_body(operation)
        if not body:
            return ("None", {})

        schema = body.get(OasField.SCHEMA, {})
        name = "body"
        ref = schema.get(OasField.REFS)
        if ref:
            name = self.short_reference_name(ref)
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

