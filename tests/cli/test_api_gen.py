from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from openapi_spec_tools.cli.api_gen import generate_api
from tests.cli.helpers import read_text
from tests.helpers import StringIo
from tests.helpers import asset_filename


@pytest.mark.parametrize(
    ["code_dir", "expected_dir"],
    [
        pytest.param(None, "my_api_pkg", id="basic"),
        pytest.param("sna", "sna", id="overrides"),
    ],
)
def test_api_generate_success(code_dir, expected_dir, temp_working_dir):
    oas_file = asset_filename("pet2.yaml")
    pkg_name = "my_api_pkg"
    base_dir = Path(temp_working_dir)
    code_path = Path(base_dir, code_dir).as_posix() if code_dir else None

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        generate_api(
            oas_file,
            pkg_name,
            code_dir=code_path,
        )
        assert "Generated API files\n" == mock_stdout.getvalue()

    # NOTE: just check some basics here -- more detailed checks elsewhere
    path = Path(temp_working_dir) / expected_dir
    file = path / "pets.py"
    assert file.exists()

    text = file.read_text()
    assert f"Copyright {datetime.now().year}" in text

    filenames = {i.name for i in path.iterdir()}
    expected = {
        "__init__.py",
        "_environment.py",
        "_logging.py",
        "_requests.py",
        "pets.py",
    }
    assert filenames == expected


def test_api_generate_success_copyright(copyright_fixture):
    oas_file = asset_filename("pet2.yaml")

    pkg_name = "my_api_pkg"
    directory = TemporaryDirectory()
    base_dir = Path(directory.name)

    copyright_text = "# Simple copyright message"
    copyright_file = base_dir / "copyright.txt"
    copyright_file.write_bytes(copyright_text.encode(encoding="utf-8"))
    code_dir = base_dir / "foo"

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        generate_api(
            oas_file,
            pkg_name,
            code_dir=code_dir.as_posix(),
            copyright_file=copyright_file.as_posix()
        )
        assert "Generated API files\n" == mock_stdout.getvalue()

    filenames = {
        "_environment.py",
        "_logging.py",
        "_requests.py",
        "pets.py",
    }
    for fname in filenames:
        file = code_dir / fname
        text = read_text(file.as_posix())
        assert copyright_text in text
