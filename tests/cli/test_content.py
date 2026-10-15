from unittest import mock

import pytest

from openapi_spec_tools.cli.content import content_type_list
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET2_YAML = asset_filename("pet2.yaml")

@pytest.mark.parametrize(
    ["filename", "max_size", "content_type", "expected"],
    [
        pytest.param(
            PET2_YAML,
            None,
            None,
            "application/json\n    createPets\n    deletePetById\n"
            "    listPets\n    showPetById\n",
            id="basic",
        ),
        pytest.param(
            PET2_YAML,
            2,
            None,
            "application/json\n    createPets\n    deletePetById\n"
            "    ...\n    + 2 more\n",
            id="max-size",
        ),
        pytest.param(PET2_YAML, None, "application/yaml", "No content-types found\n", id="not-found"),
    ]
)
def test_content_type_list(filename, max_size, content_type, expected) -> None:
    args = {
        "filename": filename,
        "content_type": content_type,
    }
    if max_size is not None:
        args["max_size"] = max_size

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        content_type_list(**args)

        output = mock_stdout.getvalue()
        assert output == expected
