from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from typing import Optional
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli_gen.cli import TreeDisplay
from openapi_spec_tools.cli_gen.cli import TreeFormat
from openapi_spec_tools.cli_gen.cli import generate_check_missing
from openapi_spec_tools.cli_gen.cli import generate_cli
from openapi_spec_tools.cli_gen.cli import generate_unreferenced
from openapi_spec_tools.cli_gen.cli import layout_check_format
from openapi_spec_tools.cli_gen.cli import layout_operations
from openapi_spec_tools.cli_gen.cli import layout_tree
from openapi_spec_tools.cli_gen.cli import layout_tree_with_error_handling
from openapi_spec_tools.cli_gen.cli import open_layout_with_error_handling
from openapi_spec_tools.cli_gen.cli import open_oas_with_error_handling
from openapi_spec_tools.cli_gen.cli import show_cli_tree
from openapi_spec_tools.cli_gen.cli import trim_oas
from tests.cli_gen.cli_output import P_V_ALL
from tests.cli_gen.cli_output import P_V_MID
from tests.cli_gen.cli_output import P_V_PETS
from tests.cli_gen.cli_output import P_V_SHALLOW
from tests.cli_gen.cli_output import PET_ALL
from tests.cli_gen.cli_output import PET_FUNC
from tests.cli_gen.cli_output import PET_HELP
from tests.cli_gen.cli_output import PET_OP
from tests.cli_gen.cli_output import PET_PATH
from tests.cli_gen.helpers import to_ascii
from tests.helpers import StringIo
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.json", "ERROR: unable to parse", id="bad-json"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad-yaml"),
    ]
)
def test_open_oas(filename, message) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        open_oas_with_error_handling(asset_filename(filename))

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad"),
    ]
)
def test_open_layout_with_error(filename, message) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        open_layout_with_error_handling(asset_filename(filename))

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


@pytest.mark.parametrize(
    ["filename", "message"],
    [
        pytest.param("gone", "ERROR: failed to find", id="missing"),
        pytest.param("bad.yaml", "ERROR: unable to parse", id="bad"),
        pytest.param("pet2.yaml", "ERROR: No start value found for 'start'", id="bad"),
    ]
)
def test_layout_tree_with_error(filename, message) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        layout_tree_with_error_handling(asset_filename(filename), "start")

    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output.startswith(message)


BAD_LAYOUT_FILE = asset_filename("layout_bad.yaml")

ERR_SUB_MISSIING ="""\
Missing sub-commands for:
    dog_shows
"""
ERR_SUB_UNUSED = """\
Unused sub-commands for:
    shelters
"""
ERR_SUB_ORDER = """\
Sub-commands are misordered:
    owners < pets_examine
"""
ERR_OPS_PROPS = """\
Sub-commands have missing properties:
    owners: description, operations
    veterinarians: add operationId or subcommandId, delete operationId or subcommandId
"""
ERR_OPS_DUPES = """\
Duplicate operations in sub-commands:
    shelters: list at 0, 2
"""
ERR_OPS_ORDER = """\
Sub-command operation orders should be:
    main: owners, pet, shows, vets
    pets: create, delete, examine, update
    shelters: list, list, rescue
"""
ERR_PAGINATION = """\
Pagination parameter errors:
    shelters.list: cannot have next URL in both header and body property
"""


def args_disabled(updates: dict[str, Any]) -> dict[str, Any]:
    options = {
        "filename": BAD_LAYOUT_FILE,
        "references": False,
        "sub_order": False,
        "missing_props": False,
        "op_dups": False,
        "op_order": False,
        "pagination": False,
    }

    values = options.copy()
    values.update(updates)
    return values


