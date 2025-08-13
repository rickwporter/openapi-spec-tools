from pathlib import Path
from tempfile import TemporaryDirectory

from openapi_spec_tools.base_gen.files import DEFAULT_COPYRIGHT
from openapi_spec_tools.base_gen.files import copy_and_update
from openapi_spec_tools.base_gen.files import copyright
from openapi_spec_tools.base_gen.files import set_copyright
from tests.helpers import asset_filename


def test_copyright(copyright_fixture):
    assert DEFAULT_COPYRIGHT == copyright()

    text = "this is my copyright"
    set_copyright(text)
    assert text == copyright()

    # reset to default
    set_copyright()
    assert DEFAULT_COPYRIGHT == copyright()


def test_copy_and_update():
    source = asset_filename("arg_test.py")

    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name) / "my_destination.py"
    package = "this.is_a.different.package"
    replacements = {
        "openapi_spec_tools.cli_gen": package,
    }

    copy_and_update(source, dst_path.as_posix(), replacements)

    text = dst_path.read_text()
    assert DEFAULT_COPYRIGHT in text
    assert package in text
    assert "openapi_spec_tools.cli_gen" not in text
