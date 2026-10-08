from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.layout.config import LayoutConfig
from openapi_spec_tools.types import ContentType


def test_from_config_defaults():
    uut = LayoutConfig()

    assert uut.prefix is None
    assert uut.max_help_length is None
    assert uut.supported_content is None
    assert uut.common_operations is None
    assert uut.page_size_params is None
    assert uut.page_start_params is None
    assert uut.item_start_params is None
    assert uut.items_properties is None
    assert uut.next_properties is None
    assert uut.next_headers is None


def test_from_config_overrides():
    supported = [ContentType.APP_JSON, ContentType.APP_YAML]
    operations = {"add": "create", "get": "show"}

    uut = LayoutConfig(
        prefix="/api/v1",
        max_help_length=40,
        supported_content=supported,
        common_operations=operations,
        page_size_params="limit",
        page_start_params=["page", "offset"],
        item_start_params="start",
        items_properties=["results", "items"],
        next_properties="next",
        next_headers=["Link", "X-Next"],
    )

    assert "/api/v1" == uut.prefix
    assert 40 == uut.max_help_length
    assert supported == uut.supported_content
    assert operations == uut.common_operations
    assert "limit" == uut.page_size_params
    assert ["page", "offset"] == uut.page_start_params
    assert "start" == uut.item_start_params
    assert ["results", "items"] == uut.items_properties
    assert "next" == uut.next_properties
    assert ["Link", "X-Next"] == uut.next_headers


def test_from_yaml_defaults():
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "layout.yaml"
        path.write_text("max_help_length: 40\n", encoding="utf-8")
        config = LayoutConfig.from_yaml(path)

    assert LayoutConfig(max_help_length=40) == config


def test_from_yaml():
    text = """\
prefix: /api/v1
max_help_length: 40
supported_content:
  - application/json
  - application/yaml
common_operations:
  add: create
  get: show
page_size_params: limit
page_start_params:
  - page
  - offset
item_start_params: start
items_properties:
  - results
  - items
next_properties: next
next_headers:
  - Link
  - X-Next
"""
    expected = LayoutConfig(
        prefix="/api/v1",
        max_help_length=40,
        supported_content=[ContentType.APP_JSON, ContentType.APP_YAML],
        common_operations={"add": "create", "get": "show"},
        page_size_params="limit",
        page_start_params=["page", "offset"],
        item_start_params="start",
        items_properties=["results", "items"],
        next_properties="next",
        next_headers=["Link", "X-Next"],
    )
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "layout.yaml"
        path.write_text(text, encoding="utf-8")
        assert expected == LayoutConfig.from_yaml(path)
        assert expected == LayoutConfig.from_yaml(path.as_posix())


def test_from_yaml_empty():
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "layout.yaml"
        path.write_text("", encoding="utf-8")
        assert LayoutConfig() == LayoutConfig.from_yaml(path)


def test_from_yaml_missing():
    with pytest.raises(FileNotFoundError):
        LayoutConfig.from_yaml("/no/such/layout.yaml")
