from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.cli_gen import TreeDisplay
from openapi_spec_tools.cli.cli_gen import generate_check_missing
from openapi_spec_tools.cli.cli_gen import generate_cli
from openapi_spec_tools.cli.cli_gen import generate_unreferenced
from openapi_spec_tools.cli.cli_gen import show_cli_tree
from openapi_spec_tools.cli.cli_gen import trim_oas
from openapi_spec_tools.cli.cli_gen import update_layout
from tests.cli.cli_gen_output import P_V_ALL
from tests.cli.cli_gen_output import P_V_MID
from tests.cli.cli_gen_output import P_V_PETS
from tests.cli.cli_gen_output import P_V_SHALLOW
from tests.cli.cli_gen_output import PET_ADD
from tests.cli.cli_gen_output import PET_ALL
from tests.cli.cli_gen_output import PET_FUNC
from tests.cli.cli_gen_output import PET_HELP
from tests.cli.cli_gen_output import PET_OP
from tests.cli.cli_gen_output import PET_PATH
from tests.cli.helpers import read_text
from tests.helpers import StringIo
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["code_dir", "test_dir", "include_tests", "expected_code", "expected_test"],
    [
        pytest.param(None, None, True, "my_cli_pkg", "tests", id="basic"),
        pytest.param(None, None, False, "my_cli_pkg", "tests", id="no-tests"),
        pytest.param("sna", "foo", True, "sna", "foo", id="overrides"),
        pytest.param("sna", "foo", False, "sna", "foo", id="untested-overrides"),
    ],
)
def test_cli_generate_success(code_dir, test_dir, include_tests, expected_code, expected_test):
    layout_file = asset_filename("layout_pets.yaml")
    oas_file = asset_filename("pet2.yaml")
    pkg_name = "my_cli_pkg"
    directory = TemporaryDirectory()
    base_dir = Path(directory.name)
    code_path = Path(base_dir, code_dir).as_posix() if code_dir else None
    test_path = Path(base_dir, test_dir).as_posix() if test_dir else None

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        generate_cli(
            oas_file,
            pkg_name,
            layout_file=layout_file,
            project_dir=directory.name,
            code_dir=code_path,
            test_dir=test_path,
            include_tests=include_tests
        )
        assert "Generated files\n" == mock_stdout.getvalue()

    # NOTE: just check some basics here -- more detailed checks elsewhere
    path = Path(directory.name) / expected_code
    file = path / "main.py"
    assert file.exists()

    text = file.read_text()
    assert "#!/usr/bin/env python3" in text
    assert f"Copyright {datetime.now().year}" in text
    assert "from typing import Annotated" in text
    assert 'app = typer.Typer(no_args_is_help=True, help="Manage pets")' in text
    assert 'if __name__ == "__main__":' in text

    filenames = {i.name for i in path.iterdir()}
    expected = {
        "__init__.py",
        "_arguments.py",
        "_console.py",
        "_display.py",
        "_exceptions.py",
        "_logging.py",
        "_requests.py",
        "_tree.py",
        "main.py",
        "tree.yaml",
    }
    assert filenames == expected

    path = Path(directory.name) / expected_test
    if not include_tests:
        assert not path.exists()
    else:
        filenames = {i.name for i in path.iterdir()}
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


def test_cli_generate_success_copyright(copyright_fixture):
    layout_file = asset_filename("layout_pets.yaml")
    oas_file = asset_filename("pet2.yaml")

    pkg_name = "my_cli_pkg"
    directory = TemporaryDirectory()
    base_dir = Path(directory.name)

    copyright_text = "# Simple copyright message"
    copyright_file = base_dir / "copyright.txt"
    copyright_file.write_bytes(copyright_text.encode(encoding="utf-8"))

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        generate_cli(
            oas_file,
            pkg_name,
            layout_file=layout_file,
            project_dir=directory.name,
            include_tests=True,
            copyright_file=copyright_file.as_posix()
        )
        assert "Generated files\n" == mock_stdout.getvalue()

    filenames = {
        "_arguments.py",
        "_console.py",
        "_display.py",
        "_exceptions.py",
        "_logging.py",
        "_requests.py",
        "_tree.py",
        "main.py",
        "tree.yaml",
    }
    path = base_dir / pkg_name
    for fname in filenames:
        file = path / fname
        text = read_text(file.as_posix())
        assert copyright_text in text

    filenames = {
        "helpers.py",
        "test_console.py",
        "test_display.py",
        "test_exceptions.py",
        "test_logging.py",
        "test_main.py",
        "test_requests.py",
        "test_tree.py",
    }
    path = base_dir / "tests"
    for fname in filenames:
        file = path / fname
        text = read_text(file.as_posix())
        assert copyright_text in text


