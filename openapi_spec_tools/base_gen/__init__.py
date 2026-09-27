"""Base generator which is the base class for API and CLI generoators."""
from .base_generator import BaseGenerator
from .utils import is_case_sensitive
from .utils import maybe_quoted
from .utils import prepend
from .utils import quoted
from .utils import replace_special
from .utils import set_missing
from .utils import shallow
from .utils import simple_escape
from .utils import to_camel_case
from .utils import to_snake_case
