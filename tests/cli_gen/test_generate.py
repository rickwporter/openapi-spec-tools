from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from oas_tools.cli_gen.generate import COPYRIGHT
from oas_tools.cli_gen.generate import check_for_missing
from oas_tools.cli_gen.generate import copy_and_update
from oas_tools.cli_gen.generate import copy_infrastructure
from oas_tools.cli_gen.generate import generate_node
from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.utils import open_oas
from tests.helpers import asset_filename


def test_generate_node_single():
    pkg_name = "cli_pkg"
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets.yaml"))
    directory = TemporaryDirectory()
    generator = Generator(pkg_name, oas)
    generate_node(generator, tree, directory.name)

    path = Path(directory.name)
    file = path / "main.py"
    assert file.exists()

    text = file.read_text()
    assert "#!/usr/bin/env python3" in text
    assert f"Copyright {datetime.now().year}" in text
    assert "from typing_extensions import Annotated" in text
    assert 'app = typer.Typer(no_args_is_help=True, help="Manage pets")' in text
    assert 'if __main__ == "__main__":'

    expected = [
        # app.command stuff
        '@app.command("add", help="Create a pet")',
        '@app.command("delete", help="Delete a pet")',
        '@app.command("list", help="List all pets")',
        '@app.command("show", help="Info for a specific pet")',

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
    generator = Generator(pkg_name, oas)
    generate_node(generator, tree, directory.name)

    path = Path(directory.name)
    expectations = {
        "main": [
            'app.add_typer(owners, name="owners")',
            'app.add_typer(pets, name="pet")',
            'app.add_typer(veterinarians, name="vets")',
        ],
        "owners": [
            '@app.command("create", help="Create a pet owner")',
            '@app.command("delete", help="Delete an owner")',
            '@app.command("pets", help="List owners pets")',
            '@app.command("update", help="Update an owner")',
        ],
        "pets": [
            '@app.command("create", help="Create a pet")',
            '@app.command("delete", help="Delete a pet")',
            '@app.command("update", help="Info for a specific pet")',
        ],
        "pets_examine":[
            '@app.command("blood-pressure", help="Record result of blood-pressure")',
            '@app.command("heart-rate", help="Record result of heart-rate")',
        ],
        "veterinarians": [
            '@app.command("add", help="Create a veterinarian")',
            '@app.command("delete", help="Delete a veterinarian")',
        ],
    }

    for module_name, expected in expectations.items():
        file = path / f"{module_name}.py"
        assert file.exists()

        text = file.read_text()
        assert "#!/usr/bin/env python3" in text
        assert f"Copyright {datetime.now().year}" in text
        assert "from typing_extensions import Annotated" in text
        assert 'app = typer.Typer(no_args_is_help=True, ' in text
        assert 'if __main__ == "__main__":'

        for v in expected:
            assert v in text


def test_generate_node_skip_bugged():
    pkg_name = "cli_pkg"
    oas = open_oas(asset_filename("pets_and_vets.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    directory = TemporaryDirectory()
    generator = Generator(pkg_name, oas)

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
            '@app.command("delete", help="Delete a pet")',
        ],
    }

    for module_name, unexpected in unexpectations.items():
        file = path / f"{module_name}.py"
        assert file.exists()

        text = file.read_text()
        assert "#!/usr/bin/env python3" in text
        assert f"Copyright {datetime.now().year}" in text
        assert "from typing_extensions import Annotated" in text
        assert 'app = typer.Typer(no_args_is_help=True, ' in text
        assert 'if __main__ == "__main__":'

        for v in unexpected:
            assert v not in text


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


def test_copy_and_update():
    source = asset_filename("arg_test.py")

    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name) / "my_destination.py"
    package = "this.is_a.different.package"

    copy_and_update(source, dst_path.as_posix(), package)

    text = dst_path.read_text()
    assert COPYRIGHT in text
    assert package in text
    assert "oas_tools.cli_gen" not in text


def test_copy_infrastructure():
    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name)
    package = "another.package"

    copy_infrastructure(dst_path.as_posix(), package)

    filenames = set(i.name for i in dst_path.iterdir())
    expected = {"_arguments.py", "_display.py", "_exceptions.py", "_logging.py", "_requests.py"}
    assert filenames == expected
