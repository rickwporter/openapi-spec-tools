"""Declares the abstract ApiGenerator base class that is the basis for API generation.

This functionality that is useful for all API generators, and forces addition of function_definition()
for various. The abstract function allows the files.py to maintain the same interface.
"""
import logging
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import Optional

from openapi_spec_tools.base_gen.base_generator import BaseGenerator
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField


class ApiGenerator(BaseGenerator, ABC):
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(self, package_name: str, oas: dict[str, Any], logger: Optional[logging.Logger] = None):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
        super().__init__(oas, logger=logger)
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

    @abstractmethod
    def function_definition(self, command: LayoutNode) -> str:
        """Provide function definition for specified command."""
        pass  # pragma: no cover
