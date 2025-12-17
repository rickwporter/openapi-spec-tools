"""Implementation for displaying data in a user-friendly fashion."""
from typing import Any


def allowed(obj: Any, properties: list[str]) -> Any:
    """Get the item with just the specified properties."""
    if obj is None:
        return None

    if isinstance(obj, list):
        # recursively call for each object in list
        return [allowed(item, properties) for item in obj]

    return {prop: obj.get(prop) for prop in properties}


def remove(obj: Any, properties: list[str]) -> Any:
    """Remove the specified properties from the specified object."""
    if obj is None:
        return None

    if isinstance(obj, list):
        # recursively call for each item in the list
        return [remove(item, properties) for item in obj]

    for pname in properties:
        # remove all the properties
        obj.pop(pname, None)

    return obj
