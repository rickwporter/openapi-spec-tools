from pathlib import Path
from typing import Any
from unittest import mock

import pytest
import requests
import typer
import yaml

from openapi_spec_tools.cli.references import _DOWNLOAD_TIMEOUT_SECONDS
from openapi_spec_tools.cli.references import check_duplicate_file_names
from openapi_spec_tools.cli.references import download_references
from openapi_spec_tools.cli.references import extract_filename
from openapi_spec_tools.cli.references import find_external_references
from openapi_spec_tools.cli.references import get_external_references
from openapi_spec_tools.cli.references import is_url
from tests.helpers import StringIo
from tests.helpers import asset_filename

PET_YAML = asset_filename("pet.yaml")
COMMON_URL = "https://example.com/common.yaml"
ERRORS_URL = "https://cdn.example/errors.json"

FIND_EXTERNAL = """\
https://cdn.example/errors.json:
- /Foo
https://example.com/common.yaml:
- /components/schemas/Error
- /components/schemas/Pet

"""


def _spec_with_refs(*refs: str) -> dict[str, Any]:
    properties = {f"item{index}": {"$ref": ref} for index, ref in enumerate(refs)}
    return {
        "openapi": "3.0.3",
        "info": {"title": "external", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": {"Local": {"type": "object", "properties": properties}}},
    }


def _write_spec(directory: Path, spec: dict[str, Any]) -> Path:
    path = directory / "spec.yaml"
    path.write_text(yaml.dump(spec), encoding="utf-8", newline="\n")
    return path


def test_get_external_references_ignores_local() -> None:
    spec = _spec_with_refs("#/components/schemas/Local")
    assert get_external_references(spec) == {}


def test_get_external_references_groups_fragments() -> None:
    spec = _spec_with_refs(
        f"{COMMON_URL}#/components/schemas/Pet",
        f"{COMMON_URL}#/components/schemas/Error",
        f"{ERRORS_URL}#/components/schemas/Failure",
        "#/components/schemas/Local",
    )
    assert get_external_references(spec) == {
        COMMON_URL: ["/components/schemas/Error", "/components/schemas/Pet"],
        ERRORS_URL: ["/components/schemas/Failure"],
    }


@pytest.mark.parametrize(
    ["reference"],
    [
        pytest.param("https://example.com/pet.yaml", id="no-fragment"),
        pytest.param("https://example.com/a.yaml#/Foo#bar", id="extra-hash"),
        pytest.param("not-a-reference", id="bare"),
    ],
)
def test_get_external_references_invalid(reference: str, caplog: pytest.LogCaptureFixture) -> None:
    spec = _spec_with_refs(reference)
    with caplog.at_level("ERROR", logger="oas.cli.references"):
        assert get_external_references(spec) == {}
    assert f"Invalid reference: {reference}" in caplog.text


@pytest.mark.parametrize(
    ["value", "expected"],
    [
        pytest.param("https://example.com/common.yaml", True, id="https"),
        pytest.param("http://example.com/a.yaml", True, id="http"),
        pytest.param("common.yaml", False, id="bare"),
        pytest.param("./dir/pet.yaml", False, id="relative"),
        pytest.param("../components/Pet.yaml", False, id="parent"),
        pytest.param("/abs/pet.yaml", False, id="absolute"),
    ],
)
def test_is_url(value: str, expected: bool) -> None:
    assert is_url(value) is expected


@pytest.mark.parametrize(
    ["url", "expected"],
    [
        pytest.param("https://example.com/a/b/common.yaml", "common.yaml", id="url"),
        pytest.param("https://example.com/common.yaml", "common.yaml", id="host-file"),
        pytest.param("https://example.com/common.yaml?version=1", "common.yaml", id="query"),
        pytest.param(
            "https://example.com/path/common.yaml#/components/schemas/Pet",
            "common.yaml",
            id="fragment",
        ),
        pytest.param("./dir/pet.yaml", "pet.yaml", id="relative"),
        pytest.param("common.yaml", "common.yaml", id="bare"),
    ],
)
def test_extract_filename(url: str, expected: str) -> None:
    assert extract_filename(url) == expected


def test_check_duplicate_file_names_unique() -> None:
    check_duplicate_file_names([
        "https://a.example/pet.yaml",
        "https://a.example/owner.yaml",
    ])


def test_check_duplicate_file_names_conflict() -> None:
    urls = [
        "https://a.example/pet.yaml",
        "https://b.example/owner.yaml",
        "https://c.example/pet.yaml",
        "https://d.example/owner.yaml",
    ]
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        check_duplicate_file_names(urls)
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == "ERROR: Duplicate filenames for: owner.yaml, pet.yaml\n"


def test_find_external_references_none() -> None:
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        find_external_references(PET_YAML)
    assert mock_stdout.getvalue() == f"No external references found in {PET_YAML}\n"


def test_find_external_references_found(tmp_path: Path) -> None:
    spec = _spec_with_refs(
        f"{COMMON_URL}#/components/schemas/Pet",
        f"{COMMON_URL}#/components/schemas/Error",
        f"{ERRORS_URL}#/Foo",
    )
    filename = _write_spec(tmp_path, spec)
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        find_external_references(str(filename))
    assert mock_stdout.getvalue() == FIND_EXTERNAL


def test_download_references_none(tmp_path: Path) -> None:
    out_dir = tmp_path / "unused"
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        download_references(PET_YAML, out_dir=str(out_dir))
    assert mock_stdout.getvalue() == f"No external references found in {PET_YAML}\n"
    assert not out_dir.exists()


def test_download_references_writes_files(tmp_path: Path) -> None:
    spec = _spec_with_refs(
        f"{COMMON_URL}#/components/schemas/Pet",
        f"{ERRORS_URL}#/components/schemas/Failure",
    )
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "nested" / "refs"
    bodies = {
        COMMON_URL: "title: common\ndescription: café\n",
        ERRORS_URL: '{"title": "errors"}\n',
    }

    def fake_get(url: str, timeout: int) -> mock.Mock:
        response = mock.Mock()
        response.text = bodies[url]
        response.raise_for_status.return_value = None
        assert timeout == _DOWNLOAD_TIMEOUT_SECONDS
        return response

    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch("openapi_spec_tools.cli.references.requests.get", side_effect=fake_get) as mock_get,
    ):
        download_references(str(filename), out_dir=str(out_dir))

    assert (out_dir / "common.yaml").read_text(encoding="utf-8") == bodies[COMMON_URL]
    assert (out_dir / "errors.json").read_text(encoding="utf-8") == bodies[ERRORS_URL]
    assert mock_get.call_count == 2
    output = mock_stdout.getvalue().splitlines()
    assert output == [
        f"Wrote {out_dir / 'errors.json'} for {ERRORS_URL}",
        f"Wrote {out_dir / 'common.yaml'} for {COMMON_URL}",
    ]