@pytest.mark.parametrize(
    ["layout_args", "message"],
    [
        pytest.param(
            {"filename":BAD_LAYOUT_FILE},
            "".join([
                ERR_SUB_MISSIING,
                ERR_SUB_UNUSED,
                ERR_SUB_ORDER,
                ERR_OPS_PROPS,
                ERR_OPS_DUPES,
                ERR_OPS_ORDER,
                ERR_PAGINATION,
            ]),
            id="all"
        ),
        pytest.param(
            args_disabled({"references": True}),
            "".join([ERR_SUB_MISSIING, ERR_SUB_UNUSED]),
            id="references",
        ),
        pytest.param(
            args_disabled({"sub_order": True}),
            ERR_SUB_ORDER,
            id="sub-order",
        ),
        pytest.param(
            args_disabled({"missing_props": True}),
            ERR_OPS_PROPS,
            id="ops-props",
        ),
        pytest.param(
            args_disabled({"op_dups": True}),
            ERR_OPS_DUPES,
            id="ops-dupes",
        ),
        pytest.param(
            args_disabled({"op_order": True}),
            ERR_OPS_ORDER,
            id="ops-order",
        ),
        pytest.param(
            args_disabled({"pagination": True}),
            ERR_PAGINATION,
            id="pagination",
        ),
    ]
)
def test_layout_check_format_failure(layout_args: dict[str, Any], message: str) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        with pytest.raises(typer.Exit) as err:
            layout_check_format(**layout_args)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert message == output


def test_layout_check_format_success() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        filename = asset_filename("layout_pets.yaml")
        layout_check_format(filename=filename)
        output = mock_stdout.getvalue()
        assert f"No errors found in {filename}\n" == output

FULL_TEXT = """\
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Command              ┃ Identifier            ┃ Help                       ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ main                 │ main                  │ Pet management application │
│   owners             │ owners                │ Keepers of the pets        │
│     create           │ createOwner           │                            │
│     delete           │ deleteOwner           │                            │
│     pets             │ listOwnerPets         │                            │
│     update           │ updateOwner           │                            │
│   pet                │ pets                  │ Manage your pets           │
│     create           │ createPets            │                            │
│     delete           │ deletePetById         │                            │
│     examine          │ pets_examine          │ Examine your pet           │
│       blood-pressure │ checkPetBloodPressure │                            │
│       heart-rate     │ checkPetHeartRate     │                            │
│     update           │ showPetById           │                            │
│   vets               │ veterinarians         │ Manage veterinarians       │
│     add              │ createVet             │                            │
│     delete           │ deleteVet             │                            │
└──────────────────────┴───────────────────────┴────────────────────────────┘
"""

PET_TEXT = """\
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Command            ┃ Identifier            ┃ Help             ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ pets               │ pets                  │ Manage your pets │
│   create           │ createPets            │                  │
│   delete           │ deletePetById         │                  │
│   examine          │ pets_examine          │ Examine your pet │
│     blood-pressure │ checkPetBloodPressure │                  │
│     heart-rate     │ checkPetHeartRate     │                  │
│   update           │ showPetById           │                  │
└────────────────────┴───────────────────────┴──────────────────┘
"""

EXAMINE_TEXT = """\
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ Command          ┃ Identifier            ┃ Help             ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ pets_examine     │ pets_examine          │ Examine your pet │
│   blood-pressure │ checkPetBloodPressure │                  │
│   heart-rate     │ checkPetHeartRate     │                  │
└──────────────────┴───────────────────────┴──────────────────┘
"""
EXAMINE_JSON = """\
{
  "command": "pets_examine",
  "identifier": "pets_examine",
  "description": "Examine your pet",
  "children": [
    {
      "command": "blood-pressure",
      "identifier": "checkPetBloodPressure",
      "description": ""
    },
    {
      "command": "heart-rate",
      "identifier": "checkPetHeartRate",
      "description": ""
    }
  ]
}
"""
EXAMINE_YAML = """\
command: pets_examine
identifier: pets_examine
description: Examine your pet
children:
- command: blood-pressure
  identifier: checkPetBloodPressure
  description: ''
- command: heart-rate
  identifier: checkPetHeartRate
  description: ''
"""

