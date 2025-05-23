import dataclasses
from enum import Enum
from typing import Any
from typing import Optional


class LayoutField(str, Enum):
    NAME = "name"
    BUG_IDS = "bugIds"
    DESCRIPTION = "description"
    OP_ID = "operationId"
    OPERATIONS = "operations"
    SUB_ID = "subcommandId"
    SUMMARY_FIELDS = "summaryFields"
    PAGINATION = "pagination"


class PaginationField(str, Enum):
    ITEM_PROP = "itemProperty"
    ITEM_START = "itemStart"
    NEXT_HEADER = "nextHeader"
    NEXT_PROP = "nextProperty"
    PAGE_SIZE = "pageSize"
    PAGE_START = "pageStart"

    @classmethod
    def contains(cls, value: str) -> bool:
        """This is a fix because `x in PaginationField` is not supported in Python 3.9."""
        try:
            cls(value)
            return True
        except ValueError:
            return False


@dataclasses.dataclass
class PaginationNames:
    # page_size - dictates the limit per request
    page_size: Optional[str] = None

    # page_start - dictates the starting point when it is in page increments
    page_start: Optional[str] = None

    # offset_start - dictates the starting point when it is specified in item increments
    item_start: Optional[str] = None

    # items property specifies the property name to pull out the data from
    items_property: Optional[str] = None

    # locations for next url
    next_header: Optional[str] = None
    next_property: Optional[str] = None


@dataclasses.dataclass
class LayoutNode:
    command: str
    identifier: str
    description: str = ""
    bugs: list[str] = dataclasses.field(default_factory=list)
    summary_fields: list[str] = dataclasses.field(default_factory=list)
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    children: list["LayoutNode"] = dataclasses.field(default_factory=list)
    pagination: Optional[PaginationNames] = None

    def as_dict(self, sparse: bool = True) -> dict[str, Any]:
        """Convenience method to convert to dictionary"""
        def filter_empty_or_none(d: list[tuple[str, Any]]) -> dict[str, Any]:
            """Skips keys whose value is None, or an empty list/dict/set"""
            return {k: v for (k, v) in d if v is not None and v != [] and v != {}}

        return dataclasses.asdict(self, dict_factory=filter_empty_or_none if sparse else None)

    def subcommands(self, include_bugged: bool = False) -> list["LayoutNode"]:
        """Return a list of LayoutNodes that have children."""
        return [n for n in self.children if n.children and (include_bugged or not n.bugs)]

    def operations(self, include_bugged: bool = False) -> list["LayoutNode"]:
        """Return a list of LayoutNodes without any children."""
        return [n for n in self.children if not n.children and (include_bugged or not n.bugs)]

    def find(self, *args) -> Optional["LayoutNode"]:
        """Search for the provided commands"""
        for child in self.children:
            if child.command == args[0]:
                if len(args) == 1:
                    return child
                return child.find(*args[1:])

        return None
