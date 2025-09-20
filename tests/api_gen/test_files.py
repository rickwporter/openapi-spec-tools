from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from openapi_spec_tools.api_gen.files import copy_api_infrastructure
from openapi_spec_tools.api_gen.files import generate_api_node
from openapi_spec_tools.layout.layout_generator import LayoutGenerator
from openapi_spec_tools.utils import open_oas
from tests.api_gen.helpers import TestApiGenerator
from tests.helpers import asset_filename


def test_generate_api_node_single():
    pkg_name = "api_pkg"
    oas = open_oas(asset_filename("pet2.yaml"))
    layout_gen = LayoutGenerator(oas)
    tree = layout_gen.generate("")
    directory = TemporaryDirectory()
    generator = TestApiGenerator(pkg_name, oas)
    generate_api_node(generator, tree, directory.name)

    path = Path(directory.name)
    file = path / "pets.py"
    assert file.exists()

    text = file.read_text()
    assert f"Copyright {datetime.now().year}" in text

    expected = [
        # function definitions - partial to allow for expansion
        'def create_pets',
        'def delete_pet_by_id',
        'def list_pets',
        'def show_pet_by_id',

        # NOTE: function doc-strings are same as help strings
        '# handler for createPets',
        '# handler for deletePetById',
        '# handler for listPets',
        '# handler for showPetById',
    ]
    for v in expected:
        assert v in text


def test_generate_api_node_multiple():
    pkg_name = "api_pkg"
    oas = open_oas(asset_filename("pets_and_vets.yaml"))
    layout_gen = LayoutGenerator(oas)
    tree = layout_gen.generate("")
    directory = TemporaryDirectory()
    generator = TestApiGenerator(pkg_name, oas)
    generate_api_node(generator, tree, directory.name)

    path = Path(directory.name)
    expectations = {
        "owners": [
            'def create_owner',
            'def delete_owner',
            'def update_owner',
        ],
        "owners_pets": [
            "def list_owner_pets",
        ],
        "pets": [
            'def create_pets',
            'def delete_pet_by_id',
            'def list_pets',
            'def show_pet_by_id',
        ],
    }

    for module_name, expected in expectations.items():
        file = path / f"{module_name}.py"
        assert file.exists()

        text = file.read_text()
        assert f"Copyright {datetime.now().year}" in text

        for v in expected:
            assert v in text


def test_copy_api_infrastructure():
    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name)
    package = "another.package"

    copy_api_infrastructure(dst_path.as_posix(), package)

    filenames = {i.name for i in dst_path.iterdir()}
    expected = {
        "_environment.py",
        "_logging.py",
        "_requests.py",
    }
    assert filenames == expected

    # make sure all the imports have been updated
    for fname in filenames:
        file = dst_path / fname
        text = file.read_text()
        assert "from openapi_spec_tools" not in text
