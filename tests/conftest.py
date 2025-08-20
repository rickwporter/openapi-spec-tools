import os
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.base_gen.files import set_copyright


@pytest.fixture
def copyright_fixture():
    set_copyright()  # set to default
    yield
    set_copyright() # reset to default


@pytest.fixture
def temp_working_dir():
    orig = os.getcwd()
    with TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        yield temp_dir
        os.chdir(orig)
