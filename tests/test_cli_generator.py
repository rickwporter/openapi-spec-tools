from datetime import datetime
from datetime import timezone

import pytest

from oas_tools.cli_gen.generator import Generator
from oas_tools.cli_gen.layout import file_to_tree
from oas_tools.utils import open_oas
from tests.helpers import asset_filename

SUM = "summary"
DESC = "description"


def test_shebang():
    uut = Generator("cli_package", {})
    text = uut.shebang()
    assert text.startswith("#!/")
    assert "python3" in text


def test_copyright():
    uut = Generator("cli_package", {})
    year = datetime.now(timezone.utc).year
    text = uut.copyright()
    assert "Copyright" in text
    assert str(year) in text


def test_standard_imports():
    uut = Generator("cli_package", {})
    text = uut.standard_imports()
    assert "import typer" in text
    assert "from typing_extensions import Annotated" in text


def test_subcommand_imports():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = Generator("cli_package", oas)
    text = uut.subcommand_imports(tree.subcommands())
    for name in ["pets", "owners", "veterinarians"]:
        line = f"from cli_package.{name} import app as {name}"
        assert line in text


def test_app_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    uut = Generator("cli_package", oas)
    text = uut.app_definition(tree)
    assert 'app = typer.Typer(no_args_is_help=True, help="Pet management application")' in text
    for name, command in {
        "pets": "pet",
        "owners": "owners",
        "veterinarians": "vets",
    }.items():
        # NOTE: this is not universal, but works here
        line = f'app.add_typer({name}, name="{command}")'
        assert line in text


@pytest.mark.parametrize(
    ["op", "expected"],
    [
        pytest.param({}, "", id="empty"),
        pytest.param({SUM: "Short summary"}, "Short summary", id="summary-only"),
        pytest.param({SUM: "Short summary", DESC: "Short description"}, "Short summary", id="summary-preferred"),
        pytest.param({SUM: "Summary does NOT. Get truncated."}, "Summary does NOT. Get truncated.", id="long-summary"),
        pytest.param({DESC: "Short"}, "Short", id="short-desc"),
        pytest.param({DESC: "First.sentence ends. here"}, "First.sentence ends", id="desc-sentence"),
    ]
)
def test_op_short_help(op, expected):
    uut = Generator("foo", {})
    assert expected == uut.op_short_help(op)


@pytest.mark.parametrize(
    ["op", "expected"],
    [
        pytest.param({}, "", id="empty"),
        pytest.param({SUM: "Short summary"}, "Short summary", id="summary-only"),
        pytest.param({SUM: "Short summary", DESC: "Short description"}, "Short description", id="desc-preferred"),
        pytest.param({DESC: "Short"}, "Short", id="short-desc"),
        pytest.param({DESC: "First.sentence ends. here"}, "First.sentence ends. here", id="long-desc"),
    ]
)
def test_op_long_help(op, expected):
    uut = Generator("foo", {})
    assert expected == uut.op_long_help(op)


def test_function_definition():
    oas = open_oas(asset_filename("pet2.yaml"))
    tree = file_to_tree(asset_filename("layout_pets2.yaml"))
    item = tree.find("pet", "create")
    uut = Generator("cli_package", oas)
    text = uut.function_definition(item)
    assert '@app.command("create", help="Create a pet")' in text
    assert 'def create_pets(' in text
    assert '# handler for createPets: POST /pets' in text


def test_main():
    uut = Generator("cli_package", {})
    text = uut.main()
    assert 'if __name__ == "__main__":' in text
    assert "app()" in text
