"""Telegram limits of a rich message, checked before sending."""
from typing import List

from .entities import RichBlock

MAX_TEXT_LENGTH = 32768
MAX_BLOCKS = 500
MAX_DEPTH = 16
MAX_TABLE_COLUMNS = 20


def _count(blocks: List[RichBlock], depth: int) -> int:
    """Number of blocks with nested ones, checks depth and table width."""
    if depth > MAX_DEPTH:
        raise ValueError(
            f"Rich message is nested deeper than {MAX_DEPTH} levels",
        )
    total = 0
    for block in blocks:
        total += block.own_count()
        for width in block.row_widths():
            if width > MAX_TABLE_COLUMNS:
                raise ValueError(
                    f"Table has more than {MAX_TABLE_COLUMNS} columns",
                )
        for levels, nested in block.nested():
            total += _count(nested, depth + levels)
    return total


def check_limits(blocks: List[RichBlock]) -> None:
    """Raise ValueError if blocks exceed Telegram rich message limits."""
    count = _count(blocks, 1)
    if count > MAX_BLOCKS:
        raise ValueError(
            f"Rich message has {count} blocks, the limit is {MAX_BLOCKS}",
        )
    length = sum(block.text_length() for block in blocks)
    if length > MAX_TEXT_LENGTH:
        raise ValueError(
            f"Rich message text has {length} characters, "
            f"the limit is {MAX_TEXT_LENGTH}",
        )