@pytest.mark.parametrize(
    ["start", "style", "expected"],
    [
        pytest.param("main", TreeFormat.TEXT, FULL_TEXT, id="main"),
        pytest.param("pets", TreeFormat.TEXT, PET_TEXT, id="pets"),
        pytest.param("pets_examine", TreeFormat.TEXT, EXAMINE_TEXT, id="examine-text"),
        pytest.param("pets_examine", TreeFormat.JSON, EXAMINE_JSON, id="examine-json"),
        pytest.param("pets_examine", TreeFormat.YAML, EXAMINE_YAML, id="examine-yaml"),
    ]
)
def test_layout_tree(start: Optional[str], style: TreeFormat, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        layout_tree(asset_filename("layout_pets2.yaml"), start=start, style=style)

        output = mock_stdout.getvalue()
        assert to_ascii(output) == to_ascii(expected)


LAYOUT_OPS_PET = """\
createPets
deletePetById
listPets
showPetById
"""
LAYOUT_OPS_CT_FULL = """\
audit_list
audit_retrieve
audit_summary_retrieve
backup_snapshot_create
environments_create
environments_destroy
environments_list
environments_partial_update
environments_pushes_list
environments_retrieve
environments_tags_create
environments_tags_destroy
environments_tags_list
environments_tags_partial_update
environments_tags_retrieve
environments_tags_update
environments_update
grants_create
grants_destroy
grants_list
grants_multi_destroy
grants_partial_update
grants_retrieve
grants_update
memberships_create
memberships_destroy
memberships_list
memberships_partial_update
memberships_retrieve
memberships_update
users_current_retrieve
users_destroy
users_list
users_retrieve
utils_generate_password_create
"""
LAYOUT_OPS_CT_ENV = """\
environments_create
environments_destroy
environments_list
environments_partial_update
environments_pushes_list
environments_retrieve
environments_tags_create
environments_tags_destroy
environments_tags_list
environments_tags_partial_update
environments_tags_retrieve
environments_tags_update
environments_update
"""

@pytest.mark.parametrize(
    ["filename", "start", "expected"],
    [
        pytest.param("layout_pets.yaml", "main", LAYOUT_OPS_PET, id="simple"),
        pytest.param("layout_cloudtruth.yaml", "main", LAYOUT_OPS_CT_FULL, id="subcommands"),
        pytest.param("layout_cloudtruth.yaml", "environments", LAYOUT_OPS_CT_ENV, id="start"),
    ]
)
def test_layout_operations(filename, start, expected) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        layout_operations(asset_filename(filename), start=start)

        output = mock_stdout.getvalue()
        assert to_ascii(output) == to_ascii(expected)


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
            layout_file,
            oas_file,
            pkg_name,
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

    def _read_text(filename: str) -> str:
        with open(filename, "r", encoding="utf-8", newline="\n") as fp:
            return fp.read()

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        generate_cli(
            layout_file,
            oas_file,
            pkg_name,
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
        text = _read_text(file.as_posix())
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
        text = _read_text(file.as_posix())
        assert copyright_text in text


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
                layout_file, oas_file, pkg_name, code_dir=code_dir, test_dir=test_dir, include_tests=include_tests
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
            generate_cli(layout_file, oas_file, pkg_name, directory.name)
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
    ["layout_file", "oas_file", "start", "display", "depth", "expected"],
    [
        pytest.param(
            "layout_operationless.yaml",
            "pet2.yaml",
            "hospital",
            TreeDisplay.ALL,
            10,
            "No operations or sub-commands found\n",
            id="empty",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.ALL, 10, PET_ALL, id="all",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.HELP, 10, PET_HELP, id="help",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.FUNCTION, 10, PET_FUNC, id="func",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.OPERATION, 10, PET_OP, id="operation",
        ),
        pytest.param(
            "layout_pets.yaml", "pet2.yaml", "main", TreeDisplay.PATH, 10, PET_PATH, id="path",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.ALL, 10, P_V_ALL, id="complete",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "pets", TreeDisplay.OPERATION, 10, P_V_PETS, id="alt-start",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.OPERATION, 0, P_V_SHALLOW, id="depth=0",
        ),
        pytest.param(
            "layout_pets2.yaml", "pets_and_vets.yaml", "main", TreeDisplay.OPERATION, 1, P_V_MID, id="depth=1",
        ),
    ]
)
def test_show_cli_tree(layout_file, oas_file, start, display, depth, expected):
    lname = asset_filename(layout_file)
    oname = asset_filename(oas_file)
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        show_cli_tree(lname, oname, start=start, display=display, max_depth=depth)

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
