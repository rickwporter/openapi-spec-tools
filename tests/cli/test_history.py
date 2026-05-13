import json
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Any
from typing import Optional
from unittest import mock

import pytest
import typer

from openapi_spec_tools.cli.history import _find_commits
from openapi_spec_tools.cli.history import _read_data
from openapi_spec_tools.cli.history import commit_changes
from openapi_spec_tools.cli.history import commit_diff
from openapi_spec_tools.cli.history import commit_history
from openapi_spec_tools.cli.history import commit_show
from tests.cli_gen.helpers import to_ascii
from tests.helpers import StringIo
from tests.helpers import asset_filename

# NOTE: dates are specified to avoid needing test updates in the future
START = datetime(2025, 1, 1, tzinfo=timezone.utc)
END = datetime(2026, 3, 1, tzinfo=timezone.utc)
FILE_ERROR = "ERROR: Unable to find file\n"


@pytest.mark.parametrize(
    ["asset_name", "start", "end", "author", "max_count", "expected"],
    [
        pytest.param("pet.yaml", None, None, None, None, {'46370d4'}, id="single"),
        pytest.param("pet.yaml", START, END, None, None, {'46370d4'}, id="in-range"),
        pytest.param("pet.yaml", END, None, None, None, set(), id="too-early"),
        pytest.param("pet.yaml", None, START, None, None, set(), id="too-late"),
        pytest.param("pet.yaml", None, None, "RicK PorTer", None, {'46370d4'}, id="author-name"),
        pytest.param("pet.yaml", None, None, "rickwporter", None, {'46370d4'}, id="author-email"),
        pytest.param("pet.yaml", None, None, "rickXporter", None, set(), id="author-not-found"),
        pytest.param("pet2.yaml", None, None, None, None, {'502a33f', 'b8121dd', '65d346f'}, id="several"),
        pytest.param("pet2.yaml", None, None, None, 10, {'502a33f', 'b8121dd', '65d346f'}, id="max-ten"),
        pytest.param("pet2.yaml", None, None, None, 2, {'502a33f', 'b8121dd'}, id="max-two"),
    ]
)
def test_find_commits(
    asset_name: str,
    start: Optional[datetime],
    end: Optional[datetime],
    author: Optional[str],
    max_count: Optional[int],
    expected: set[str],
) -> None:
    commits = _find_commits(asset_filename(asset_name), start=start, end=end, author=author, max_count=max_count)
    ids = {_.hexsha[:7] for _ in commits}
    assert ids == expected


def test_read_data() -> None:
    # no diffs to test reading, so just directly using a JSON file
    json_file = asset_filename("pet2.json")
    commits = _find_commits(json_file)
    commit_data = _read_data(commits[0], json_file)
    file_data = json.load(Path(json_file).open())
    assert commit_data == file_data


PETS2_HISTORY_TABLE = """\
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Date       ┃ Commit  ┃ Properties                                   ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2025-04-12 │ 502a33f │  author   Rick Porter                        │
│            │         │  message  Add exception handling             │
├────────────┼─────────┼──────────────────────────────────────────────┤
│ 2025-04-12 │ b8121dd │  author   Rick Porter                        │
│            │         │  message  Add min/max support for int/float  │
├────────────┼─────────┼──────────────────────────────────────────────┤
│ 2025-02-02 │ 65d346f │  author   Rick Porter                        │
│            │         │  message  Another test asset                 │
└────────────┴─────────┴──────────────────────────────────────────────┘
"""
PETS2_HISTORY_YAML = """\
- author: Rick Porter
  commit: 502a33f
  date: '2025-04-12'
  message: Add exception handling
- author: Rick Porter
  commit: b8121dd
  date: '2025-04-12'
  message: Add min/max support for int/float
- author: Rick Porter
  commit: 65d346f
  date: '2025-02-02'
  message: Another test asset

"""
PETS2_HISTORY_JSON = """\
[
  {
    "date": "2025-04-12",
    "commit": "502a33f",
    "author": "Rick Porter",
    "message": "Add exception handling"
  },
  {
    "date": "2025-04-12",
    "commit": "b8121dd",
    "author": "Rick Porter",
    "message": "Add min/max support for int/float"
  },
  {
    "date": "2025-02-02",
    "commit": "65d346f",
    "author": "Rick Porter",
    "message": "Another test asset"
  }
]
"""
NO_COMMITS = """\
No commits found.
"""
@pytest.mark.parametrize(
    ["args", "expected"],
    [
        pytest.param(
            {"oas_file": asset_filename("pet2.yaml"), "start": START, "end": END, "out_fmt": "table"},
            PETS2_HISTORY_TABLE,
            id="table",
        ),
        pytest.param(
            {"oas_file": asset_filename("pet2.yaml"), "start": START, "end": END, "out_fmt": "yaml"},
            PETS2_HISTORY_YAML,
            id="yaml",
        ),
        pytest.param(
            {"oas_file": asset_filename("pet2.yaml"), "start": START, "end": END, "out_fmt": "json"},
            PETS2_HISTORY_JSON,
            id="json",
        ),
        pytest.param(
            {"oas_file": asset_filename("pet2.yaml"), "author": "john"},
            NO_COMMITS,
            id="no-author",
        ),
    ]
)
def test_commit_history_success(args: dict[str, Any], expected: str) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        commit_history(**args)

    result = mock_stdout.getvalue()
    assert to_ascii(result) == to_ascii(expected)


