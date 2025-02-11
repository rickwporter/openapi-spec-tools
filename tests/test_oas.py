import io
import tempfile
from pathlib import Path
from typing import Any
from typing import Optional
from unittest import mock

import pytest
import typer

from oas_tools.oas import DisplayOption
from oas_tools.oas import diff
from oas_tools.oas import info
from oas_tools.oas import models_list
from oas_tools.oas import models_show
from oas_tools.oas import models_used_by
from oas_tools.oas import models_uses
from oas_tools.oas import operation_list
from oas_tools.oas import operation_show
from oas_tools.oas import paths_list
from oas_tools.oas import paths_operations
from oas_tools.oas import paths_show
from oas_tools.oas import summary
from oas_tools.oas import tags_list
from oas_tools.oas import tags_show
from oas_tools.oas import update

from .helpers import asset_filename

FILENAME = "FILENAME"
PET_YAML = asset_filename("pet.yaml")
PET2_YAML = asset_filename("pet2.yaml")


#################################################
# Top-level stuff
def test_info() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        summary(PET2_YAML)

        output = mock_stdout.getvalue().replace(PET2_YAML, FILENAME)
        expected = f"""\
OpenAPI spec ({FILENAME}):
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        diff(PET2_YAML, PET2_YAML)

        output = mock_stdout.getvalue().replace(PET2_YAML, FILENAME).replace("\n", "")
        expected = f"No differences between {FILENAME} and {FILENAME}"
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

@pytest.mark.parametrize(
    ["filename", "kwargs", "expected"],
    [
        pytest.param(PET2_YAML, {}, f"No differences between {FILENAME} and updated\n", id="no-updates"),
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
            f"Found 5 differences from {FILENAME}\n",
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
            f"Found 2 differences from {FILENAME}\n",
            id="remove-ops",
        ),
        pytest.param(
            PET2_YAML,
            {"allowed_operations": ["deletePetById"], "remove_all_tags": True, "display_option": DisplayOption.FINAL},
            PET2_UPDATE_DELETE,
            id="allow-ops",
        ),
    ]
)
def test_update_success(filename: str, kwargs: dict[str, Any], expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        update(filename, **kwargs)
        output = mock_stdout.getvalue().replace(filename, FILENAME)
        assert output == expected

def test_update_success_save() -> None:
    with (
        mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout,
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        with pytest.raises(typer.Exit) as err:
            update(PET2_YAML, allowed_operations=["listPets"], remove_operations=["deletePetById"])
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == "ERROR: cannot specify both --allow-op and --remove-op\n"


##########################################
# Operations
@pytest.mark.parametrize(
    ["filename", "search", "expected"],
    [
        pytest.param(
            PET2_YAML,
            None,
            "Found 4 operations:\n    createPets\n    deletePetById\n    listPets\n    showPetById\n",
            id="no-search",
        ),
        pytest.param(
            PET2_YAML,
            "id",
            "Found 2 operations matching 'id':\n    deletePetById\n    showPetById\n",
            id="search-case",
        ),
        pytest.param(PET2_YAML, "dogs", "No operations found matching 'dogs'\n", id="search-none"),
    ]
)
def test_operation_list(filename, search, expected) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        operation_list(filename, search)

        output = mock_stdout.getvalue()
        assert output == expected


PET2_SHOW_LIST_OP = """\
/pets:
    get:
        operationId: listPets
        parameters:
        -   description: How many items to return at one time (max 100)
            in: query
            name: limit
            required: false
            schema:
                format: int32
                maximum: 100
                type: integer
        responses:
            '200':
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Pets'
                description: A paged array of pets
                headers:
                    x-next:
                        description: A link to the next page of responses
                        schema:
                            type: string
            default:
                content:
                    application/json:
                        schema:
                            $ref: '#/components/schemas/Error'
                description: unexpected error
        summary: List all pets
        tags:
        - pets

"""

PET2_SHOW_DELETE_OP = """\
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
    params:
    -   description: The id of the pet to retrieve
        in: path
        name: petId
        required: true
        schema:
            type: string