def test_cli_generate_success_no_layout():
    oas_file = asset_filename("pet2.yaml")

    pkg_name = "my_cli_pkg"
    directory = TemporaryDirectory()
    base_dir = Path(directory.name)

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        generate_cli(
            oas_file,
            pkg_name,
            project_dir=directory.name,
            prefix="/pets"
        )
        text = mock_stdout.getvalue()
        assert "Generated layout -- equivalent can be saved using 'layout suggest'" in text
        assert "Generated files" in text

    filenames = {
        "__init__.py",
        "_arguments.py",
        "_console.py",
        "_display.py",
        "_exceptions.py",
        "_logging.py",
        "_requests.py",
        "_tree.py",
        "main.py",
        "tree.yaml",
    }
    path = base_dir / pkg_name
    found = {item.name for item in path.iterdir()}
    assert filenames == found


@pytest.mark.parametrize(
    ["code_dir", "test_dir", "include_tests", "error"],
    [
        pytest.param(
            None,
            "foo",
            False,
            (
                "Must provide code directory using either `--project-dir` (which "
                "uses package name), or `--code-dir`\n"
            ),
            id="no-code",
        ),
        pytest.param(
            "sna",
            None,
            True,
            (
                "Must provide test directory using either `--project-dir` (which uses "
                "tests sub-directory), or `--tests-dir`\n"
            ),
            id="no-test",
        ),
    ]
)
def test_cli_generate_location_errors(code_dir, test_dir, include_tests, error):
    layout_file = asset_filename("layout_pets.yaml")
    oas_file = asset_filename("pet2.yaml")
    pkg_name = "my_cli_pkg"

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        with pytest.raises(typer.Exit) as context:
            generate_cli(
                oas_file,
                pkg_name,
                layout_file=layout_file,
                code_dir=code_dir,
                test_dir=test_dir,
                include_tests=include_tests,
            )
        ex = context.value
        assert ex.exit_code == 1
        assert error == mock_stdout.getvalue()


def test_cli_generate_failure():
    layout_file = asset_filename("layout_pets2.yaml")
    oas_file = asset_filename("pet.yaml")
    pkg_name = "my_cli_pkg"
    directory = TemporaryDirectory()
    message = """\
Commands with missing operations:
    owners: createOwner, deleteOwner, listOwnerPets, updateOwner
    pets: deletePetById
    veterinarians: createVet, deleteVet
"""

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        with pytest.raises(typer.Exit) as context:
            generate_cli(oas_file, pkg_name, layout_file, directory.name)
        ex = context.value
        assert ex.exit_code == 1
        assert message == mock_stdout.getvalue()


def test_cli_check_failure():
    layout_file = asset_filename("layout_pets2.yaml")
    oas_file = asset_filename("pet.yaml")
    message = """\
Commands with missing operations:
    owners: createOwner, deleteOwner, listOwnerPets, updateOwner
    pets: deletePetById
    veterinarians: createVet, deleteVet
"""

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        with pytest.raises(typer.Exit) as context:
            generate_check_missing(layout_file, oas_file)
        ex = context.value
        assert ex.exit_code == 1
        assert message == mock_stdout.getvalue()


def test_cli_check_success():
    layout_file = asset_filename("layout_pets.yaml")
    oas_file = asset_filename("pet2.yaml")

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        generate_check_missing(layout_file, oas_file)
        assert f"All operations in {layout_file} found in {oas_file}\n" == mock_stdout.getvalue()


UNREF_PETS_VETS_NORMAL = """\
owners
  - createOwner
  - deleteOwner
  - updateOwner
owners/pets
  - listOwnerPets
examine/bloodPressure
  - checkPetBloodPressure
examine/heartRate
  - checkPetHeartRate
version
  - appVersion
vets
  - createVet
  - deleteVet

Found 9 operations in 6 paths
"""

