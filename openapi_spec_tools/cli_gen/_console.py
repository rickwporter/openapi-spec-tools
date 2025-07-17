import os

from rich.console import Console

TEST_TERMINAL_WIDTH = 100


def console_factory(*args, **kwargs) -> Console:
    """Create/initialize a Console object.

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
        width = TEST_TERMINAL_WIDTH
    return Console(*args, width=width, **kwargs)
