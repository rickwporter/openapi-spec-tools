import pytest

from oas_tools.constants import PATHS
from oas_tools.utils import find_references

from .helpers import open_test_oas


@pytest.mark.parametrize(
    ["asset", "path", "references"],
    [
        pytest.param("pet.yaml", "/pets", {"Error", "Pet", "Pets"}, id="/pet"),
        pytest.param("pet.yaml", "/pets/{petId}", {"Error", "Pet"}, id="/pets/{petId}"),
        pytest.param("ct.yaml", "/api/schema/", set(), id="/api/schema"),
        pytest.param(
            "ct.yaml",
            "/api/v1/environments/",
            {"Environment", "EnvironmentCreate", "PaginatedEnvironmentList"},
            id="/api/v1/environments",
        )
    ],
)
def test_utils_find_path_references(asset, path, references) -> None:
    oas = open_test_oas(asset)
    path_data = oas.get(PATHS, {}).get(path)
    found = find_references(path_data)
    assert references == found
