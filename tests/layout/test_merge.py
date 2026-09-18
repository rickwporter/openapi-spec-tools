import pytest

from openapi_spec_tools.layout.merge import find_peers
from openapi_spec_tools.layout.merge import merge
from openapi_spec_tools.layout.merge import merge_node_properties
from openapi_spec_tools.layout.types import LayoutNode
from openapi_spec_tools.layout.types import PaginationNames

A = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='b', identifier='B'),
    ]
)
B = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='b', identifier='B'),
        LayoutNode(command='c', identifier='C'),
    ]
)
C = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='b', identifier='B'),
        LayoutNode(command='c', identifier='C'),
        LayoutNode(command='d', identifier='D'),
    ]
)
D = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='b', identifier='B', children=[
            LayoutNode(command='x', identifier='X'),
            LayoutNode(command='y', identifier='Y'),
        ]),
    ]
)
E = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='b', identifier='B', children=[LayoutNode(command='x', identifier='X')]),
        LayoutNode(command='c', identifier='C', children=[LayoutNode(command='m', identifier='M')]),
    ]
)
F = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A', bugs=["blackfly", "mosquito"], hidden_fields=["left"]),
        LayoutNode(command='b', identifier='B'),
    ]
)
G = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='c', identifier='C', pagination=PaginationNames(page_size="size")),
    ]
)
H = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A', bugs=["blackfly", "mosquito"], hidden_fields=["left"]),
        LayoutNode(command='c', identifier='C', pagination=PaginationNames(page_size="size")),
    ]
)
J = LayoutNode(
    command='main',
    identifier='main',
    children=[
        LayoutNode(command='a', identifier='A'),
        LayoutNode(command='b', identifier='B'),
        LayoutNode(
            command='c',
            identifier='C',
            children=[
                LayoutNode(command='x', identifier='X'),
                LayoutNode(command='y', identifier='Y'),
                LayoutNode(command='z', identifier='Z'),
            ],
        ),
    ]
)


@pytest.mark.parametrize(
    ["node", "op_id", "expected"],
    [
        pytest.param(A, "foo", [], id="not-found"),
        pytest.param(A, "A", ["B"], id="single"),
        pytest.param(C, "C", ["B", "D"], id="multiple"),
        pytest.param(D, "X", ["Y"], id="nested"),
    ]
)
def test_find_peers(node: LayoutNode, op_id: str, expected: list[str]) -> None:
    assert expected == find_peers(node, op_id)


@pytest.mark.parametrize(
    ["original", "updates", "expected"],
    [
        pytest.param(A, B, B, id="add"),
        pytest.param(B, A, A, id="subtract"),
        pytest.param(C, B, B, id="add-sub"),
        pytest.param(D, E, E, id="nested"),
        pytest.param(F, G, H, id="props"),
        pytest.param(A, J, J, id="multi-children"),
    ]
)
def test_merge(original: LayoutNode, updates: LayoutNode, expected: LayoutNode) -> None:
    result = merge(original, updates)
    # NOTE: using dicts for easier comparison
    assert expected.as_dict() == result.as_dict()


@pytest.mark.parametrize(
    ["props", "src", "dst", "expected"],
    [
        pytest.param(
            [],
            LayoutNode(command='a1', identifier='A', bugs=["b1"]),
            LayoutNode(command='a2', identifier='A'),
            LayoutNode(command='a2', identifier='A'),
            id="no-props",
        ),
        pytest.param(
            ["bugs"],
            LayoutNode(command='a1', identifier='A', bugs=["b1"]),
            LayoutNode(command='a2', identifier='A'),
            LayoutNode(command='a2', identifier='A', bugs=["b1"]),
            id="single-prop",
        ),
        pytest.param(
            ["bugs", "command"],
            LayoutNode(command='a1', identifier='A', bugs=["b1"]),
            LayoutNode(command='a2', identifier='A'),
            LayoutNode(command='a1', identifier='A', bugs=["b1"]),
            id="multi-prop",
        ),
        pytest.param(
            ["sna", "foo", "bar"],
            LayoutNode(command='a1', identifier='A', extra={"sna": "string", "bar": True}),
            LayoutNode(command='a2', identifier='A', extra={"sna": 1, "foo": None}),
            LayoutNode(command='a2', identifier='A', extra={"sna": "string", "foo": None, "bar": True}),
            id="extras",
        ),
        pytest.param(
            ["bugs", "command"],
            LayoutNode(
                command='main1',
                identifier='main',
                bugs=["b2"],
                children=[
                    LayoutNode(command='aa', identifier='A', bugs=["b1"]),
                    LayoutNode(command='bb', identifier='B', children=[
                        LayoutNode(command='yy', identifier='Y', bugs=["b3"]),
                    ]),
                ]
            ),
            LayoutNode(
                command='main2',
                identifier='main',
                children=[
                    LayoutNode(command='a', identifier='A'),
                    LayoutNode(command='b', identifier='B', children=[
                        LayoutNode(command='x', identifier='X'),
                        LayoutNode(command='y', identifier='Y'),
                    ]),
                ]
            ),
            LayoutNode(
                command='main1',
                identifier='main',
                bugs=["b2"],
                children=[
                    LayoutNode(command='aa', identifier='A', bugs=["b1"]),
                    LayoutNode(command='bb', identifier='B', children=[
                        LayoutNode(command='x', identifier='X'),
                        LayoutNode(command='yy', identifier='Y', bugs=["b3"]),
                    ]),
                ]
            ),
            id="children",
        ),
    ]
)
def test_merge_properties(props: list[str], src: LayoutNode, dst: LayoutNode, expected: LayoutNode) -> None:
    assert expected == merge_node_properties(props, src, dst)
