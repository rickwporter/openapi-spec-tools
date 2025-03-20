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

@dataclasses.dataclass
class CommandNode:
    name: str
    description: str = ""
    operation_id: Optional[str] = None
    bugs: list[str] = dataclasses.field(default_factory=list)
    summary_fields: list[str] = dataclasses.field(default_factory=list)
    extra: dict[str, Any] = dataclasses.field(default_factory=dict)
    children: list["CommandNode"] = dataclasses.field(default_factory=list)


