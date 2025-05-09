import io
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from typing import Optional
from unittest import mock

import pytest
import typer

from oas_tools.cli_gen.cli import TreeFormat
from oas_tools.cli_gen.cli import generate_check_missing
from oas_tools.cli_gen.cli import generate_cli
from oas_tools.cli_gen.cli import generate_unreferenced
from oas_tools.cli_gen.cli import layout_check_format
from oas_tools.cli_gen.cli import layout_tree
from tests.helpers import asset_filename
from tests.helpers import to_ascii

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
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
    ):
        with pytest.raises(typer.Exit) as err:
            layout_check_format(**layout_args)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert message == output


def test_layout_check_format_success() -> None:
    with (
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        layout_tree(asset_filename("layout_pets2.yaml"), start=start, style=style)

        output = mock_stdout.getvalue()
        assert to_ascii(output) == to_ascii(expected)

def test_cli_generate_success():
    layout_file = asset_filename("layout_pets.yaml")
    oas_file = asset_filename("pet2.yaml")
    pkg_name = "my_cli_pkg"
    directory = TemporaryDirectory()

    with (
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
    ):
        generate_cli(layout_file, oas_file, pkg_name, directory.name)
        assert f"Generated files in {directory.name}\n" == mock_stdout.getvalue()

    # NOTE: just check some basics here -- more detailed checks elsewhere
    path = Path(directory.name)
    file = path / "main.py"
    assert file.exists()

    text = file.read_text()
    assert "#!/usr/bin/env python3" in text
    assert f"Copyright {datetime.now().year}" in text
    assert "from typing_extensions import Annotated" in text
    assert 'app = typer.Typer(no_args_is_help=True, help="Manage pets")' in text
    assert 'if __main__ == "__main__":'

    filenames = set(i.name for i in path.iterdir())
    expected = {
        "__init__.py",
        "_arguments.py",
        "_display.py",
        "_exceptions.py",
        "_logging.py",
        "_requests.py",
        "main.py",
    }
    assert filenames == expected


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
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
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
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
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
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
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
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
    ):
        lf_name = asset_filename(layout_file)
        generate_unreferenced(lf_name, asset_filename(oas_file), full_path=full)
        result = mock_stdout.getvalue()
        assert expected == result