def test_download_references_skips_local_file(tmp_path: Path) -> None:
    local_name = "common.yaml"
    spec = _spec_with_refs(
        f"{local_name}#/components/schemas/Pet",
        f"{ERRORS_URL}#/components/schemas/Failure",
    )
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
    out_dir.mkdir()
    local_file = out_dir / local_name
    local_text = "title: local\n"
    local_file.write_text(local_text, encoding="utf-8", newline="\n")
    body = '{"title": "errors"}\n'

    def fake_get(url: str, timeout: int) -> mock.Mock:
        assert url == ERRORS_URL
        assert timeout == _DOWNLOAD_TIMEOUT_SECONDS
        response = mock.Mock()
        response.text = body
        response.raise_for_status.return_value = None
        return response

    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch("openapi_spec_tools.cli.references.requests.get", side_effect=fake_get) as mock_get,
    ):
        download_references(str(filename), out_dir=str(out_dir))

    assert mock_get.call_count == 1
    assert local_file.read_text(encoding="utf-8") == local_text
    assert (out_dir / "errors.json").read_text(encoding="utf-8") == body
    assert mock_stdout.getvalue().splitlines() == [
        f"{local_name} is a filename instead of a URL",
        f"Wrote {out_dir / 'errors.json'} for {ERRORS_URL}",
    ]


def test_download_references_missing_local_file(tmp_path: Path) -> None:
    local_name = "common.yaml"
    spec = _spec_with_refs(f"{local_name}#/components/schemas/Pet")
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch("openapi_spec_tools.cli.references.requests.get") as mock_get,
        pytest.raises(typer.Exit) as err,
    ):
        download_references(str(filename), out_dir=str(out_dir))
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == f"ERROR: Local file {local_name} does not exist!\n"
    mock_get.assert_not_called()
    assert not (out_dir / local_name).exists()


def test_download_references_duplicate_names(tmp_path: Path) -> None:
    spec = _spec_with_refs(
        "https://a.example/api/pet.yaml#/components/schemas/Pet",
        "https://b.example/other/pet.yaml#/components/schemas/Pet",
    )
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch("openapi_spec_tools.cli.references.requests.get") as mock_get,
        pytest.raises(typer.Exit) as err,
    ):
        download_references(str(filename), out_dir=str(out_dir))
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == "ERROR: Duplicate filenames for: pet.yaml\n"
    mock_get.assert_not_called()
    assert not out_dir.exists()


def test_download_references_request_error(tmp_path: Path) -> None:
    spec = _spec_with_refs(f"{COMMON_URL}#/components/schemas/Pet")
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch(
            "openapi_spec_tools.cli.references.requests.get",
            side_effect=requests.ConnectionError("network down"),
        ),
        pytest.raises(typer.Exit) as err,
    ):
        download_references(str(filename), out_dir=str(out_dir))
    assert err.value.exit_code == 1
    output = mock_stdout.getvalue()
    assert output == f"ERROR: Failed to download {COMMON_URL}: network down\n"
    assert not (out_dir / "common.yaml").exists()


def test_download_references_http_error(tmp_path: Path) -> None:
    spec = _spec_with_refs(f"{COMMON_URL}#/components/schemas/Pet")
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
    response = mock.Mock()
    response.raise_for_status.side_effect = requests.HTTPError("404 Client Error")
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch("openapi_spec_tools.cli.references.requests.get", return_value=response),
        pytest.raises(typer.Exit) as err,
    ):
        download_references(str(filename), out_dir=str(out_dir))
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == f"ERROR: Failed to download {COMMON_URL}: 404 Client Error\n"
    assert not (out_dir / "common.yaml").exists()


@pytest.mark.parametrize(
    ["command"],
    [
        pytest.param(find_external_references, id="find"),
        pytest.param(download_references, id="download"),
    ],
)
def test_references_missing_file(command) -> None:
    filename = "no-such-openapi.yaml"
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        command(filename)
    assert err.value.exit_code == 1
    assert mock_stdout.getvalue() == f"ERROR: failed to find {filename}\n"