def test_commit_history_failure() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as context,
    ):
        commit_history(asset_filename("foo.yaml"))

    ex = context.value
    assert ex.exit_code == 1
    assert FILE_ERROR == mock_stdout.getvalue()


PETS2_CHANGES_TABLE = """\
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Date       ┃ Commit  ┃ Changes                    ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2025-04-12 │ 502a33f │ paths:                     │
│            │         │   /pets:                   │
│            │         │     get:                   │
│            │         │       parameters[0]:       │
│            │         │         schema:            │
│            │         │           minimum: removed │
├────────────┼─────────┼────────────────────────────┤
│ 2025-04-12 │ b8121dd │ paths:                     │
│            │         │   /pets:                   │
│            │         │     get:                   │
│            │         │       parameters[0]:       │
│            │         │         schema:            │
│            │         │           minimum: added   │
└────────────┴─────────┴────────────────────────────┘
"""
PETS2_CHANGES_YAML = """\
- changes:
    paths:
      /pets:
        get:
          parameters[0]:
            schema:
              minimum: removed
  commit: 502a33f
  date: '2025-04-12'
- changes:
    paths:
      /pets:
        get:
          parameters[0]:
            schema:
              minimum: added
  commit: b8121dd
  date: '2025-04-12'

"""
PETS2_CHANGES_JSON = """\
[
  {
    "date": "2025-04-12",
    "commit": "502a33f",
    "changes": {
      "paths": {
        "/pets": {
          "get": {
            "parameters[0]": {
              "schema": {
                "minimum": "removed"
              }
            }
          }
        }
      }
    }
  },
  {
    "date": "2025-04-12",
    "commit": "b8121dd",
    "changes": {
      "paths": {
        "/pets": {
          "get": {
            "parameters[0]": {
              "schema": {
                "minimum": "added"
              }
            }
          }
        }
      }
    }
  }
]
"""
NO_DIFFS = """\
No differences found with those parameters.
"""
MISC_YAML_CHANGES = """\
- changes:
    paths:
      /pets/{numFeet}/{species}/{neutered}/{birthday}:
        get:
          parameters: 'different lengths: 17 != 18'
  commit: 31676f5
  date: '2025-07-08'

"""
@pytest.mark.parametrize(
    ["args", "expected"],
    [
        pytest.param(
            {
                "oas_file": asset_filename("pet2.yaml"),
                "start": START,
                "end": END,
                "out_fmt": "table",
            },
            PETS2_CHANGES_TABLE,
            id="table",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("pet2.yaml"),
                "start": START,
                "end": END,
                "out_fmt": "yaml"
            },
            PETS2_CHANGES_YAML,
            id="yaml",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("pet2.yaml"),
                "start": START,
                "end": END,
                "out_fmt": "json",
            },
            PETS2_CHANGES_JSON,
            id="json",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("pet2.yaml"),
                "author": "fred",
                "start": START,
                "end": END,
                "out_fmt": "json",
            },
            NO_DIFFS,
            id="no-author",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("misc.yaml"),
                "start": datetime(2025, 7, 14, tzinfo=timezone.utc),
                "end": datetime(2025, 7, 10),
                "out_fmt": "yaml"
            },
            MISC_YAML_CHANGES,
            id="late-start",
        ),
    ]
)
def test_commit_changes_success(args: dict[str, Any], expected: str) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        commit_changes(**args)

    result = mock_stdout.getvalue()
    assert to_ascii(result) == to_ascii(expected)


def test_commit_changes_failure() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as context,
    ):
        commit_changes(asset_filename("foo.yaml"))

    ex = context.value
    assert ex.exit_code == 1
    assert FILE_ERROR == mock_stdout.getvalue()


