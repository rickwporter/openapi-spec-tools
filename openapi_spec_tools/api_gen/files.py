"""Implementation for creating/copying CLI files."""
import os

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.base_gen._logging import get_logger
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.layout.types import LayoutNode

logger = get_logger(GENERATOR_LOG_CLASS)


def generate_api_node(generator: ApiGenerator, node: LayoutNode, directory: str) -> None:
    """Create a file/module for the current node, and recursively goes through sub-commands."""
    if node.operations():
        module_name = to_snake_case(node.identifier)
        logger.info(f"Generating {module_name} module")
        text = generator.copyright
        text += generator.standard_imports()
        for command in node.operations():
            text += generator.function_definition(command)

        filename = os.path.join(directory, module_name + ".py")
        with open(filename, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        generate_api_node(generator, command, directory)
