import io
from typing import Any
from unittest import mock

import pytest
import typer

from oas_tools.cli_gen.cli import layout_check_format
from tests.helpers import asset_filename

BAD_LAYOUT_FILE = asset_filename("bad_layout.yaml")

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
    cli: owners, pet, shows, vets
    pets: create, delete, examine, update
    shelters: list, list, rescue
"""


def args_disabled(updates: dict[str, Any]) -> dict[str, Any]:
    options = {
        "filename": BAD_LAYOUT_FILE,
        "references": False,
        "sub_order": False,
        "missing_props": False, 
        "op_dups": False, 
        "op_order": False,
    }
    
    values = options.copy()
    values.update(updates)
    return values


@pytest.mark.parametrize(
    ["layout_args", "message"],
    [
        pytest.param(
            {"filename":BAD_LAYOUT_FILE},
            "".join([ERR_SUB_MISSIING, ERR_SUB_UNUSED, ERR_SUB_ORDER, ERR_OPS_PROPS, ERR_OPS_DUPES, ERR_OPS_ORDER]),
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


def test_layour_check_format_success() -> None:
    with (
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
    ):
        filename = asset_filename("pets_layout.yaml")
        layout_check_format(filename=filename)
        output = mock_stdout.getvalue()
        assert f"No errors found in {filename}\n" == output
