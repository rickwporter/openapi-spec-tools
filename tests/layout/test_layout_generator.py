from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from openapi_spec_tools.layout.layout_generator import LayoutGenerator
from openapi_spec_tools.layout.utils import write_layout
from openapi_spec_tools.types import OasField
from openapi_spec_tools.utils import map_operations
from openapi_spec_tools.utils import open_oas
from tests.helpers import asset_filename

NAME = "name"
OP_ID = "operationId"
X_METH = "x-method"


@pytest.mark.parametrize(
    ["path", "prefix", "expected"],
    [
        pytest.param("", "", [], id="empty"),
        pytest.param("/foo", "/foo", [], id="only-prefix"),
        pytest.param("/foo", "/foo/foo", ["foo"], id="single-prefix"),
        pytest.param("/foo/{bar}", "/foo", [], id="prefix-id"),
        pytest.param("/sna/foo/{bar}", "/foo", ["sna", "foo"], id="late-prefix"),
        pytest.param("/sna/foo/{bar}/all", "/sna", ["foo", "all"], id="all"),
    ],
)
def test_path_to_parts(path, prefix, expected):
    uut = LayoutGenerator({})
    assert expected == uut.path_to_parts(path, prefix)


@pytest.mark.parametrize(
    ["parts", "expected"],
    [
        pytest.param([], [], id="empty"),
        pytest.param(["foo"], ["foo"], id="simple"),
        pytest.param(["Foo"], ["foo"], id="title"),
        pytest.param(["FooBar"], ["foo-bar"], id="camel"),
        pytest.param(["foo_bar"], ["foo-bar"], id="snake"),
    ]
)
def test_parts_to_commands(parts, expected):
    uut = LayoutGenerator({})
    assert expected == uut.parts_to_commands(parts)


@pytest.mark.parametrize(
    ["commands", "expected"],
    [
        pytest.param([], "", id="empty"),
        pytest.param(["foo"], "foo", id="simple"),
        pytest.param(["sna", "foo"], "sna_foo", id="multiple"),
        pytest.param(["sna", "fooBar"], "sna_foo_bar", id="camel"),
        pytest.param(["sna_foo", "bar"], "sna_foo_bar", id="snake"),
    ]
)
def test_commands_to_identifier(commands, expected):
    uut = LayoutGenerator({})
    assert expected == uut.commands_to_identifier(commands)


@pytest.mark.parametrize(
    ["name", "expected"],
    [
        pytest.param("my-name", {NAME: "my-name", "something": "else"}, id="found"),
        pytest.param("your-name", None, id="not-found")
    ],
)
def test_find_parameter(name, expected):
    parameters = [
        {NAME: "other", "value": None},
        {NAME: "my-name", "something": "else"},
    ]
    uut = LayoutGenerator({})
    assert expected == uut.find_parameter(parameters, name)


@pytest.mark.parametrize(
    ["reference", "found"],
    [
        pytest.param("#/components/schemas/Pet", True, id="found"),
        pytest.param("#/components/", False, id="no-keys"),
        pytest.param("#/components/schemas/Animal", False, id="not-found"),
    ]
)
def test_get_model(reference, found):
    oas = open_oas(asset_filename("pet.yaml"))
    uut = LayoutGenerator(oas)

    item = uut.get_model(reference)
    assert found == (item is not None)


ANIMAL = {'type': 'object', 'properties': {'species': {'type': 'string'}}}
PET = {'type': 'object', 'properties': {'id': {'type': 'integer'}, 'name': {'type': 'string'}}}

@pytest.mark.parametrize(
    ["op_id", "expected"],
    [
        pytest.param("getSomething", None, id="no-success"),
        pytest.param("deleteSomething", None, id="no-content"),
        pytest.param("putSomething", None, id="unsupported"),
        pytest.param("postSomething", PET, id="yaml"),
        pytest.param("deleteSomethingElse", PET, id="json"),
        pytest.param("getSomethingElse", ANIMAL, id="no-ref"),
    ]
)
def test_get_response_body(op_id, expected):
    oas = open_oas(asset_filename("misc2.yaml"))
    uut = LayoutGenerator(oas)

    operations = map_operations(oas.get(OasField.PATHS, {}))
    op = operations.get(op_id)
    actual = uut.get_response_body(op)
    assert expected == actual


@pytest.mark.parametrize(
    ["op_data", "expected"],
    [
        pytest.param({X_METH: "PUT", OP_ID: "foo_list"}, "set", id="put"),
        pytest.param({X_METH: "PaTCh", OP_ID: "foo_list"}, "update", id="update"),
        pytest.param({X_METH: "delete", OP_ID: "add_item"}, "create", id="begin"),
        pytest.param({X_METH: "delete", OP_ID: "itemRetrieve"}, "show", id="end"),
        pytest.param({X_METH: "delete", OP_ID: "item"}, "delete", id="method"),
    ]
)
def test_suggest_command(op_data, expected):
    uut = LayoutGenerator({})
    assert expected == uut.suggest_command(op_data)


def test_generate_pets():
    oas = open_oas(asset_filename("pet.yaml"))

    uut = LayoutGenerator(oas)
    node = uut.generate("/pets")
    assert [] == node.subcommands()
    ops = node.operations()
    assert 3 == len(ops)
    assert {"list", "create", "show"} == {o.command for o in ops}
    assert {"listPets", "createPets", "showPetById"} == {o.identifier for o in ops}


def test_generate_cloudtruth():
    oas = open_oas(asset_filename("ct.yaml"))

    uut = LayoutGenerator(oas)
    node = uut.generate("/api/v1")

    assert 'CloudTruth centralizes your configuration parameters' in node.description

    # no direct operations -- all in sub-commands
    assert [] == node.operations()

    subcmds = node.subcommands()
    assert 17 == len(subcmds)

    # a couple spot checks
    current_user = node.find("users", "current")
    assert [] == current_user.subcommands()
    sub_ops = current_user.operations()
    assert 1 == len(sub_ops)
    item = sub_ops[0]
    assert "show" == item.command
    assert "users_current_retrieve" == item.identifier

    key_list = node.find("integrations", "azure", "key-vault", "list")
    assert "list" == key_list.command
    assert "integrations_azure_key_vault_list" == key_list.identifier


def test_generate_misc():
    oas = open_oas(asset_filename("misc.yaml"))

    uut = LayoutGenerator(oas)
    node = uut.generate("", description="this is it")

    assert node.description == "this is it"
    assert [] == node.operations()

    sub_cmds = node.subcommands()
    assert 2 == len(sub_cmds)

    pets = node.find("pets")
    pet_cmds = pets.operations()
    assert 2 == len(pet_cmds)
    assert {"show", "delete"} == {cmd.command for cmd in pet_cmds}


def test_generate_node_file():
    oas = open_oas(asset_filename("pet.yaml"))
    tempdir = TemporaryDirectory()
    file = Path(tempdir.name) / "layout.yaml"
    generator = LayoutGenerator(oas)
    node = generator.generate("")

    assert "CLI to manage your application" == node.description

    write_layout(file.as_posix(), node)

    text = file.read_text(encoding="utf-8", errors="ignore")
    expected = '''\
main:
    description: CLI to manage your application
    operations:
    - name: pets
      subcommandId: pets

pets:
    description: Manage pets
    operations:
    - name: create
      operationId: createPets
    - name: list
      operationId: listPets
    - name: show
      operationId: showPetById
'''
    assert expected in text
