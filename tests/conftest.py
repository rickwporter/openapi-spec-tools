import os
from tempfile import TemporaryDirectory

import pytest


@pytest.fixture
def temp_working_dir():
    orig = os.getcwd()
    with TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        yield temp_dir
        os.chdir(orig)
