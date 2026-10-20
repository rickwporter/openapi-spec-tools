from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.arguments import ExpansionType
from openapi_spec_tools.cli.models import models_list
from openapi_spec_tools.cli.models import models_operations
from openapi_spec_tools.cli.models import models_show
from openapi_spec_tools.cli.models import models_used_by
from openapi_spec_tools.cli.models import models_uses
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET_YAML = asset_filename("pet.yaml")
PET2_YAML = asset_filename("pet2.yaml")
MISC2_YAML = asset_filename("misc2.yaml")

@pytest.mark.parametrize(
    ["filename", "search", "expected"],
    [
        pytest.param(PET_YAML, None, "Found 3 models:\n    Error\n    Pet\n    Pets\n", id="no-search"),
        pytest.param(PET_YAML, "et", "Found 2 models matching 'et':\n    Pet\n    Pets\n", id="search-simple"),
        pytest.param(PET_YAML, "Elliot", "No models found matching 'Elliot'\n", id="not-found"),
    ]
)
def test_models_list(filename: str, search: str | None, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        models_list(filename, search)

        output = mock_stdout.getvalue()
        assert output == expected

MISC_MODEL_COMPOSED_PET_SHOW = """\
ComposedPet:
    allOf:
    -   $ref: '#/components/schemas/Pet'
    -   properties:
            tag:
                type: string
        required:
        - name
        type: object
    description: Pet plus extra
    required:
    - tag
"""
MISC_MODEL_COMPOSED_PET_EXPAND = """\
ComposedPet:
    description: Pet plus extra
    properties:
        id:
            type: integer
            x-reference: Pet
        name:
            type: string
            x-reference: Pet
        tag:
            type: string
            x-reference: ComposedPet
    required:
    - name
    - tag
    type: object
    x-reference: Pet
"""
MISC_MODEL_PET_SHOW = """\
Pet:
    properties:
        id:
            type: integer
        name:
            type: string
    type: object
"""
MISC_MODEL_PET_EXPAND = """\
Pet:
    properties:
        id:
            type: integer
            x-reference: Pet
        name:
            type: string
            x-reference: Pet
    type: object
"""
MISC_MODEL_COMPOSED_PET_REF = f"""\
{MISC_MODEL_COMPOSED_PET_SHOW}\
{MISC_MODEL_PET_SHOW}
"""

MISC_MODEL_COMPOSED_PET_REF_EXPAND = f"""\
{MISC_MODEL_COMPOSED_PET_EXPAND}\
{MISC_MODEL_PET_EXPAND}
"""

@pytest.mark.parametrize(
    ["filename", "model", "references", "expansion", "expected"],
    [
        pytest.param(MISC2_YAML, "Pet", False, ExpansionType.NONE, MISC_MODEL_PET_SHOW, id="basic"),
        pytest.param(MISC2_YAML, "Pet", True, ExpansionType.EXPAND, MISC_MODEL_PET_EXPAND, id="no-refs"),
        pytest.param(MISC2_YAML, "ComposedPet", False, ExpansionType.NONE, MISC_MODEL_COMPOSED_PET_SHOW, id="complex"),
        pytest.param(MISC2_YAML, "ComposedPet", True, ExpansionType.NONE, MISC_MODEL_COMPOSED_PET_REF, id="ref"),
        pytest.param(
            MISC2_YAML, "ComposedPet", False, ExpansionType.EXPAND, MISC_MODEL_COMPOSED_PET_EXPAND, id="expand",
        ),
        pytest.param(
            MISC2_YAML, "ComposedPet", True, ExpansionType.EXPAND, MISC_MODEL_COMPOSED_PET_REF_EXPAND, id="ref-expand",
        ),
    ]
)
def test_models_show_success(filename, model, references, expansion, expected) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        models_show(filename, model, include_referenced=references, expansion=expansion)

        output = mock_stdout.getvalue()
        assert output.rstrip() == expected.rstrip()


def test_models_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        models_uses(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_uses_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        models_used_by(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_used_by_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            models_used_by(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: no model '{search}' found\n"


@pytest.mark.parametrize(
    ["filename", "model", "expected"],
    [
        pytest.param(PET2_YAML, "Pets", "Found Pets is used by 1 operations:\n    listPets\n", id="single"),
        pytest.param(
            PET2_YAML,
            "Pet", "Found Pet is used by 3 operations:\n    createPets\n    listPets\n    showPetById\n",
            id="multiple",
        ),
    ]
)
def test_models_operations_success(filename: str, model: str, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        models_operations(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_models_operations_failures() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "Iguana"
        with pytest.raises(typer.Exit) as err:
            models_operations(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: no model '{search}' found\n"
