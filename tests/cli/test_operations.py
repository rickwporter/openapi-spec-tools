from typing import Any
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.operations import operation_list
from openapi_spec_tools.cli.operations import operation_models
from openapi_spec_tools.cli.operations import operation_request_body
from openapi_spec_tools.cli.operations import operation_response_body
from openapi_spec_tools.cli.operations import operation_show
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET2_YAML = asset_filename("pet2.yaml")
PET3_YAML = asset_filename("pet3.yaml")
BODY_YAML = asset_filename("bodies.yaml")

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
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        operation_show(filename, operation)

        output = mock_stdout.getvalue()
        assert output == expected


def test_operation_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "missingPets"
        with pytest.raises(typer.Exit) as err:
            operation_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


@pytest.mark.parametrize(
    ["filename", "operation", "expected"],
    [
        pytest.param(PET2_YAML, "deletePetById", "Found deletePetById uses 1 models:\n    Error\n", id="delete"),
        pytest.param(
            PET2_YAML,
            "listPets", "Found listPets uses 3 models:\n    Error\n    Pet\n    Pets\n",
            id="list",
        ),
        pytest.param(PET3_YAML, "appVersion", "appVersion does not reference any models\n", id="none"),
    ]
)
def test_operation_models_success(filename, operation, expected) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        operation_models(filename, operation)

        output = mock_stdout.getvalue()
        assert output == expected


