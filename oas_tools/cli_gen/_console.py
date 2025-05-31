import os

from rich.console import Console


def console_factory(*args, **kwargs) -> Console:  # pragma: no cover
    """Utility to consolidate creation/initialization of Console.

    A little hacky here... Allow terminal width to be set directly by an environment variable, or
    when detecting that we're testing use a wide terminal to avoid line wrap issues.
    """
    width = kwargs.pop("width", None)
    width_env = os.environ.get("TERMINAL_WIDTH")
    pytest_version = os.environ.get("PYTEST_VERSION")
    if width is not None:
        pass
    elif width_env is not None:
        width = int(width_env)
    elif pytest_version is not None:
        width = 100
    return Console(*args, width=width, **kwargs)


