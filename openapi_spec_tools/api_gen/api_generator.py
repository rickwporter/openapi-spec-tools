"""Declares the abstract ApiGenerator base class that is the basis for API generation.

This functionality that is useful for all API generators, and forces addition of function_definition()
for various. The abstract function allows the files.py to maintain the same interface.
"""
from abc import ABC
from abc import abstractmethod
from typing import Any

from openapi_spec_tools.base_gen.base_generator import BaseGenerator
from openapi_spec_tools.base_gen.constants import COLLECTIONS
from openapi_spec_tools.base_gen.constants import SEP1
from openapi_spec_tools.base_gen.utils import maybe_quoted
from openapi_spec_tools.base_gen.utils import quoted
from openapi_spec_tools.base_gen.utils import simple_escape
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField

DEFAULT_VAR_HOST = "API_HOST"
DEFAULT_VAR_KEY = "API_KEY"
DEFAULT_VAR_TIMEOUT = "API_TIMEOUT"
DEFAULT_VAR_LOG_LEVEL = "API_LOG_LEVEL"
DEFAULT_VALUE_LOG_LEVEL = "info"
DEFAULT_VALUE_TIMEOUT = 5


class ApiGenerator(BaseGenerator, ABC):
    """Provides the majority of the CLI generation functions.

    Store a few key things to avoid the need for passing them all around, but most of the "action"
    is driven by an outside actor. This was done in an object-oriented fashion so pieces can be
    overridden by consumers.
    """

    def __init__(
        self,
        package_name: str,
        oas: dict[str, Any],
        env_host: str = DEFAULT_VAR_HOST,
        env_key: str = DEFAULT_VAR_KEY,
        env_timeout: str = DEFAULT_VAR_TIMEOUT,
        env_log_level: str = DEFAULT_VAR_LOG_LEVEL,
        default_log_level: str = DEFAULT_VALUE_LOG_LEVEL,
        default_timeout: int = DEFAULT_VALUE_TIMEOUT,
        **kwargs,
    ):
        """Initialize with the OpenAPI spec and other data for generating multiple modules."""
        super().__init__(oas, **kwargs)
        self.package_name = package_name
        self.env_host = env_host
        self.env_key = env_key
        self.env_timeout = env_timeout
        self.env_log_level = env_log_level
        self.default_log = default_log_level
        self.default_timeout = default_timeout

    def property_help(self, prop: dict[str, Any]) -> str:
        """Get the short help string for the specified property."""
        help = prop.get(OasField.SUMMARY) or prop.get(OasField.DESCRIPTION) or ""
        short_ref = prop.get(OasField.X_REF)
        choices = prop.get(OasField.ENUM)
        required = prop.get(OasField.REQUIRED)

        if help:
            if len(help) > self.max_help_length:
                help = help.split(". ")[0].strip()[:self.max_help_length] + '...'
        elif short_ref:
            help = f"see {short_ref} for info"
        elif choices:
            help = f"choices: {', '.join([str(_) for _ in choices])}"

        if required and "require" not in help.lower():
            if not help.endswith(" "):
                help += " "
            help += "[required]"

        if not help:
            return ""
        return f"  # {simple_escape(help)}"

    def op_body_arguments(self, body_params: list[dict[str, Any]]) -> list[str]:
        """Convert the body parameters dictionary into a list of API function arguments/help."""
        args = []
        for prop_name, prop_data in body_params.items():
            prop_data[OasField.NAME.value] = prop_name
            arg = self.property_to_argument(prop_data, allow_required=False)
            args.append(arg)

        return args

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

    def init_infra_args(self, operation: dict[str, Any]) -> str:
        """Provide initialization of standard arguments inside body."""
        host_default = (
            f'_e.env_string({quoted(self.env_host)}, '
            f'default={quoted(self.default_host)}, except_missing=True)'
        )
        key_default = f'_e.env_string({quoted(self.env_key)}, except_missing=True)'
        timeout_default = f'_e.env_int({quoted(self.env_timeout)}, default={self.default_timeout})'
        log_default = f'_e.env_string({quoted(self.env_log_level)}, default={quoted(self.default_log)})'
        lines = [
            f'_api_host = _api_host or {host_default}',
            f'_api_key = _api_key or {key_default}',
            f'_api_timeout = _api_timeout or {timeout_default}',
            f'_log_level = _log_level or {log_default}',
        ]
        return SEP1.join(lines)


    def command_infra_arguments(self, command: LayoutNode) -> list[str]:
        """Get the standard CLI function arguments to the command."""
        host_help = f'API host, read from {self.env_host} if not provided'
        if self.default_host:
            host_help += f', defaults to {self.default_host}'
        key_help = f'API key for bearer auth, read from {self.env_key} if not provided'
        timeout_help = (
            f'timeout for operation, read from {self.env_timeout} if not provided, '
            f'defaults to {self.default_timeout}'
        )
        log_help = f'log level, read from {self.env_log_level} if not provided, defaults to {self.default_log}'
        args = [
            f'_api_host: Optional[str] = None,  # {host_help}',
            f'_api_key: Optional[str] = None,  # {key_help}',
            f'_api_timeout: Optional[int] = None,  # {timeout_help}',
            f'_log_level: Optional[str] = None,  # {log_help}',
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
