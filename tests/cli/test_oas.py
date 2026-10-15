import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.oas import DisplayOption
from openapi_spec_tools.cli.oas import diff
from openapi_spec_tools.cli.oas import info
from openapi_spec_tools.cli.oas import summary
from openapi_spec_tools.cli.oas import update
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET2_YAML = asset_filename("pet2.yaml")


#################################################
# Top-level stuff
def test_info() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        info(PET2_YAML)

        output = mock_stdout.getvalue()
        expected = """\
info:
    license:
        name: MIT
    title: Swagger Petstore
    version: 1.0.0

"""
        assert output == expected


def test_summary() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        summary(PET2_YAML)

        output = mock_stdout.getvalue()
        expected = """\
OpenAPI spec (pet2.yaml):
    Models: 3
    Paths: 2
    Operation methods (4):
        get: 2
        put: 0
        patch: 0
        delete: 1
        post: 1
    Tags (2) with operation counts:
        pets: 3
        admin: 1
"""
        assert output == expected

def test_diff_found() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        diff(asset_filename("pet.yaml"), PET2_YAML)

        output = mock_stdout.getvalue()
        expected = """\
components:
    schemas:
        Pet:
            properties:
                owner: added
            required: added owner
paths:
    /pets/{petId}:
        delete: added
        get:
            parameters: removed
        parameters: added
tags: added

"""
        assert output == expected

def test_diff_not_found() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        diff(PET2_YAML, PET2_YAML)

        output = mock_stdout.getvalue().replace("\n", "")
        expected = "No differences between pet2.yaml and pet2.yaml"
        assert output == expected

PET2_DIFF_TAG_YAML = """\
paths:
    /pets:
        get:
            tags: removed
        post:
            tags: removed
    /pets/{petId}:
        delete:
            tags: removed
        get:
            tags: removed
tags: removed

"""

PET2_UPDATE_DELETE = """\
components:
    schemas:
        Error:
            properties:
                code:
                    format: int32
                    type: integer
                message:
                    type: string
            required:
            - code
            - message
            type: object
info:
    license:
        name: MIT
    title: Swagger Petstore
    version: 1.0.0
openapi: 3.0.0
paths:
    /pets/{petId}:
        delete:
            operationId: deletePetById
            responses:
                '204':
                    description: Expected empty response for successful delete
                default:
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/Error'
                    description: unexpected error
            summary: Delete a pet
        parameters:
        -   description: The id of the pet to retrieve
            in: path
            name: petId
            required: true
            schema:
                type: string
servers:
-   url: http://petstore.swagger.io/v1

"""
PET2_HEADERS_REMOVED = """\
paths:
    /pets:
        get:
            responses:
                '200':
                    headers: removed

"""

@pytest.mark.parametrize(
    ["filename", "kwargs", "expected"],
    [
        pytest.param(PET2_YAML, {}, "No differences between pet2.yaml and updated\n", id="no-updates"),
        pytest.param(PET2_YAML, {"remove_all_tags": True}, PET2_DIFF_TAG_YAML, id="remove-tags"),
        pytest.param(
            PET2_YAML,
            {"remove_all_tags": True, "display_option": DisplayOption.DIFF},
            PET2_DIFF_TAG_YAML,
            id="remove-tags-diff",
        ),
        pytest.param(
            PET2_YAML,
            {"remove_all_tags": True, "display_option": DisplayOption.NONE},
            "",
            id="remove-tags-none",
        ),
        pytest.param(
            PET2_YAML,
            {"remove_all_tags": True, "display_option": DisplayOption.SUMMARY},
            "Found 5 differences from pet2.yaml\n",
            id="remove-tags-summary",
        ),
        pytest.param(
            PET2_YAML,
            {"nullable_not_required": True, "indent": 2},
            "components:\n  schemas:\n    Pet:\n      required: removed owner\n\n",
            id="nullable-not-required",
        ),
        pytest.param(
            PET2_YAML,
            {"remove_operations": ["listPets", "createPets"], "display_option": DisplayOption.SUMMARY},
            "Found 2 differences from pet2.yaml\n",
            id="remove-ops",
        ),
        pytest.param(
            PET2_YAML,
            {"allowed_operations": ["deletePetById"], "remove_all_tags": True, "display_option": DisplayOption.FINAL},
            PET2_UPDATE_DELETE,
            id="allow-ops",
        ),
        pytest.param(
            PET2_YAML,
            {"remove_properties": ["headers"]},
            PET2_HEADERS_REMOVED,
            id="remove-property",
        )
    ]
)
def test_update_success(filename: str, kwargs: dict[str, Any], expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        update(filename, **kwargs)
        output = mock_stdout.getvalue()
        assert output == expected

def test_update_success_save() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        tempfile.TemporaryDirectory() as temp_dir,
    ):
        temp_file = Path(temp_dir) / "foo.yaml"
        assert not temp_file.exists()
        update(
            PET2_YAML,
            allowed_operations=["deletePetById", "listPets"],
            display_option=DisplayOption.FINAL,
            updated_filename=temp_file,
        )
        output = mock_stdout.getvalue()
        assert temp_file.exists()
        expected = temp_file.read_text() + "\n"
        assert output == expected


def test_update_failure() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        update(PET2_YAML, allowed_operations=["listPets"], remove_operations=["deletePetById"])
    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output == "ERROR: cannot specify both --allow-op and --remove-op\n"
