from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.paths import paths_list
from openapi_spec_tools.cli.paths import paths_operations
from openapi_spec_tools.cli.paths import paths_show
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET_YAML = asset_filename("pet.yaml")
PET2_YAML = asset_filename("pet2.yaml")

@pytest.mark.parametrize(
    ["filename", "search", "subpaths", "expected"],
    [
        pytest.param(PET_YAML, None, False, "Found 2 paths:\n    /pets\n    /pets/{petId}\n", id="no-search"),
        pytest.param(PET_YAML, "/pets", False, "Found 1 paths matching '/pets':\n    /pets\n", id="search-simple"),
        pytest.param(PET_YAML, "/PETs", False, "Found 1 paths matching '/PETs':\n    /pets\n", id="search-case"),
        pytest.param(
            PET_YAML,
            "/pets",
            True,
            "Found 2 paths matching '/pets' including sub-paths:\n    /pets\n    /pets/{petId}\n",
            id="simple-subpath",
        ),
        pytest.param(PET_YAML, "/pets/name", False, "No paths found matching '/pets/name'\n", id="search-none"),
    ]
)
def test_paths_list(filename: str, search: str | None, subpaths: bool, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        paths_list(filename, search, subpaths)

        output = mock_stdout.getvalue()
        assert output == expected


PET_SHOW_PATH = """\
/pets/{petId}:
    get:
        operationId: showPetById
        parameters:
        -   description: The id of the pet to retrieve
            in: path
            name: petId
            required: true
            schema:
                type: string
        responses:
            '200':
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Pet'
                description: Expected response to a valid request
            default:
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Error'
                description: unexpected error
        summary: Info for a specific pet
        tags:
        - pets

"""

PET2_SHOW_PATH = """\
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
        tags:
        - admin
    get:
        operationId: showPetById
        responses:
            '200':
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Pet'
                description: Expected response to a valid request
            default:
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Error'
                description: unexpected error
        summary: Info for a specific pet
        tags:
        - pets
    parameters:
    -   description: The id of the pet to retrieve
        in: path
        name: petId
        required: true
        schema:
            type: string

"""

PET2_SHOW_PATH_REF = """\
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
        Pet:
            properties:
                id:
                    format: int64
                    type: integer
                name:
                    type: string
                owner:
                    nullable: true
                    type: string
                tag:
                    type: string
            required:
            - id
            - name
            - owner
            type: object
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
            tags:
            - admin
        get:
            operationId: showPetById
            responses:
                '200':
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/Pet'
                    description: Expected response to a valid request
                default:
                    content:
                        application/json:
                            schema:
                                $ref: '#/components/schemas/Error'
                    description: unexpected error
            summary: Info for a specific pet
            tags:
            - pets
        parameters:
        -   description: The id of the pet to retrieve
            in: path
            name: petId
            required: true
            schema:
                type: string

"""

@pytest.mark.parametrize(
    ["filename", "path", "references", "expected"],
    [
        pytest.param(PET_YAML, "/pets/{petId}", False, PET_SHOW_PATH, id="found"),
        pytest.param(PET2_YAML, "/pets/{petId}", False, PET2_SHOW_PATH, id="params"),
        pytest.param(PET2_YAML, "/pets/{petId}", True, PET2_SHOW_PATH_REF, id="references"),
    ]
)
def test_paths_show_success(filename: str, path: str, references: bool, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        paths_show(filename, path, include_models=references)

        output = mock_stdout.getvalue()
        assert output == expected


def test_paths_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "/pet/name"
        with pytest.raises(typer.Exit) as err:
            paths_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


@pytest.mark.parametrize(
    ["filename", "search", "subpaths", "expected"],
    [
        pytest.param(
            PET_YAML,
            None,
            False,
            "/pets:\n- listPets\n- createPets\n/pets/{petId}:\n- showPetById\n\n",
            id="no-search",
        ),
        pytest.param(PET_YAML, "/pets", False, "/pets:\n- listPets\n- createPets\n\n", id="search-simple"),
        pytest.param(PET_YAML, "/PETs", False, "/pets:\n- listPets\n- createPets\n\n", id="search-case"),
        pytest.param(
            PET_YAML,
            "/pets",
            True,
            "/pets:\n- listPets\n- createPets\n/pets/{petId}:\n- showPetById\n\n",
            id="simple-subpath",
        ),
        pytest.param(
            PET2_YAML,
            "/pets/{petId}",
            True,
            "/pets/{petId}:\n- showPetById\n- deletePetById\n\n",
            id="params",
        ),
    ]
)
def test_paths_operations_successs(filename: str, search: str | None, subpaths: bool, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        paths_operations(filename, search, subpaths)

        output = mock_stdout.getvalue()
        assert output == expected


def test_paths_operations_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "/no/such/path"
        with pytest.raises(typer.Exit) as err:
            paths_operations(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"
