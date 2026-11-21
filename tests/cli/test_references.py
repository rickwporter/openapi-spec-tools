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
from openapi_spec_tools.cli.references import get_spec_data
from openapi_spec_tools.cli.references import is_url
from openapi_spec_tools.cli.references import update_references
from tests.cli.helpers import read_text
from tests.helpers import StringIo
from tests.helpers import asset_filename
from tests.helpers import open_test_oas

PET_YAML = asset_filename("pet.yaml")
PET_EXTERNAL = asset_filename("pet_external.yaml")
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
        pytest.param("C:/abs/pet.yaml", False, id="windows-drive"),
        pytest.param("c:\\foo", False, id="windows-backslash"),
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
        pytest.param("C:/abs/dir/pet.yaml", "pet.yaml", id="windows-drive"),
        pytest.param("c:\\foo\\pet.yaml", "pet.yaml", id="windows-backslash"),
    ],
)
def test_extract_filename(url: str, expected: str) -> None:
    assert extract_filename(url) == expected


def _response_text(text: str) -> mock.Mock:
    response = mock.Mock()
    response.text = text
    response.raise_for_status.return_value = None
    return response


PETS = {"openapi": "3.0.3", "info": {"title": "Pets"}}


@pytest.mark.parametrize(
    ["name", "content", "expected"],
    [
        pytest.param("common.yaml", b"openapi: 3.0.3\ninfo:\n  title: Pets\n", PETS, id="yaml"),
        pytest.param("common.yml", b"title: Pets\n", {"title": "Pets"}, id="yml"),
        pytest.param("common.json", b'{"openapi": "3.0.3", "info": {"title": "Pets"}}', PETS, id="json"),
        pytest.param("common.JSON", b'{"title": "Pets"}', {"title": "Pets"}, id="json-upper"),
    ],
)
def test_get_spec_data_local(tmp_path: Path, name: str, content: bytes, expected: dict[str, Any]) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    actual = get_spec_data(str(path))
    assert actual == expected


def test_get_spec_data_url(caplog: pytest.LogCaptureFixture) -> None:
    content = '{"openapi": "3.0.3"}\n'
    url = "https://example.com/specs/common.YAML"
    response = _response_text(content)
    with (
        caplog.at_level("INFO", logger="oas.cli.references"),
        mock.patch("openapi_spec_tools.cli.references.requests.get", return_value=response) as mock_get,
    ):
        assert get_spec_data(url) == {"openapi": "3.0.3"}
    mock_get.assert_called_once_with(url, timeout=_DOWNLOAD_TIMEOUT_SECONDS)
    assert f"Download of {url} too " in caplog.text


def test_get_spec_data_missing_local_file() -> None:
    missing = "missing.yaml"
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        get_spec_data(missing)
    assert err.value.exit_code == 1
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: Local file {missing} does not exist!\n"


def test_get_spec_data_download_error() -> None:
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        mock.patch(
            "openapi_spec_tools.cli.references.requests.get",
            side_effect=requests.ConnectionError("network down"),
        ),
        pytest.raises(typer.Exit) as err,
    ):
        get_spec_data(COMMON_URL)
    assert err.value.exit_code == 1
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: Failed to download {COMMON_URL}: network down\n"


@pytest.mark.parametrize(
    ["name", "content", "message"],
    [
        pytest.param("notes.txt", b"title: Pets\n", "Unsupported spec file type", id="extension"),
        pytest.param("broken.json", b"{", "Failed to parse", id="invalid-json"),
        pytest.param("broken.yaml", b":\n  -", "Failed to parse", id="invalid-yaml"),
        pytest.param("list.json", b"[1, 2]", "expected an object", id="json-list"),
        pytest.param("list.yaml", b"- pets\n", "expected an object", id="yaml-list"),
    ],
)
def test_get_spec_data_parse_errors(tmp_path: Path, name: str, content: bytes, message: str) -> None:
    path = tmp_path / name
    path.write_bytes(content)
    with (
        mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as err,
    ):
        get_spec_data(str(path))
    assert err.value.exit_code == 1
    actual = mock_stdout.getvalue()
    assert message in actual


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
    actual = mock_stdout.getvalue()
    assert actual == "ERROR: Duplicate filenames for: owner.yaml, pet.yaml\n"


def test_find_external_references_none() -> None:
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        find_external_references(PET_YAML)
    actual = mock_stdout.getvalue()
    assert actual == f"No external references found in {PET_YAML}\n"


def test_find_external_references_found(tmp_path: Path) -> None:
    spec = _spec_with_refs(
        f"{COMMON_URL}#/components/schemas/Pet",
        f"{COMMON_URL}#/components/schemas/Error",
        f"{ERRORS_URL}#/Foo",
    )
    filename = _write_spec(tmp_path, spec)
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        find_external_references(str(filename))
    actual = mock_stdout.getvalue()
    assert actual == FIND_EXTERNAL


