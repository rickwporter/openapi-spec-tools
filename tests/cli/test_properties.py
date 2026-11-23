from unittest import mock

import pytest

from openapi_spec_tools.cli.arguments import ExpansionType
from openapi_spec_tools.cli.properties import PropertySource
from openapi_spec_tools.cli.properties import properties_list
from tests.helpers import StringIo
from tests.helpers import asset_filename

MISC2_YAML = asset_filename("misc2.yaml")
PET_YAML = asset_filename("pet.yaml")

PET_PROPERTIES = """\
Found 7 properties:
    code:
        component/schemas/Error
    id:
        component/schemas/Pet
    limit:
        parameter/listPets
    message:
        component/schemas/Error
    name:
        component/schemas/Pet
    petId:
        parameter/showPetById
    tag:
        component/schemas/Pet
"""

MISC_PROPERTIES = """\
Found 12 properties:
    data:
        component/schemas/Wrapper
        response/getComposed
    extra:
        response/getComposed
    fromA:
        component/schemas/LoopA
    fromB:
        component/schemas/LoopB
    id:
        component/schemas/Pet
    limit:
        parameter/getComposed
    links:
        component/schemas/Wrapper
        response/getComposed
    name:
        component/schemas/Foo
        component/schemas/Pet
    next:
        component/schemas/LinksPage
    page:
        parameter/getComposed
    species:
        response/getSomethingElse
    tag:
        component/schemas/ComposedPet
"""


PET_MODELS = """\
Found 5 properties:
    code:
        component/schemas/Error
    id:
        component/schemas/Pet
    message:
        component/schemas/Error
    name:
        component/schemas/Pet
    tag:
        component/schemas/Pet
"""

PET_PARAMETERS = """\
Found 2 properties:
    limit:
        parameter/listPets
    petId:
        parameter/showPetById
"""

MISC_RESPONSES = """\
Found 4 properties:
    data:
        response/getComposed
    extra:
        response/getComposed
    links:
        response/getComposed
    species:
        response/getSomethingElse
"""


@pytest.mark.parametrize(
    ["filename", "search", "source", "expected"],
    [
        pytest.param(PET_YAML, None, PropertySource.ALL, PET_PROPERTIES, id="all"),
        pytest.param(
            PET_YAML,
            "a",
            PropertySource.ALL,
            "Found 3 properties matching 'a':\n"
            "    message:\n"
            "        component/schemas/Error\n"
            "    name:\n"
            "        component/schemas/Pet\n"
            "    tag:\n"
            "        component/schemas/Pet\n",
            id="search",
        ),
        pytest.param(PET_YAML, "Elliot", PropertySource.ALL, "No properties found matching 'Elliot'\n", id="not-found"),
        pytest.param(MISC2_YAML, None, PropertySource.ALL, MISC_PROPERTIES, id="inline-bodies"),
        pytest.param(PET_YAML, None, PropertySource.COMPONENTS, PET_MODELS, id="components"),
        pytest.param(PET_YAML, None, PropertySource.PARAMETERS, PET_PARAMETERS, id="parameters"),
        pytest.param(PET_YAML, None, PropertySource.REQUESTS, "No properties found\n", id="requests"),
        pytest.param(MISC2_YAML, None, PropertySource.RESPONSES, MISC_RESPONSES, id="responses"),
    ],
)
def test_properties_list(
    filename: str,
    search: str | None,
    source: PropertySource,
    expected: str,
) -> None:
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        properties_list(filename, search, source)

        assert mock_stdout.getvalue() == expected


PET_REQUESTS_EXPANDED = """\
Found 3 properties:
    id:
        request/createPets
    name:
        request/createPets
    tag:
        request/createPets
"""

MISC_COMPONENTS_EXPANDED = """\
Found 8 properties:
    data:
        component/schemas/Wrapper
    fromA:
        component/schemas/LoopA
        component/schemas/LoopB
    fromB:
        component/schemas/LoopA
        component/schemas/LoopB
    id:
        component/schemas/ComposedPet
        component/schemas/Pet
    links:
        component/schemas/Wrapper
    name:
        component/schemas/ComposedPet
        component/schemas/Foo
        component/schemas/Pet
    next:
        component/schemas/LinksPage
    tag:
        component/schemas/ComposedPet
"""

MISC_RESPONSES_FLATTENED = """\
Found 10 properties:
    data.id:
        response/getComposed
    data.name:
        response/getComposed
    extra:
        response/getComposed
    fromA:
        response/getComposedLoop
    fromB:
        response/getComposedLoop
    id:
        response/deleteSomethingElse
        response/getComposedModel
        response/getSomething
        response/postSomething
        response/putSomething
    links.next:
        response/getComposed
    name:
        response/deleteSomethingElse
        response/getComposedModel
        response/getSomething
        response/postSomething
        response/putSomething
    species:
        response/getSomethingElse
    tag:
        response/getComposedModel
"""


@pytest.mark.parametrize(
    ["filename", "source", "expansion", "expected"],
    [
        pytest.param(PET_YAML, PropertySource.REQUESTS, ExpansionType.EXPAND, PET_REQUESTS_EXPANDED, id="expand"),
        pytest.param(
            MISC2_YAML, PropertySource.COMPONENTS, ExpansionType.EXPAND, MISC_COMPONENTS_EXPANDED, id="expand-models",
        ),
        pytest.param(
            MISC2_YAML, PropertySource.RESPONSES, ExpansionType.FLATTEN, MISC_RESPONSES_FLATTENED, id="flatten",
        ),
    ],
)
def test_properties_list_expansion(
    filename: str,
    source: PropertySource,
    expansion: ExpansionType,
    expected: str,
) -> None:
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        properties_list(filename, None, source, expansion)

        assert mock_stdout.getvalue() == expected


def test_properties_list_expansion_skips_malformed(tmp_path) -> None:
    malformed = tmp_path / "malformed.yaml"
    malformed.write_text(
        "components:\n"
        "  schemas: 1\n"
        "  parameters:\n"
        "    Broken: 1\n"
        "paths:\n"
        "  /skip: nope\n"
        "  /pets:\n"
        "    summary: hi\n"
        "    parameters:\n"
        "    - 1\n"
        "    get:\n"
        "      operationId: listPets\n"
        "      responses: []\n",
        encoding="utf-8",
    )
    empty = tmp_path / "empty.yaml"
    empty.write_text("components: []\n", encoding="utf-8")

    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        properties_list(str(malformed), None, PropertySource.ALL, ExpansionType.EXPAND)
        properties_list(str(empty), None, PropertySource.ALL, ExpansionType.EXPAND)

        assert mock_stdout.getvalue() == "No properties found\nNo properties found\n"