def test_operation_models_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "listCoyoteFood"
        with pytest.raises(typer.Exit) as err:
            operation_models(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"


def printed_schema(title: str, schema: str) -> str:
    """Match body output, including the indent the command adds after the final newline."""
    if not schema.endswith("\n"):
        schema += "\n"
    body = "    " + schema.replace("\n", "\n    ")
    return f"{title}\n{body}\n"


WIDGET_EXPANDED = """\
properties:
    name:
        type: string
    tag:
        type: string
required:
- name
type: object
x-reference: Widget
"""

REF_RESPONSE_SCHEMA = """\
content:
    application/json:
        schema:
            type: string
description: ok
x-reference: Ok
"""


@pytest.mark.parametrize(
    ["operation", "kwargs", "title", "schema"],
    [
        pytest.param(
            "expandRequest",
            {},
            "Found expandRequest required request-body (application/json):",
            "$ref: '#/components/schemas/Widget'\n",
            id="unexpanded",
        ),
        pytest.param(
            "expandRequest",
            {"expand": True},
            "Found expandRequest required request-body (application/json):",
            WIDGET_EXPANDED,
            id="expanded",
        ),
        pytest.param(
            "firstStandard",
            {},
            "Found firstStandard required request-body (application/xml):",
            "type: boolean\n",
            id="first-standard",
        ),
        pytest.param(
            "firstStandard",
            {"content_type": "application/json"},
            "Found firstStandard required request-body (application/json):",
            "type: integer\n",
            id="later-type",
        ),
        pytest.param(
            "firstStandard",
            {"content_type": "application/xml"},
            "Found firstStandard required request-body (application/xml):",
            "type: boolean\n",
            id="explicit-xml",
        ),
        pytest.param(
            "skipSchema",
            {},
            "Found skipSchema request-body (application/yaml):",
            "type: string\n",
            id="skip-missing-schema",
        ),
    ],
)
def test_operation_request_body_success(
    operation: str,
    kwargs: dict[str, Any],
    title: str,
    schema: str,
) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        operation_request_body(BODY_YAML, operation, **kwargs)

        assert mock_stdout.getvalue() == printed_schema(title, schema)


@pytest.mark.parametrize(
    ["operation", "kwargs", "expected"],
    [
        pytest.param("missingOp", {}, "ERROR: failed to find missingOp\n", id="no-op"),
        pytest.param("noBody", {}, "ERROR: no requestBody for noBody\n", id="no-body"),
        pytest.param(
            "expandRequest",
            {"content_type": "application/yaml"},
            "ERROR: no application/yaml content found for expandRequest\n",
            id="content-type",
        ),
        pytest.param("noSchema", {}, "ERROR: no standard content found for noSchema\n", id="no-schema"),
        pytest.param("plainOnly", {}, "ERROR: no standard content found for plainOnly\n", id="nonstandard"),
        pytest.param("emptyContent", {}, "ERROR: no requestBody for emptyContent\n", id="empty-content"),
        pytest.param(
            "firstStandard",
            {"content_type": "multipart/form-data"},
            "ERROR: no multipart/form-data content found for firstStandard\n",
            id="nonstandard-type",
        ),
    ],
)
def test_operation_request_body_failure(
    operation: str,
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        operation_request_body(BODY_YAML, operation, **kwargs)
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == expected


@pytest.mark.parametrize(
    ["operation", "kwargs", "title", "schema"],
    [
        pytest.param(
            "multiType",
            {},
            "Found multiType 200 response (application/xml):",
            "type: boolean\n",
            id="skip-error-and-html",
        ),
        pytest.param(
            "multiType",
            {"content_type": "application/json"},
            "Found multiType 200 response (application/json):",
            "type: number\n",
            id="content-type",
        ),
        pytest.param(
            "multiType",
            {"response_code": "400"},
            "Found multiType 400 response (application/json):",
            "type: string\n",
            id="response-code",
        ),
        pytest.param(
            "emptyThenBody",
            {},
            "Found emptyThenBody 201 response (application/json):",
            "type: string\n",
            id="skip-empty",
        ),
        pytest.param(
            "schemaLater",
            {},
            "Found schemaLater 200 response (application/yaml):",
            "type: string\n",
            id="skip-missing-schema",
        ),
        pytest.param(
            "refResponse",
            {},
            "Found refResponse 200 response:",
            "$ref: '#/components/responses/Ok'\n",
            id="ref-only",
        ),
        pytest.param(
            "refResponse",
            {"expand": True},
            "Found refResponse 200 response:",
            REF_RESPONSE_SCHEMA,
            id="ref-expand",
        ),
        pytest.param(
            "expandRequest",
            {"expand": True, "response_code": "default"},
            "Found expandRequest default response (application/json):",
            WIDGET_EXPANDED,
            id="expand-error",
        ),
    ],
)
def test_operation_response_body_success(
    operation: str,
    kwargs: dict[str, Any],
    title: str,
    schema: str,
) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        operation_response_body(BODY_YAML, operation, **kwargs)

        assert mock_stdout.getvalue() == printed_schema(title, schema)


@pytest.mark.parametrize(
    ["operation", "kwargs", "expected"],
    [
        pytest.param("missingOp", {}, "ERROR: failed to find missingOp\n", id="no-op"),
        pytest.param(
            "expandRequest",
            {},
            "ERROR: no successful standard response found for expandRequest\n",
            id="no-resp-content",
        ),
        pytest.param(
            "expandRequest",
            {"response_code": "201"},
            "ERROR: no 201 standard response found for expandRequest\n",
            id="code",
        ),
        pytest.param(
            "expandRequest",
            {"content_type": "application/yaml"},
            "ERROR: no successful application/yaml response found for expandRequest\n",
            id="content",
        ),
        pytest.param(
            "expandRequest",
            {"response_code": "201", "content_type": "application/foo"},
            "ERROR: no 201 application/foo response found for expandRequest\n",
            id="code-content",
        ),
        pytest.param(
            "expandRequest",
            {"response_code": "404"},
            "ERROR: no 404 standard response found for expandRequest\n",
            id="unknown-code",
        ),
        pytest.param("missingResponses", {}, "ERROR: no responses for missingResponses\n", id="no-resp"),
        pytest.param("noResponses", {}, "ERROR: no responses for noResponses\n", id="empty-resp"),
    ],
)
def test_operation_response_body_failure(
    operation: str,
    kwargs: dict[str, Any],
    expected: str,
) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        operation_response_body(BODY_YAML, operation, **kwargs)
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == expected
