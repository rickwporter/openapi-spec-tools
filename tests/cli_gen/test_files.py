from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.cli_gen.cli_generator import CliGenerator
from openapi_spec_tools.cli_gen.files import check_for_missing
from openapi_spec_tools.cli_gen.files import copy_infrastructure
from openapi_spec_tools.cli_gen.files import copy_tests
from openapi_spec_tools.cli_gen.files import find_unreferenced
from openapi_spec_tools.cli_gen.files import generate_node
from openapi_spec_tools.cli_gen.files import generate_tree_node
from openapi_spec_tools.layout.utils import file_to_tree
from openapi_spec_tools.utils import open_oas
from tests.helpers import asset_filename


def test_generate_node_single():
    pkg_name = "cli_pkg"
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets.yaml"))
    directory = TemporaryDirectory()
    generator = CliGenerator(pkg_name, oas)
    generate_node(generator, tree, directory.name)

    path = Path(directory.name)
    file = path / "main.py"
    assert file.exists()

    text = file.read_text()
    assert "#!/usr/bin/env python3" in text
    assert f"Copyright {datetime.now().year}" in text
    assert "from typing import Annotated" in text
    assert 'app = typer.Typer(no_args_is_help=True, help="Manage pets")' in text
    assert 'if __name__ == "__main__":' in text

    expected = [
        # app.command stuff
        '@app.command("add", short_help="Create a pet")',
        '@app.command("delete", short_help="Delete a pet")',
        '@app.command("list", short_help="List all pets")',
        '@app.command("show", short_help="Info for a specific pet")',

        # function definitions - partial to allow for expansion
        'def create_pets',
        'def delete_pet_by_id',
        'def list_pets',
        'def show_pet_by_id',

        # NOTE: function doc-strings are same as help strings
        '# handler for createPets: POST /pets',
        '# handler for deletePetById: DELETE /pets/{petId}',
        '# handler for listPets: GET /pets',
        '# handler for showPetById: GET /pets/{petId}',
    ]
    for v in expected:
        assert v in text


