"""Implementation for creating/copying CLI files."""
import os
from pathlib import Path

from openapi_spec_tools.api_gen.api_generator import ApiGenerator
from openapi_spec_tools.base_gen._logging import get_logger
from openapi_spec_tools.base_gen.files import copy_and_update
from openapi_spec_tools.base_gen.files import copyright
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.layout.types import LayoutNode

# Maps the source to destination (currently all the same).
API_GEN = Path(__file__).parent
BASE_GEN = Path(__file__).parent.parent / "base_gen"
INFRASTRUCTURE_FILES = {
    BASE_GEN / "_logging.py": "_logging.py",
    BASE_GEN / "_requests.py": "_requests.py",
    API_GEN / "_environment.py": "_environment.py",
}

logger = get_logger(GENERATOR_LOG_CLASS)


def generate_api_node(generator: ApiGenerator, node: LayoutNode, directory: str) -> None:
    """Create a file/module for the current node, and recursively goes through sub-commands."""
    if node.operations():
        module_name = to_snake_case(node.identifier)
        logger.info(f"Generating {module_name} module")
        text = copyright()
        text += generator.standard_imports()
        for command in node.operations():
            text += generator.function_definition(command)

        filename = os.path.join(directory, module_name + ".py")
        with open(filename, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(text)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        generate_api_node(generator, command, directory)


def copy_api_infrastructure(dst_dir: str, package_name: str):
    """Iterate over the INFRASTRUCTURE_FILES, and copies from local to dst."""
    dpath = Path(dst_dir)
    replacements = {
        __package__: package_name,
        "openapi_spec_tools.api_gen": package_name,
        "openapi_spec_tools.base_gen": package_name,
    }
    for src, dst in INFRASTRUCTURE_FILES.items():
        dfile = dpath / dst
        copy_and_update(src.as_posix(), dfile.as_posix(), replacements)
