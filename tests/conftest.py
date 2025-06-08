import pytest

from openapi_spec_tools.cli_gen.generate import set_copyright


@pytest.fixture
def copyright_fixture():
    set_copyright()  # set to default
    yield
    set_copyright() # reset to default
