import re
from typing import Any, Optional

from sulguk.data import LANG_CLASS_PREFIX  # noqa: F401

ZERO_WIDTH_SPACE = "​"
# carriage return, line feed, tab and space (not nbsp)
SPACES = re.compile("[\x0d\x0a\x09\x20]+")
# the same symbols for str.strip
HTML_SPACES = "\x0d\x0a\x09\x20"
# inputs which are pressed, they become buttons
BUTTON_INPUT_TYPES = frozenset({"submit", "button", "reset"})


def collapse_spaces(text: str) -> str:
    """Every run of HTML spaces is one space, as in a browser."""
    return SPACES.sub(" ", text)


def to_int(value: Optional[str]) -> Optional[int]:
    """Number from an attribute, ``None`` if the attribute is not set."""
    return int(value) if value else None


def compact(**fields: Any) -> dict[str, Any]:
    """Dict of the fields which are set (not None)."""
    return {key: value for key, value in fields.items() if value is not None}