UNREF_PETS_VETS_FULL = """\
/owners
  - createOwner
/owners/{ownerId}
  - deleteOwner
  - updateOwner
/owners/{ownerId}/pets
  - listOwnerPets
/examine/bloodPressure
  - checkPetBloodPressure
/examine/heartRate
  - checkPetHeartRate
/version/
  - appVersion
/vets
  - createVet
/vets/{vetId}
  - deleteVet

Found 9 operations in 8 paths
"""


@pytest.mark.parametrize(
    ["layout_file", "oas_file", "full", "expected"],
    [
        pytest.param("layout_pets.yaml", "pet.yaml", True, "No unreferenced operations found\n", id="empty"),
        pytest.param("layout_pets.yaml", "pets_and_vets.yaml", False, UNREF_PETS_VETS_NORMAL, id="normal"),
        pytest.param("layout_pets.yaml", "pets_and_vets.yaml", True, UNREF_PETS_VETS_FULL, id="full"),
    ]
)
def test_unreferenced(layout_file, oas_file, full, expected):
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        lf_name = asset_filename(layout_file)
        generate_unreferenced(lf_name, asset_filename(oas_file), full_path=full)
        result = mock_stdout.getvalue()
        assert expected == result


@pytest.mark.parametrize(
    ["layout_file", "oas_file", "start", "display", "depth", "search", "expected"],
    [
        pytest.param(
            "layout_operationless.yaml",
            "pet2.yaml",
            "hospital",
            TreeDisplay.ALL,
            10,
            None,
            "No operations or sub-commands found\n",
            id="empty",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.ALL, 10, None, PET_ALL, id="all",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.HELP, 10, None, PET_HELP, id="help",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.FUNCTION, 10, None, PET_FUNC, id="func",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.OPERATION, 10, None, PET_OP, id="operation",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.PATH, 10, None, PET_PATH, id="path",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.ALL, 10, None, P_V_ALL, id="complete",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "pets", TreeDisplay.OPERATION, 10, "", P_V_PETS, id="alt-start",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.OPERATION, 0, "", P_V_SHALLOW, id="depth=0",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.OPERATION, 1, None, P_V_MID, id="depth=1",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.FUNCTION, 10, "add", PET_ADD, id="search",
        )
    ]
)
def test_show_cli_tree(layout_file, oas_file, start, display, depth, search, expected):
    lname = asset_filename(layout_file)
    oname = asset_filename(oas_file)
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        show_cli_tree(lname, oname, start=start, display=display, max_depth=depth, search=search)

        result = mock_stdout.getvalue()
        assert expected == result


def test_trim_oas():
    directory = TemporaryDirectory()
    updated = Path(directory.name) / "trimmed.yaml"
    trim_oas(
        asset_filename("layout_cloudtruth.yaml"),
        asset_filename("ct.yaml"),
        updated_file=updated,
        remove_properties=["example"],
    )
    expected = Path(asset_filename("ct_trimmed.yaml")).read_text()
    actual = updated.read_text()
    assert expected == actual


def test_update_layout_none():
    directory = TemporaryDirectory()
    updated_file = Path(directory.name) / "layout.yaml"
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        update_layout(
            asset_filename("layout_pets.yaml"),
            asset_filename("pet.yaml"),
            updated_file.as_posix(),
            prefix="/pets",
            indent=1,
        )
        assert "No unreferenced operations found" in mock_stdout.getvalue()
        assert not updated_file.exists()


def test_update_layout_updates():
    directory = TemporaryDirectory()
    updated_file = Path(directory.name) / "layout.yaml"
    orig_filename = asset_filename("layout_pets3.yaml")
    original_text = read_text(orig_filename)
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        update_layout(
            orig_filename,
            asset_filename("pet3.yaml"),
            updated_file.as_posix(),
            prefix="/pets",
            indent=1,
        )

    assert "Added 3 operations" in mock_stdout.getvalue()
    assert updated_file.exists()
    updated_text = updated_file.read_text()

    # check that the getSchema operation was added
    assert "operationId: getSchema" not in original_text
    assert "operationId: getSchema" in updated_text

    # check that another already exists
    assert "operationId: showPetById" in original_text
    assert "operationId: showPetById" in updated_text
