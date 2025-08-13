import pytest

from openapi_spec_tools.base_gen.files import set_copyright


@pytest.fixture
def copyright_fixture():
    set_copyright()  # set to default
    yield
    set_copyright() # reset to default
