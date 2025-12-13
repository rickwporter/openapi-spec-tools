"""Field enums and class definitions for objects used by the layout file."""
from enum import Enum
from typing import Any
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class LayoutField(str, Enum):
    """Field names in the layout file, mostly inside the operations section."""

    NAME = "name"
    BUG_IDS = "bugIds"
    DESCRIPTION = "description"
    HIDDEN_FIELDS = "hiddenFields"
    OP_ID = "operationId"
    OPERATIONS = "operations"
    SUB_ID = "subcommandId"
    SUMMARY_FIELDS = "summaryFields"
    PAGINATION = "pagination"
    ALLOWED_FIELDS = "allowedFields"
    IGNORE = "ignore"
    COLUMNS = "columns"
    REFERENCE = "reference"


class PaginationField(str, Enum):
    """Field names expected in the pagination parameters of the layout."""

    ITEM_PROP = "itemProperty"
    ITEM_START = "itemStart"
    NEXT_HEADER = "nextHeader"
    NEXT_PROP = "nextProperty"
    PAGE_SIZE = "pageSize"
    PAGE_START = "pageStart"

    @classmethod
    def contains(cls, value: str) -> bool:
        """Check wither the value is a class member (aka enum value).

        This is a fix because `x in PaginationField` is not supported in Python 3.9.
        """
        try:
            cls(value)
            return True
        except ValueError:
            return False


class ReferenceField(str, Enum):
    """Field names for reference sub-objects in the layout."""

    PACKAGE = "package"
    APP_NAME = "appName"


class PaginationNames(BaseModel):
    """Data structure for holding info related to pagination parameters."""

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

    def sizeable(self) -> bool:
        """Check if any variables are defined that should lead to allow specifying a size."""
        return any([self.page_size, self.page_start, self.item_start, self.next_header, self.next_property])


class ReferenceSubcommand(BaseModel):
    """Data structure for holding manual parameters."""

    package: str
    app_name: str = "app"


class LayoutNode(BaseModel):
    """Info for handling the layout file in a hierachical fashion."""

    command: str
    identifier: Optional[str]
    description: str = ""
    bugs: list[str] = Field(default_factory=list)
    summary_fields: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)
    children: list["LayoutNode"] = Field(default_factory=list)
    pagination: Optional[PaginationNames] = None
    reference: Optional[ReferenceSubcommand] = None
    hidden_fields: list[str] = Field(default_factory=list)
    allowed_fields: list[str] = Field(default_factory=list)
    display_columns: list[str] = Field(default_factory=list)
    ignore: Optional[bool] = None

    def as_dict(self, sparse: bool = True) -> dict[str, Any]:
        """Convert object to dictionary."""
        return self.model_dump(exclude_none=sparse, exclude_unset=sparse, exclude_defaults=sparse)

    def skip_generation(self) -> bool:
        """Whether to skip code generation for this node."""
        if self.bugs or self.ignore:
            return True

        if not self.children:
            return False

        return all(c.skip_generation() for c in self.children)

    def subcommands(self, include_all: bool = False) -> list["LayoutNode"]:
        """List of LayoutNodes that have children."""
        return [
            n for n in self.children
            if n.children and not n.reference and (include_all or not n.skip_generation())
        ]

    def operations(self, include_all: bool = False) -> list["LayoutNode"]:
        """List of LayoutNodes without any children."""
        return [
            n for n in self.children
            if not n.children and not n.reference and (include_all or not n.skip_generation())
        ]

    def references(self, include_all: bool = False) -> list["LayoutNode"]:
        """List of LayoutNodes with manual configuration."""
        return [
            n for n in self.children
            if n.reference and (include_all or not n.skip_generation())
        ]

    def find(self, *args) -> Optional["LayoutNode"]:
        """Search for the provided commands."""
        if not args:
            return None

        for child in self.children:
            if child.command == args[0]:
                if len(args) == 1:
                    return child
                return child.find(*args[1:])

        return None
