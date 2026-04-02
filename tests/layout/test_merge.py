import pytest

from openapi_spec_tools.layout.merge import merge
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



@pytest.mark.parametrize(
    ["original", "updates", "expected"],
    [
        pytest.param(A, B, B, id="add"),
        pytest.param(B, A, A, id="subtract"),
        pytest.param(C, B, B, id="add-sub"),
        pytest.param(D, E, E, id="nested"),
        pytest.param(F, G, H, id="props")
    ]
)
def test_merge(original: LayoutNode, updates: LayoutNode, expected: LayoutNode) -> None:
    result = merge(original, updates)
    # NOTE: using dicts for easier comparison
    assert expected.as_dict() == result.as_dict()
