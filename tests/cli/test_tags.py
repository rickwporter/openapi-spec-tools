from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.tags import tags_list
from openapi_spec_tools.cli.tags import tags_show
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET2_YAML = asset_filename("pet2.yaml")

@pytest.mark.parametrize(
    ["filename", "search", "expected"],
    [
        pytest.param(PET2_YAML, None, "Found 2 tags:\n    admin\n    pets\n", id="no-search"),
        pytest.param(PET2_YAML, "ad", "Found 1 tags matching 'ad':\n    admin\n", id="search-simple"),
        pytest.param(PET2_YAML, "you're it", "No tags found matching 'you're it'\n", id="not-found"),
    ]
)
def test_tags_list(filename: str, search: str | None, expected: str) -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
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
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        tags_show(filename, model)

        output = mock_stdout.getvalue()
        assert output == expected


def test_tags_show_failure() -> None:
    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        search = "Dog"
        with pytest.raises(typer.Exit) as err:
            tags_show(PET2_YAML, search)
        assert err.value.exit_code == 1
        output = mock_stdout.getvalue()
        assert output == f"ERROR: failed to find {search}\n"
