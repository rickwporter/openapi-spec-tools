from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import pytest

from openapi_spec_tools.cli_gen._tree import TreeDisplay
from openapi_spec_tools.cli_gen._tree import TreeNode
from openapi_spec_tools.cli_gen._tree import tree
from tests.cli_gen.helpers import to_ascii


def test_tree_node_get():
    node = TreeNode(
        name="myName",
        help="not helpful",
        operation="pysops",
        function="disfunction",
        method="madness",
        path="narrow",
    )
    assert "myName" == node.name
    assert [] == node.children

    assert "not helpful" == node.get(TreeDisplay.HELP)
    assert "pysops" == node.get(TreeDisplay.OPERATION)
    assert "disfunction" == node.get(TreeDisplay.FUNCTION)
    assert "MADNESS narrow" == node.get(TreeDisplay.PATH)
    assert node.get(TreeDisplay.ALL) is None


SAMPLE_TREE = """
audit:
  description: View CloudTruth audit data
  name: audit
  operations:
  - function: audit_list
    help: A searchable log of all the actions taken by users and service accounts
      within the organization.
    method: GET
    name: list
    operationId: audit_list
    path: /api/v1/audit/
  - function: audit_retrieve
    help: Retrieve one record from the audit log.
    method: GET
    name: show
    operationId: audit_retrieve
    path: /api/v1/audit/{id}/
environments:
  description: Manage CloudTruth environments
  name: environment
  operations:
  - function: environments_create
    help: ''
    method: POST
    name: create
    operationId: environments_create
    path: /api/v1/environments/
  - function: environments_destroy
    help: ''
    method: DELETE
    name: delete
    operationId: environments_destroy
    path: /api/v1/environments/{id}/
  - name: tags
    subcommandId: environments_tags
environments_tags:
  description: Manage environment tags
  name: tags
  operations:
  - function: environments_tags_create
    help: Tags allow you to name stable points for your configuration.
    method: POST
    name: create
    operationId: environments_tags_create
    path: /api/v1/environments/{environment_pk}/tags/
main:
  description: Manage CloudTruth application
  name: main
  operations:
  - function: backup_snapshot_create
    help: Get a snapshot of all Projects with parameters
    method: POST
    name: backup
    operationId: backup_snapshot_create
    path: /api/v1/backup/snapshot/
  - function: utils_generate_password_create
    help: Get a randomly generated password using AWS Secrets Manager, with fallback
      to /dev/urandom.
    method: POST
    name: generate-password
    operationId: utils_generate_password_create
    path: /api/v1/utils/generate_password/
  - name: audit
    subcommandId: audit
  - name: environment
    subcommandId: environments
"""

FULL_DISPLAY = """\
╭─ Command Tree ───────────────────────────────────────────────────────────────────────────────────╮
│ backup             help       Get a snapshot of all Projects with parameters                     │
│                    operation  backup_snapshot_create                                             │
│                    path       POST   /api/v1/backup/snapshot/                                    │
│                    function   backup_snapshot_create                                             │
│ generate-password  help  Get a randomly generated password using AWS Secrets Manager, with fallb │
│                    oper  utils_generate_password_create                                          │
│                    path  POST   /api/v1/utils/generate_password/                                 │
│                    func  utils_generate_password_create                                          │
│ audit*             help  View CloudTruth audit data                                              │
│   list             help  A searchable log of all the actions taken by users and service accounts │
│                    oper  audit_list                                                              │
│                    path  GET    /api/v1/audit/                                                   │
│                    func  audit_list                                                              │
│   show             help       Retrieve one record from the audit log.                            │
│                    operation  audit_retrieve                                                     │
│                    path       GET    /api/v1/audit/{id}/                                         │
│                    function   audit_retrieve                                                     │
│ environment*       help  Manage CloudTruth environments                                          │
│   create           operation  environments_create                                                │
│                    path       POST   /api/v1/environments/                                       │
│                    function   environments_create                                                │
│   delete           operation  environments_destroy                                               │
│                    path       DELETE /api/v1/environments/{id}/                                  │
│                    function   environments_destroy                                               │
│   tags*            help  Manage environment tags                                                 │
│     create         help       Tags allow you to name stable points for your configuration.       │
│                    operation  environments_tags_create                                           │
│                    path       POST   /api/v1/environments/{environment_pk}/tags/                 │
│                    function   environments_tags_create                                           │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
"""
OP_DISPLAY = """\
╭─ Command Tree ───────────────────────────────────────────────────────────────────────────────────╮
│ backup             backup_snapshot_create                                                        │
│ generate-password  utils_generate_password_create                                                │
│ audit*                                                                                           │
│   list             audit_list                                                                    │
│   show             audit_retrieve                                                                │
│ environment*                                                                                     │
│   create           environments_create                                                           │
│   delete           environments_destroy                                                          │
│   tags*                                                                                          │
│     create         environments_tags_create                                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
"""
DEPTH_DISPLAY = """\
╭─ Command Tree ───────────────────────────────────────────────────────────────────────────────────╮
│ backup             backup_snapshot_create                                                        │
│ generate-password  utils_generate_password_create                                                │
│ audit*                                                                                           │
│   list             audit_list                                                                    │
│   show             audit_retrieve                                                                │
│ environment*                                                                                     │
│   create           environments_create                                                           │
│   delete           environments_destroy                                                          │
│   tags*                                                                                          │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
"""
SUB_DISPLAY = """\
╭─ Command Tree ───────────────────────────────────────────────────────────────────────────────────╮
│ create  Tags allow you to name stable points for your configuration.                             │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
"""


@pytest.mark.parametrize(
    ["start", "display", "depth", "expected"],
    [
        pytest.param("main", TreeDisplay.ALL, 10, FULL_DISPLAY, id="full"),
        pytest.param("main", TreeDisplay.OPERATION, 10, OP_DISPLAY, id="operation"),
        pytest.param("main", TreeDisplay.OPERATION, 1, DEPTH_DISPLAY, id="depth"),
        pytest.param("environments_tags", TreeDisplay.HELP, 10, SUB_DISPLAY, id="sub"),
    ]
)
def test_show_tree(start, display, depth, expected):
    directory = TemporaryDirectory()
    file = Path(directory.name, "sample.yaml")
    data = SAMPLE_TREE.encode(encoding="utf-8")
    file.write_bytes(data=data)

    with (
        mock.patch('sys.stdout', new_callable=StringIO) as mock_stdout,
    ):
        tree(file.as_posix(), identifier=start, display=display, max_depth=depth)

        result = mock_stdout.getvalue().replace("\r", "")
        assert to_ascii(expected) == to_ascii(result)