MISC_COMMIT_TABLE = """\
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Date       ┃ Commit  ┃ Changes                      ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 2025-06-25 │ 05b302d │ components:                  │
│            │         │   schemas:                   │
│            │         │     PetExt:                  │
│            │         │       allOf[1]:              │
│            │         │         properties:          │
│            │         │           listVarious: added │
└────────────┴─────────┴──────────────────────────────┘
"""
MISC_COMMIT_JSON = """\
[
  {
    "date": "2025-06-25",
    "commit": "05b302d",
    "changes": {
      "components": {
        "schemas": {
          "PetExt": {
            "allOf[1]": {
              "properties": {
                "listVarious": "added"
              }
            }
          }
        }
      }
    }
  }
]
"""
MISC_COMMIT_NOT_FOUND = """\
No matching commit found.
"""
@pytest.mark.parametrize(
      ["args", "expected"],
      [
        pytest.param(
            {
                "oas_file": asset_filename("misc.yaml"),
                "commit": "05b302d",
            },
            MISC_COMMIT_TABLE,
            id="table",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("misc.yaml"),
                "commit": "05b3",
                "out_fmt": "json",
            },
            MISC_COMMIT_JSON,
            id="json",
        ),
        pytest.param(
            {
                "oas_file": asset_filename("misc.yaml"),
                "commit": "05b3abcdef",
            },
            MISC_COMMIT_NOT_FOUND,
            id="not-found",
        ),
      ]
)
def test_commit_show_success(args: dict[str, Any], expected: str) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        commit_show(**args)

    result = mock_stdout.getvalue()
    assert to_ascii(result) == to_ascii(expected)


def test_commit_show_failure() -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
        pytest.raises(typer.Exit) as context,
    ):
        commit_show(asset_filename("foo.yaml"), "deadbeef")

    ex = context.value
    assert ex.exit_code == 1
    assert FILE_ERROR == mock_stdout.getvalue()


HASH_DELTA1 = "dac5b6d..852fb5b"
MISC_DIFF1_TABLE = """\
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Commits          ┃ Changes                     ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ dac5b6d..852fb5b │ components:                 │
│                  │   schemas:                  │
│                  │     Pets:                   │
│                  │       items: removed        │
│                  │       maxItems: removed     │
│                  │       properties: added     │
│                  │       type: array != object │
│                  │     ShapeShifter: added     │
└──────────────────┴─────────────────────────────┘
"""
MISC_DIFF1_JSON = """\
[
  {
    "commits": "dac5b6d..852fb5b",
    "changes": {
      "components": {
        "schemas": {
          "Pets": {
            "items": "removed",
            "maxItems": "removed",
            "properties": "added",
            "type": "array != object"
          },
          "ShapeShifter": "added"
        }
      }
    }
  }
]
"""
MISC_DIFF1_YAML = """\
- changes:
    components:
      schemas:
        Pets:
          items: removed
          maxItems: removed
          properties: added
          type: array != object
        ShapeShifter: added
  commits: dac5b6d..852fb5b
"""
DIFF_NO_CHANGE = """\
Unable to determine differences.
"""
@pytest.mark.parametrize(
    ["args", "expected"],
    [
        pytest.param({"oas_file": asset_filename("misc.yaml"), "hash": HASH_DELTA1}, MISC_DIFF1_TABLE, id="table"),
        pytest.param(
            {"oas_file": asset_filename("misc.yaml"), "hash": HASH_DELTA1, "out_fmt": "json"},
            MISC_DIFF1_JSON,
            id="json",
        ),
        pytest.param({
            "oas_file": asset_filename("misc.yaml"), "hash": HASH_DELTA1, "out_fmt": "yaml"},
            MISC_DIFF1_YAML,
            id="yaml",
        ),
        pytest.param({
            "oas_file": asset_filename("misc.yaml"), "hash": "dac5b6d..dac5b6d"},
            DIFF_NO_CHANGE,
            id="no-change",
        ),
        pytest.param({
            "oas_file": asset_filename("misc.yaml"), "hash": "dac5b6d"},
            MISC_DIFF1_TABLE,
            id="no-end",
        ),
    ]
)
def test_commit_diff_success(args: dict[str, Any], expected: str) -> None:
    with (
        mock.patch('sys.stdout', new_callable=StringIo) as mock_stdout,
    ):
        commit_diff(**args)

    result = mock_stdout.getvalue()
    assert to_ascii(result) == to_ascii(expected)