"""

@pytest.mark.parametrize(
    ["filename", "operation", "expected"],
    [
        pytest.param(PET2_YAML, "listPets", PET2_SHOW_LIST_OP, id="found"),
        pytest.param(PET2_YAML, "deletePetById", PET2_SHOW_DELETE_OP, id="params"),
    ]
)
def test_operation_show_success(filename, operation, expected) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        operation_show(filename, operation)

        output = mock_stdout.getvalue()
        assert output == expected


def test_operation_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "missingPets"
        with pytest.raises(typer.Exit) as err:
            operation_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


##########################################
# Paths
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
def test_paths_list(filename: str, search: Optional[str], subpaths: bool, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        paths_show(filename, path, include_models=references)

        output = mock_stdout.getvalue()
        assert output == expected


def test_paths_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
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
def test_paths_operations_successs(filename: str, search: Optional[str], subpaths: bool, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        paths_operations(filename, search, subpaths)

        output = mock_stdout.getvalue()
        assert output == expected


def test_paths_operations_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "/no/such/path"
        with pytest.raises(typer.Exit) as err:
            paths_operations(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


##########################################
# Models
@pytest.mark.parametrize(
    ["filename", "search", "expected"],
    [
        pytest.param(PET_YAML, None, "Found 3 models:\n    Error\n    Pet\n    Pets\n", id="no-search"),
        pytest.param(PET_YAML, "et", "Found 2 models matching 'et':\n    Pet\n    Pets\n", id="search-simple"),
        pytest.param(PET_YAML, "Elliot", "No models found matching 'Elliot'\n", id="not-found"),
    ]
)
def test_models_list(filename: str, search: Optional[str], expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        models_list(filename, search)

        output = mock_stdout.getvalue()
        assert output == expected

PET_MODEL_PETS_SHOW = """\
Pets:
    items:
        $ref: '#/components/schemas/Pet'
    maxItems: 100
    type: array

"""

PET_MODEL_PETS_REF_SHOW = f"""\
Pet:
    properties:
        id:
            format: int64
            type: integer
        name:
            type: string
        tag:
            type: string
    required:
    - id
    - name
    type: object
{PET_MODEL_PETS_SHOW}\
"""
@pytest.mark.parametrize(
    ["filename", "model", "references", "expected"],
    [
        pytest.param(PET_YAML, "Pets", False, PET_MODEL_PETS_SHOW, id="found"),
        pytest.param(PET_YAML, "Pets", True, PET_MODEL_PETS_REF_SHOW, id="references"),
    ]
)
def test_models_show_success(filename, model, references, expected) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        models_show(filename, model, references)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            models_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


@pytest.mark.parametrize(
    ["filename", "model", "expected"],
    [
        pytest.param(PET_YAML, "Pets", "Found Pets uses 1 models:\n    Pet\n", id="found"),
        pytest.param(PET_YAML, "Pet", "Pet does not use any other models\n", id="no-uses"),
    ]
)
def test_models_uses_success(filename: str, model: str, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        models_uses(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_uses_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            models_uses(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: no model '{search}' found\n"


@pytest.mark.parametrize(
    ["filename", "model", "expected"],
    [
        pytest.param(PET_YAML, "Pet", "Found Pet is used by 1 models:\n    Pets\n", id="found"),
        pytest.param(PET_YAML, "Pets", "Pets is not used by any other models\n", id="no-uses"),
    ]
)
def test_models_used_by_success(filename: str, model: str, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        models_used_by(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_used_by_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            models_used_by(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: no model '{search}' found\n"


##########################################
# Tags
@pytest.mark.parametrize(
    ["filename", "search", "expected"],
    [
        pytest.param(PET2_YAML, None, "Found 2 tags:\n    admin\n    pets\n", id="no-search"),
        pytest.param(PET2_YAML, "ad", "Found 1 tags matching 'ad':\n    admin\n", id="search-simple"),
        pytest.param(PET2_YAML, "you're it", "No tags found matching 'you're it'\n", id="not-found"),
    ]
)
def test_tags_list(filename: str, search: Optional[str], expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        tags_list(filename, search)

        output = mock_stdout.getvalue()
        assert output == expected

@pytest.mark.parametrize(
    ["filename", "model", "expected"],
    [
        pytest.param(PET2_YAML, "admin", "Tag admin has 1 operations:\n    deletePetById\n", id="found"),
    ]
)
def test_tags_show_success(filename, model, expected) -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        tags_show(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_tags_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=io.StringIO) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            tags_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"