def test_download_references_none(tmp_path: Path) -> None:
    out_dir = tmp_path / "unused"
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        download_references(PET_YAML, out_dir=str(out_dir))
    actual = mock_stdout.getvalue()
    assert actual == f"No external references found in {PET_YAML}\n"
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
        ERRORS_URL: '{"title": "errors"}\r\n',
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

    assert read_text(out_dir / "common.yaml") == bodies[COMMON_URL]
    assert read_text(out_dir / "errors.json") == '{"title": "errors"}\n'
    assert mock_get.call_count == 2
    actual = mock_stdout.getvalue()
    assert actual.splitlines() == [
        f"Wrote {out_dir / 'errors.json'} for {ERRORS_URL}",
        f"Wrote {out_dir / 'common.yaml'} for {COMMON_URL}",
    ]


def test_download_references_copies_local_file(tmp_path: Path) -> None:
    local_name = "common.yaml"
    local_file = tmp_path / local_name
    local_bytes = "title: local\ndescription: café\n".encode()
    local_file.write_bytes(local_bytes)
    spec = _spec_with_refs(
        f"{local_name}#/components/schemas/Pet",
        f"{ERRORS_URL}#/components/schemas/Failure",
    )
    filename = _write_spec(tmp_path, spec)
    out_dir = tmp_path / "refs"
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
    assert read_text(local_file) == "title: local\ndescription: café\n"
    assert read_text(out_dir / "common.yaml") == "title: local\ndescription: café\n"
    assert read_text(out_dir / "errors.json") == body
    actual = mock_stdout.getvalue()
    assert actual.splitlines() == [
        f"Wrote {out_dir / 'common.yaml'} for {local_name}",
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
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: Local file {local_name} does not exist!\n"
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
    actual = mock_stdout.getvalue()
    assert actual == "ERROR: Duplicate filenames for: pet.yaml\n"
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
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: Failed to download {COMMON_URL}: network down\n"
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
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: Failed to download {COMMON_URL}: 404 Client Error\n"
    assert not (out_dir / "common.yaml").exists()


@pytest.mark.parametrize(
    ["command"],
    [
        pytest.param(find_external_references, id="find"),
        pytest.param(download_references, id="download"),
        pytest.param(update_references, id="update"),
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
    actual = mock_stdout.getvalue()
    assert actual == f"ERROR: failed to find {filename}\n"


def _assert_pet_external_resolved(spec: dict[str, Any]) -> None:
    """Assert pet.yaml models were copied and the external refs are local."""
    shared = open_test_oas("pet.yaml")["components"]["schemas"]
    schemas = spec["components"]["schemas"]
    assert set(schemas) == {"Catalog", "Error", "Pet", "Pets"}
    assert schemas["Catalog"] == {"type": "object", "properties": {"name": {"type": "string"}}}
    assert schemas["Pet"] == shared["Pet"]
    assert schemas["Pets"] == shared["Pets"]
    assert schemas["Error"] == shared["Error"]
    responses = spec["paths"]["/catalog"]["get"]["responses"]
    assert responses["200"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Pets"
    assert responses["default"]["content"]["application/json"]["schema"]["$ref"] == "#/components/schemas/Error"


def test_update_references_none(tmp_path: Path) -> None:
    out_file = tmp_path / "updated.yaml"
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        update_references(PET_YAML, updated_filename=str(out_file))
    actual = mock_stdout.getvalue()
    assert actual == f"No external references found in {PET_YAML}\n"
    assert not out_file.exists()


def test_update_references_inlines_models(tmp_path: Path) -> None:
    filename = tmp_path / "pet_external.yaml"
    filename.write_text(read_text(PET_EXTERNAL), encoding="utf-8", newline="\n")
    (tmp_path / "pet.yaml").write_text(read_text(PET_YAML), encoding="utf-8", newline="\n")
    with mock.patch("sys.stdout", new_callable=StringIo) as mock_stdout:
        update_references(str(filename))
    actual = mock_stdout.getvalue()
    assert actual == ""
    _assert_pet_external_resolved(yaml.safe_load(read_text(filename)))


def test_update_references_out_file(tmp_path: Path) -> None:
    original = read_text(PET_EXTERNAL)
    out_file = tmp_path / "updated.yaml"
    update_references(PET_EXTERNAL, updated_filename=str(out_file))
    assert read_text(PET_EXTERNAL) == original
    _assert_pet_external_resolved(yaml.safe_load(read_text(out_file)))


def test_update_references_missing_inner_model(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    common = {
        "components": {
            "schemas": {
                "Pet": {
                    "type": "object",
                    "properties": {"friend": {"$ref": "#/components/schemas/Missing"}},
                },
            },
        },
    }
    common_path = tmp_path / "common.yaml"
    common_path.write_text(yaml.dump(common), encoding="utf-8", newline="\n")
    filename = _write_spec(tmp_path, _spec_with_refs("common.yaml#/components/schemas/Pet"))
    with caplog.at_level("WARNING", logger="oas.cli.references"):
        update_references(str(filename))
    assert "Failed to find ref for schemas/Missing" in caplog.text
    schemas = yaml.safe_load(read_text(filename))["components"]["schemas"]
    assert "Missing" not in schemas
    assert schemas["Pet"]["properties"]["friend"]["$ref"] == "#/components/schemas/Missing"
    assert schemas["Local"]["properties"]["item0"]["$ref"] == "#/components/schemas/Pet"
