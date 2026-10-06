from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest
import typer
import yaml

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
def test_api_generate_success_directory(code_dir, expected_dir, temp_working_dir):
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


def test_api_generate_success_copyright():
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


@pytest.mark.parametrize(
    ["layout", "expected_files"],
    [
        pytest.param(
            None,
            {
                'examine.py',
                'main.py',
                'owners.py',
                'pets.py',
                'vets.py',
            },
            id="all",
        ),
        pytest.param(asset_filename("layout_pets.yaml"), {"main.py"}, id="layout"),
    ],
)
def test_api_generate_success_layout(layout, expected_files, temp_working_dir):
    oas_file = asset_filename("pets_and_vets.yaml")
    pkg_name = "my_api_pkg"

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        generate_api(
            oas_file,
            pkg_name,
            layout_file=layout,
        )
        assert "Generated API files\n" == mock_stdout.getvalue()

    path = Path(temp_working_dir) / pkg_name
    filenames = {i.name for i in path.iterdir()}
    expected = {
        "__init__.py",
        "_environment.py",
        "_logging.py",
        "_requests.py",
    }
    expected.update(expected_files)
    assert filenames == expected

@pytest.mark.parametrize(
    ["body_type", "expected"],
    [
        pytest.param(
            "flat", [
                'def create_pets(\n    id: int = None,',
                'body["id"] = id',
            ],
            id="flat",
        ),
        pytest.param(
            "opaque", [
                'def create_pets(\n    body: Any = None,',
            ],
            id="opaque",
        ),
        pytest.param(
            "property", [
                'def create_pets(\n    id: int = None,',
            ],
            id="property",
        ),
    ],
)
def test_api_generate_success_body_type(body_type, expected, temp_working_dir):
    oas_file = asset_filename("pet.yaml")
    pkg_name = "my_api_pkg"

    generate_api(
        oas_file,
        pkg_name,
        body_type=body_type,
    )

    file = Path(temp_working_dir) / pkg_name / "pets.py"
    text = read_text(file.as_posix())
    for item in expected:
        assert item in text


def test_api_generate_success_config():
    oas_file = asset_filename("pet2.yaml")

    pkg_name = "my_api_pkg"
    directory = TemporaryDirectory()
    base_dir = Path(directory.name)

    copyright = "# Simple copyright message"
    config = {
        "copyright": copyright,
        "env_key": ["MY_API_KEY", "API_TOKEN"],
        "default_host": "https://127.0.0.1:8080",
    }
    config_file = base_dir / "config.yaml"
    config_file.write_text(yaml.dump(config))
    code_dir = base_dir / pkg_name

    with mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout:
        generate_api(
            oas_file,
            pkg_name,
            code_dir=code_dir,
            config_file=config_file.as_posix(),
        )
        assert "Generated API files\n" == mock_stdout.getvalue()

    # check copyright onthe file
    filenames = {
        "_environment.py",
        "_logging.py",
        "_requests.py",
        "pets.py",
    }
    for fname in filenames:
        file = code_dir / fname
        text = read_text(file.as_posix())
        assert copyright in text

    # spot check other things
    file = code_dir / "pets.py"
    text = read_text(file.as_posix())
    assert '_e.env_string(["MY_API_KEY", "API_TOKEN"], except_missing=True)' in text
    assert '"API_HOST", default="https://127.0.0.1:8080"' in text


def test_api_generate_failure_no_package_name():
    oas_file = asset_filename("pet2.yaml")

    directory = TemporaryDirectory()
    base_dir = Path(directory.name)
    pkg_name = "some_package"
    code_dir = base_dir / pkg_name
    message = "Must specify package_name in arguments or configuration"

    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as context,
    ):
        generate_api(oas_file, code_dir=code_dir)
        ex = context.value
        assert ex.exit_code == 1
        assert message == mock_stdout.getvalue()

