import pytest

from sulguk.rich.entities import (
    Anchor,
    BlockquoteBlock,
    Caption,
    DetailsBlock,
    FormattedText,
    GalleryBlock,
    ListBlock,
    ListItemBlock,
    MathBlock,
    MediaBlock,
    ParagraphBlock,
    RichTextList,
    TableBlock,
    TableCell,
    Text,
)
from sulguk.rich.limits import (
    MAX_BLOCKS,
    MAX_DEPTH,
    MAX_MEDIA,
    MAX_TABLE_COLUMNS,
    MAX_TEXT_LENGTH,
    check_limits,
)


def text(*parts):
    return RichTextList([
        Text(part) if isinstance(part, str) else part for part in parts
    ])


def para(value="x"):
    return ParagraphBlock(text(value))


def quote(*blocks):
    return BlockquoteBlock(list(blocks))


def nested(depth):
    """Quotes inside of quotes, ``depth`` levels of them."""
    block = para()
    for _ in range(depth):
        block = quote(block)
    return block


def table(*row_spans):
    """Table with a row for every item, a cell has the colspan."""
    return TableBlock([
        [TableCell(colspan=span) for span in row] for row in row_spans
    ])


def test_empty():
    check_limits([])


def test_blocks_edge_is_allowed():
    check_limits([para()] * MAX_BLOCKS)


def test_too_many_blocks():
    with pytest.raises(ValueError, match="blocks, the limit is"):
        check_limits([para()] * (MAX_BLOCKS + 1))


def test_nested_blocks_are_counted():
    # a quote and a paragraph in it are two blocks
    check_limits([quote(para())] * (MAX_BLOCKS // 2))
    with pytest.raises(ValueError, match="blocks, the limit is"):
        check_limits([quote(para())] * (MAX_BLOCKS // 2 + 1))


def test_list_items_are_counted():
    items = [ListItemBlock([para()])] * 3
    # list + 3 items + 3 paragraphs
    count = MAX_BLOCKS // 7
    check_limits([ListBlock(items)] * count)
    with pytest.raises(ValueError, match="blocks, the limit is"):
        check_limits([ListBlock(items)] * (count + 1))


def test_table_rows_are_counted():
    # the table and a row of it
    with pytest.raises(ValueError, match="blocks, the limit is"):
        check_limits([table([1])] * (MAX_BLOCKS // 2 + 1))


def test_depth_edge_is_allowed():
    check_limits([nested(MAX_DEPTH - 1)])


def test_too_deep():
    with pytest.raises(ValueError, match="nested deeper"):
        check_limits([nested(MAX_DEPTH)])


def test_list_item_adds_one_more_level():
    block = para()
    for _ in range(MAX_DEPTH // 2):
        block = ListBlock([ListItemBlock([block])])
    with pytest.raises(ValueError, match="nested deeper"):
        check_limits([block])


def test_columns_edge_is_allowed():
    check_limits([table([1] * MAX_TABLE_COLUMNS)])


def test_too_many_columns():
    with pytest.raises(ValueError, match="more than 20 columns"):
        check_limits([table([1] * (MAX_TABLE_COLUMNS + 1))])


def test_colspan_counts_as_columns():
    with pytest.raises(ValueError, match="more than 20 columns"):
        check_limits([table([MAX_TABLE_COLUMNS, 1])])


def test_columns_of_every_row_are_checked():
    with pytest.raises(ValueError, match="more than 20 columns"):
        check_limits([table([1], [MAX_TABLE_COLUMNS + 1])])


def test_length_edge_is_allowed():
    check_limits([para("a" * MAX_TEXT_LENGTH)])


def test_too_long():
    with pytest.raises(ValueError, match="characters"):
        check_limits([para("a" * (MAX_TEXT_LENGTH + 1))])


def test_length_is_summed_over_all_content():
    half = MAX_TEXT_LENGTH // 2 + 1
    bold = FormattedText("bold", text("b" * half))
    with pytest.raises(ValueError, match="characters"):
        check_limits([ParagraphBlock(text("a" * half, bold))])


LONG = text("x" * 40000)


@pytest.mark.parametrize("block, name", [
    (MathBlock("x" * 40000), "expression"),
    (DetailsBlock(summary=LONG), "summary"),
    (BlockquoteBlock([para()], credit=LONG), "credit"),
    (MediaBlock("photo", "x", caption=Caption(LONG)), "caption"),
    (TableBlock([[TableCell(text=LONG)]]), "cell"),
])
def test_length_fields(block, name):
    with pytest.raises(ValueError, match="characters"):
        check_limits([block])


def photo():
    return MediaBlock("photo", "https://e.com/a.png")


def test_media_edge_is_allowed():
    check_limits([photo()] * MAX_MEDIA)


def test_too_many_media():
    with pytest.raises(ValueError, match="media attachments"):
        check_limits([photo()] * (MAX_MEDIA + 1))


def test_media_in_gallery_and_nested_blocks_are_counted():
    gallery = GalleryBlock("collage", [photo()] * MAX_MEDIA)
    check_limits([gallery])
    with pytest.raises(ValueError, match="media attachments"):
        check_limits([gallery, quote(photo())])


def test_urls_and_names_are_not_text():
    link = FormattedText(
        "url", text("link"), {"url": "https://e.com/" + "a" * MAX_TEXT_LENGTH},
    )
    check_limits([ParagraphBlock(text(link, Anchor("a" * MAX_TEXT_LENGTH)))])
