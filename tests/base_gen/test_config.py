from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.base_gen.config import GeneratorConfig
from openapi_spec_tools.types import ContentType

PKG = "some_package"


def test_from_config_defaults():
    uut = GeneratorConfig(package_name=PKG)

    assert PKG == uut.package_name
    assert uut.default_host is None
    assert uut.supported_content is None
    assert uut.max_help_length is None
    assert uut.reserved is None
    assert uut.conflict_suffix is None
    assert uut.copyright is None
    assert uut.infra_files is None
    assert uut.infra_replacements is None
    assert uut.test_files is None
    assert uut.test_replacements is None
    assert uut.env_host is None
    assert uut.env_key is None
    assert uut.env_timeout is None
    assert uut.env_log_level is None
    assert uut.default_log_level is None
    assert uut.default_timeout is None


def test_from_config_overrides():
    copyright = "# custom copyright\n"
    reserved = {"custom"}
    supported = [ContentType.APP_JSON, ContentType.APP_XML]
    infra_files = {"src.py": "dst.py"}
    test_files = {"test_src.py": "test_dst.py"}

    uut = GeneratorConfig(
        package_name="pets",
        supported_content=supported,
        max_help_length=40,
        reserved=reserved,
        conflict_suffix="x",
        copyright=copyright,
        infra_files=infra_files,
        infra_replacements={"a": "b"},
        test_files=test_files,
        test_replacements={"c": "d"},
        env_host=["HOST_A", "HOST_B"],
        env_key="MY_KEY",
        env_timeout=["TIME_A"],
        env_log_level="MY_LOG",
        default_host="https://override.test",
        default_log_level="debug",
        default_timeout=9,
    )

    assert "pets" == uut.package_name
    assert "https://override.test" == uut.default_host
    assert supported == uut.supported_content
    assert 40 == uut.max_help_length
    assert reserved == uut.reserved
    assert "x" == uut.conflict_suffix
    assert copyright == uut.copyright
    assert {"src.py": "dst.py"} == uut.infra_files
    assert {"a": "b"} == uut.infra_replacements
    assert {"test_src.py": "test_dst.py"} == uut.test_files
    assert {"c": "d"} == uut.test_replacements
    assert ["HOST_A", "HOST_B"] == uut.env_host
    assert "MY_KEY" == uut.env_key
    assert ["TIME_A"] == uut.env_timeout
    assert "MY_LOG" == uut.env_log_level
    assert "debug" == uut.default_log_level
    assert 9 == uut.default_timeout


def test_from_yaml_defaults():
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "generator.yaml"
        path.write_text("package_name: pets\n", encoding="utf-8")
        config = GeneratorConfig.from_yaml(path)

    assert GeneratorConfig(package_name="pets") == config


def test_from_yaml():
    text = """\
package_name: pets
supported_content:
  - application/json
  - application/xml
max_help_length: 40
reserved:
  - custom
conflict_suffix: x
copyright: |
  # custom copyright
infra_files:
  src.py: dst.py
infra_replacements:
  a: b
test_files:
  test_src.py: test_dst.py
test_replacements:
  c: d
env_host:
  - HOST_A
  - HOST_B
env_key: MY_KEY
env_timeout:
  - TIME_A
env_log_level: MY_LOG
default_host: https://override.test
default_log_level: debug
default_timeout: 9
"""
    expected = GeneratorConfig(
        package_name="pets",
        supported_content=[ContentType.APP_JSON, ContentType.APP_XML],
        max_help_length=40,
        reserved={"custom"},
        conflict_suffix="x",
        copyright="# custom copyright\n",
        infra_files={"src.py": "dst.py"},
        infra_replacements={"a": "b"},
        test_files={"test_src.py": "test_dst.py"},
        test_replacements={"c": "d"},
        env_host=["HOST_A", "HOST_B"],
        env_key="MY_KEY",
        env_timeout=["TIME_A"],
        env_log_level="MY_LOG",
        default_host="https://override.test",
        default_log_level="debug",
        default_timeout=9,
    )
    with TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "generator.yaml"
        path.write_text(text, encoding="utf-8")
        assert expected == GeneratorConfig.from_yaml(path)
        assert expected == GeneratorConfig.from_yaml(path.as_posix())


def test_from_yaml_missing():
    with pytest.raises(FileNotFoundError):
        GeneratorConfig.from_yaml("/no/such/generator.yaml")


def test_resolve_path_keys():
    uut = GeneratorConfig(package_name=PKG)

    assert {} == uut.resolve_path_keys(None)
    assert {} == uut.resolve_path_keys({})

    foo = "/tmp/foo.py"
    requests = "openapi_spec_tools/base_gen/_requests.py"
    data = {
        foo: "foo.py",
        requests: "requests.py",
    }
    spec_tools = Path(__file__).parent.parent.parent / "openapi_spec_tools"
    expected = {
        Path(foo): "foo.py",
        spec_tools / "base_gen" / "_requests.py": "requests.py"
    }
    assert expected == uut.resolve_path_keys(data)
