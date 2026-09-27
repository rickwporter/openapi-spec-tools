from pathlib import Path
from tempfile import TemporaryDirectory

from openapi_spec_tools.base_gen.files import copy_and_update
from tests.helpers import asset_filename


def test_copy_and_update():
    source = asset_filename("arg_test.py")

    tempdir = TemporaryDirectory()
    dst_path = Path(tempdir.name) / "my_destination.py"
    package = "this.is_a.different.package"
    replacements = {
        "openapi_spec_tools.cli_gen": package,
    }

    copyright = "# fake copyright messge"
    copy_and_update(source, dst_path.as_posix(), replacements, copyright)

    text = dst_path.read_text()
    assert copyright in text
    assert package in text
    assert "openapi_spec_tools.cli_gen" not in text