def test_generate_node_multiple():
    pkg_name = "cli_pkg"
    oas = open_oas(asset_filename("pets_and_vets.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    directory = TemporaryDirectory()
    generator = CliGenerator(pkg_name, oas)
    generate_node(generator, tree, directory.name)

    path = Path(directory.name)
    expectations = {
        "main": [
            'app.add_typer(owners, name="owners")',
            'app.add_typer(pets, name="pet")',
            'app.add_typer(veterinarians, name="vets")',
        ],
        "owners": [
            '@app.command("create", short_help="Create a pet owner")',
            '@app.command("delete", short_help="Delete an owner")',
            '@app.command("pets", short_help="List owners pets")',
            '@app.command("update", short_help="Update an owner")',
        ],
        "pets": [
            '@app.command("create", short_help="Create a pet")',
            '@app.command("delete", short_help="Delete a pet")',
            '@app.command("update", short_help="Info for a specific pet")',
        ],
        "pets_examine":[
            '@app.command("blood-pressure", short_help="Record result of blood-pressure")',
            '@app.command("heart-rate", short_help="Record result of heart-rate")',
        ],
        "veterinarians": [
            '@app.command("add", short_help="Create a veterinarian")',
            '@app.command("delete", short_help="Delete a veterinarian")',
        ],
    }

    for module_name, expected in expectations.items():
        file = path / f"{module_name}.py"
        assert file.exists()

        text = file.read_text()
        assert "#!/usr/bin/env python3" in text
        assert f"Copyright {datetime.now().year}" in text
        assert "from typing import Annotated" in text
        assert 'app = typer.Typer(no_args_is_help=True, ' in text
        assert 'if __name__ == "__main__":' in text

        for v in expected:
            assert v in text


def test_generate_node_skip_bugged():
    pkg_name = "cli_pkg"
    oas = open_oas(asset_filename("pets_and_vets.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    directory = TemporaryDirectory()
    generator = CliGenerator(pkg_name, oas)

    # create a sub-command a bug
    node = tree.find("owners")
    node.bugs = ["abc"]

    # create an operation with bugs
    node = tree.find("pet", "delete")
    node.bugs = ["123", "456"]

    generate_node(generator, tree, directory.name)

    # test differences from above
    path = Path(directory.name)
    file = path / "owners.py"
    assert not file.exists()

    unexpectations = {
        "main": [
            'app.add_typer(owners, name="owners")',
        ],
        "pets": [
            '@app.command("delete", short_help="Delete a pet")',
        ],
    }

    for module_name, unexpected in unexpectations.items():
        file = path / f"{module_name}.py"
        assert file.exists()

        text = file.read_text()
        assert "#!/usr/bin/env python3" in text
        assert f"Copyright {datetime.now().year}" in text
        assert "from typing import Annotated" in text
        assert 'app = typer.Typer(no_args_is_help=True, ' in text
        assert 'if __name__ == "__main__":' in text

        for v in unexpected:
            assert v not in text


@pytest.mark.parametrize(
    ["oas_filename", "layout_filename", "expected"],
    [
        pytest.param("pet2.yaml", "layout_pets.yaml", {'list', 'show', 'add', 'delete'}, id="simple"),
        pytest.param("pets_and_vets.yaml", "layout_pets2.yaml", {'owners', 'pet', 'vets'}, id="subcommands"),
    ]
)
def test_generate_tree_node(oas_filename, layout_filename, expected):
    oas = open_oas(asset_filename(oas_filename))
    layout = file_to_tree(asset_filename(layout_filename))
    generator = CliGenerator("cli", oas)
    tree = generate_tree_node(generator, layout)
    names = {node.name for node in tree.children}
    assert expected == names


@pytest.mark.parametrize(
    ["layout_asset", "oas_asset", "expected"],
    [
        pytest.param("layout_pets2.yaml", "pets_and_vets.yaml", {}, id="all-found"),
        pytest.param(
            "layout_pets2.yaml",
            "pet.yaml",
            {
                'owners': ['createOwner', 'deleteOwner', 'listOwnerPets', 'updateOwner'],
                'pets': ['deletePetById'],
                'veterinarians': ['createVet', 'deleteVet'],
            },
            id="missing",
        ),
    ]
)
def test_generate_check_missing(layout_asset: str, oas_asset: str, expected: dict[str, list[str]]):
    tree = file_to_tree(asset_filename(layout_asset))
    oas = open_oas(asset_filename(oas_asset))
    assert expected == check_for_missing(tree, oas)


@pytest.mark.parametrize(
    ["layout_file", "oas_file", "expected_keys"],
    [
        pytest.param("layout_pets.yaml", "pet.yaml", [], id="empty"),
        pytest.param(
            "layout_pets.yaml",
            "pets_and_vets.yaml",
            [
                'createOwner',
                'deleteOwner',
                'updateOwner',
                'listOwnerPets',
                'checkPetBloodPressure',
                'checkPetHeartRate',
                'appVersion',
                'createVet',
                'deleteVet',
            ],
            id="multiple",
        ),
        pytest.param(
            "layout_pets2.yaml",
            "pets_and_vets.yaml",
            ['listPets', 'appVersion'],
            id="deeper",
        ),
        pytest.param(
            "layout_pets3.yaml",
            "pets_and_vets.yaml",
            ['listPets', 'appVersion'],
            id="bugged",
        )
    ]
)
def test_find_unreferenced(layout_file, oas_file, expected_keys):
    tree = file_to_tree(asset_filename(layout_file))
    oas = open_oas(asset_filename(oas_file))
    unreferenced = find_unreferenced(tree, oas)
    assert set(expected_keys) == unreferenced.keys()


def test_copy_infrastructure():
    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name)
    package = "another.package"

    copy_infrastructure(dst_path.as_posix(), package)

    filenames = {i.name for i in dst_path.iterdir()}
    expected = {
        "_arguments.py",
        "_console.py",
        "_display.py",
        "_exceptions.py",
        "_logging.py",
        "_requests.py",
        "_tree.py",
    }
    assert filenames == expected


def test_copy_tests():
    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name)
    package = "my.package"

    copy_tests(dst_path.as_posix(), package, "foo")

    filenames = {i.name for i in dst_path.iterdir()}
    expected = {
        "__init__.py",
        "helpers.py",
        "test_console.py",
        "test_display.py",
        "test_exceptions.py",
        "test_logging.py",
        "test_main.py",
        "test_requests.py",
        "test_tree.py",
    }
    assert filenames == expected


def test_copy_tests_long_path():
    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name) / "tests" / "foo" / "bar"
    dst_path.mkdir(parents=True)
    package = "my.package"

    copy_tests(dst_path.as_posix(), package, "foo")

    # spot check the package name updates
    dst_file = dst_path / "test_display.py"
    text = dst_file.read_text(encoding="utf-8", errors="ignore")
    assert 'from tests.foo.bar.helpers import to_ascii' in text
