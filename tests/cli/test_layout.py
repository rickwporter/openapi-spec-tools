from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from typing import Optional
from unittest import mock

import pytest
import typer
import yaml

from openapi_spec_tools.cli.layout import TreeFormat
from openapi_spec_tools.cli.layout import layout_check_format
from openapi_spec_tools.cli.layout import layout_operations
from openapi_spec_tools.cli.layout import layout_suggest
from openapi_spec_tools.cli.layout import layout_tree
from tests.cli_gen.helpers import to_ascii
from tests.helpers import StringIo
from tests.helpers import asset_filename

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
    veterinarians: add operationId, subcommandId, or reference, delete operationId, subcommandId, or reference
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
      "identifier": "checkPetBloodPressure"
    },
    {
      "command": "heart-rate",
      "identifier": "checkPetHeartRate"
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
- command: heart-rate
  identifier: checkPetHeartRate
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


def test_layout_suggest():
    directory = TemporaryDirectory()
    layout_file = Path(directory.name) / "layout.yaml"
    layout_suggest(asset_filename("pet.yaml"), layout_file.as_posix(), prefix="/pets", indent=3)

    text = layout_file.read_text(encoding="utf-8", errors="ignore")
    assert 'main:' in text
    assert '\n   description: CLI to manage your application' in text
    assert 'name: create' in text
    assert '\n      operationId: createPets' in text
    assert 'name: list' in text
    assert 'operationId: listPets' in text
    assert 'name: show' in text
    assert 'operationId: showPetById' in text

    # modify the layout file
    data = yaml.safe_load(text)
    data['main']['description'] = "Updated CLI description"
    data['main']['operations'][0]['summaryFields'] = "short, brief"
    data['main']['operations'][1]['bugIds'] = "black-fly, gnat"
    layout_file.write_text(yaml.dump(data))

    layout_suggest(asset_filename("pet.yaml"), layout_file.as_posix(), prefix="/pets", indent=3, update=True)

    text = layout_file.read_text(encoding="utf-8", errors="ignore")
    assert 'description: Updated CLI description' in text
    assert 'summaryFields:' in text
    assert '- short' in text
    assert '- brief' in text
    assert 'bugIds:' in text
    assert '- black-fly' in text
    assert '- gnat' in text

    # do it again without the update flag and see we lose the previous updates
    layout_suggest(asset_filename("pet.yaml"), layout_file.as_posix(), prefix="/pets", indent=3, update=False)

    text = layout_file.read_text(encoding="utf-8", errors="ignore")
    assert 'description: Updated CLI description' not in text
    assert 'summaryFields:' not in text
    assert '- short' not in text
    assert '- brief' not in text
    assert 'bugIds:' not in text
    assert '- black-fly' not in text
    assert '- gnat' not in text
