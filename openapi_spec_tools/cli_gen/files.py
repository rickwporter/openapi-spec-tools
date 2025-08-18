"""Implementation for creating/copying CLI files."""
import os
from pathlib import Path
from typing import Any

from openapi_spec_tools.base_gen._logging import get_logger
from openapi_spec_tools.base_gen.files import copy_and_update
from openapi_spec_tools.base_gen.files import copyright
from openapi_spec_tools.base_gen.utils import to_snake_case
from openapi_spec_tools.cli_gen._tree import TreeField
from openapi_spec_tools.cli_gen._tree import TreeNode
from openapi_spec_tools.cli_gen.cli_generator import CliGenerator
from openapi_spec_tools.cli_gen.constants import GENERATOR_LOG_CLASS
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations

# Maps the source to destination (currently all the same).
BASE_GEN = Path(__file__).parent.parent / "base_gen"
CLI_GEN = Path(__file__).parent
INFRASTRUCTURE_FILES = {
    BASE_GEN / "_logging.py": "_logging.py",
    BASE_GEN / "_requests.py": "_requests.py",
    CLI_GEN / "_arguments.py": "_arguments.py",
    CLI_GEN / "_console.py": "_console.py",
    CLI_GEN / "_display.py": "_display.py",
    CLI_GEN / "_exceptions.py": "_exceptions.py",
    CLI_GEN / "_tree.py": "_tree.py",
}

TEST_DIR = Path(__file__).parent.parent.parent / "tests"
BASE_TEST = TEST_DIR / "base_gen"
CLI_TEST = TEST_DIR / "cli_gen"
TEST_FILES = {
    BASE_TEST / "test_logging.py": "test_logging.py",
    BASE_TEST / "test_requests.py": "test_requests.py",
    CLI_TEST / "__init__.py": "__init__.py",
    CLI_TEST / "helpers.py": "helpers.py",
    CLI_TEST / "test_console.py": "test_console.py",
    CLI_TEST / "test_display.py": "test_display.py",
    CLI_TEST / "test_exceptions.py": "test_exceptions.py",
    CLI_TEST / "test_main.py": "test_main.py",
    CLI_TEST / "test_tree.py": "test_tree.py",
}

logger = get_logger(GENERATOR_LOG_CLASS)


def generate_node(generator: CliGenerator, node: LayoutNode, directory: str) -> None:
    """Create a file/module for the current node, and recursively goes through sub-commands."""
    module_name = to_snake_case(node.identifier)
    logger.info(f"Generating {module_name} module")
    text = generator.shebang()
    text += copyright()
    text += generator.standard_imports()
    text += generator.subcommand_imports(node.subcommands())
    text += generator.app_definition(node)
    text += generator.tree_function(node)
    for command in node.operations():
        text += generator.function_definition(command)
    text += generator.main()

    filename = os.path.join(directory, module_name + ".py")
    with open(filename, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(text)
    os.chmod(filename, 0o755)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        generate_node(generator, command, directory)


def generate_tree_node(generator: CliGenerator, node: LayoutNode) -> TreeNode:
    """Generate a TreeNode hierarchy for the specified node."""
    data = generator.tree_data(node)
    children = []
    for item in data.get(TreeField.OPERATIONS, []):
        op_id = item.get(TreeField.OP_ID)
        if not op_id:
            continue
        op = TreeNode(
            name=item.get(TreeField.NAME),
            help=item.get(TreeField.HELP),
            operation=item.get(TreeField.OP_ID),
            function=item.get(TreeField.FUNC),
            method=item.get(TreeField.METHOD),
            path=item.get(TreeField.PATH),
        )
        children.append(op)

    for sub in node.subcommands():
        children.append(generate_tree_node(generator, sub))

    return TreeNode(
        name=data.get(TreeField.NAME),
        help=data.get(TreeField.DESCRIPTION),
        children=children,
    )


def generate_tree_file(generator: CliGenerator, node: LayoutNode, directory: str) -> None:
    """Create the YAML file."""
    filename = os.path.join(directory, "tree.yaml")
    with open(filename, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(copyright())
        fp.write(generator.get_tree_yaml(node))


def check_for_missing(node: LayoutNode, oas: dict[str, Any]) -> dict[str, list[str]]:
    """Look for operations in node (and children) that are NOT in the OpenAPI spec."""
    def _check_missing(node: LayoutNode, ops: dict[str, Any]) -> dict[str, list[str]]:
        current = []
        for op in node.operations():
            if op.identifier not in operations:
                current.append(op.identifier)

        if not current:
            return {}
        return {node.identifier: current}


    operations = map_operations(oas.get(OasField.PATHS, {}))
    missing = _check_missing(node, operations)

    # recursively do the same for sub-commands
    for command in node.subcommands():
        missing.update(_check_missing(command, operations))

    return missing


def find_unreferenced(node: LayoutNode, oas: dict[str, Any]) -> dict[str, Any]:
    """Find the operations in the OAS that are unrerenced by the commands."""
    def _find_operations(_node: LayoutNode) -> set[str]:
        """Recursively finds all the operations for this node and it's children."""
        current = set()
        for op in _node.operations(include_bugged=True):
            current.add(op.identifier)
        for child in _node.subcommands(include_bugged=True):
            current.update(_find_operations(child))
        return current

    referenced = _find_operations(node)
    ops = map_operations(oas.get(OasField.PATHS))
    unreferenced = {
        op_id: op_data
        for op_id, op_data in ops.items()
        if op_id not in referenced
    }

    return unreferenced


def copy_infrastructure(dst_dir: str, package_name: str):
    """Iterate over the INFRASTRUCTURE_FILES, and copies from local to dst."""
    dpath = Path(dst_dir)
    replacements = {
        __package__: package_name,
        "openapi_spec_tools.base_gen": package_name,
    }
    for src, dst in INFRASTRUCTURE_FILES.items():
        dfile = dpath / dst
        copy_and_update(src.as_posix(), dfile.as_posix(), replacements)


def copy_tests(dst_dir: str, package_name: str, main_module: str):
    """Iterate over the TEST_FILES, and copies from local to dst."""
    dpath = Path(dst_dir)
    test_package = "tests"
    parts = dpath.as_posix().split("tests/", 1)
    if len(parts) > 1:
        test_package += '.' + parts[1].replace('/', '.').rstrip('.')

    replacements = {
        "from tests.assets.arg_test": f"from {package_name}.{main_module}",  # needed for test_main.py
        __package__: package_name,
        "openapi_spec_tools.base_gen": package_name,
        "tests.cli_gen": test_package,
        "tests.base_gen": test_package,
    }
    for src, dst in TEST_FILES.items():
        dfile = dpath / dst
        copy_and_update(src.as_posix(), dfile.as_posix(), replacements)
