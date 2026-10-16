"""Tags of both converters: what each of them does with a tag.

The first groups are the same for both. ``html`` and ``body`` are not among
them: ``blocks`` converts them like containers, ``html`` skips them. The
sets of block tags differ too, because they decide different things in each
converter, so every converter has its own section below.
"""

# tags which content is never shown
DROPPED_TAGS = frozenset(
    {
        "head", "script", "style", "template", "title", "meta", "link",
        "noscript",
    },
)
# tags which are replaced with their content
TRANSPARENT_TAGS = frozenset({"output", "data", "time"})
# containers of blocks (and of text, which then becomes a paragraph)
CONTAINER_TAGS = frozenset({"div", "section", "main", "nav", "header"})
HEADING_TAGS = frozenset({"h1", "h2", "h3", "h4", "h5", "h6"})

# ---- blocks

# html and body are containers here, ``html`` converter skips them
BLOCK_CONTAINERS = CONTAINER_TAGS | {"html", "body"}
# tags which can only be separate blocks, not a part of inline text
SEPARATE_BLOCKS = frozenset(
    {
        "img", "video", "audio", "tg-document", "figure", "tg-map",
        "tg-collage", "tg-slideshow", "aside", "tg-button-row",
        "tg-thinking",
    },
)
# tag of a text with formatting -> type of the rich text
FORMAT_TAGS = {
    "b": "bold",
    "strong": "bold",
    "i": "italic",
    "em": "italic",
    "cite": "italic",
    "var": "italic",
    "tt": "italic",
    "u": "underline",
    "ins": "underline",
    "s": "strikethrough",
    "strike": "strikethrough",
    "del": "strikethrough",
    "mark": "marked",
    "sub": "subscript",
    "sup": "superscript",
    "tg-spoiler": "spoiler",
    "code": "code",
    "kbd": "code",
    "samp": "code",
}
# tag of a media -> type of the block
MEDIA_KINDS = {
    "img": "photo",
    "video": "video",
    "audio": "audio",
    "tg-document": "document",
}
OL_TYPES = frozenset({"1", "a", "A", "i", "I"})
TABLE_SECTIONS = frozenset({"thead", "tbody", "tfoot"})

# ---- html

# Tags which Telegram knows and which have no attributes to keep.
PLAIN_TAGS = frozenset(
    {
        "b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "mark",
        "sub", "sup", "tg-spoiler", "p", "footer", "hr", "ul", "aside",
        "summary", "figure", "figcaption", "table", "thead", "tbody",
        "tfoot", "tr", "caption", "tg-math", "tg-math-block", "tg-thinking",
        "br", "tg-collage", "tg-slideshow",
    },
) | HEADING_TAGS

CELL_ATTRS = frozenset({"align", "valign", "colspan", "rowspan"})

# Tags which Telegram knows, with the attributes which are kept.
TAG_ATTRS: dict[str, frozenset[str]] = {
    "a": frozenset({"href", "name"}),
    "ol": frozenset({"start", "type", "reversed"}),
    "li": frozenset({"value", "type"}),
    "blockquote": frozenset({"expandable"}),
    "details": frozenset({"open"}),
    "td": CELL_ATTRS,
    "th": CELL_ATTRS,
    "img": frozenset({"src", "alt", "tg-spoiler"}),
    "video": frozenset({"src", "tg-spoiler"}),
    "audio": frozenset({"src"}),
    "tg-document": frozenset({"src"}),
    "input": frozenset({"type", "checked"}),
    "tg-emoji": frozenset({"emoji-id"}),
    "tg-time": frozenset({"unix", "format"}),
    "tg-reference": frozenset({"name"}),
    "tg-map": frozenset({"lat", "long", "zoom"}),
    "tg-button-row": frozenset({"align"}),
}

# tags without content and closing tag
VOID_TAGS = frozenset({"br", "hr", "img", "input", "tg-map"})

# html and body are skipped here, ``blocks`` converter treats them as
# containers
HTML_TRANSPARENT_TAGS = TRANSPARENT_TAGS | {"html", "body"}
# containers become paragraphs unless they contain blocks
HTML_BLOCK_TAGS = CONTAINER_TAGS | HEADING_TAGS | {
    "p", "footer", "ul", "ol", "li", "blockquote", "aside", "details",
    "table", "pre", "figure", "hr", "tg-collage", "tg-slideshow", "tg-map",
    "tg-math-block", "tg-button-row",
}

# tags which are shown even without any text inside
VISIBLE_EMPTY_TAGS = frozenset(
    {"img", "input", "br", "wbr", "tg-emoji", "progress", "meter", "tg-map"},
)

# tags which are written as another tag
RENAMED_TAGS = {"kbd": "code", "samp": "code", "var": "i", "tt": "i"}
# ``<cite>`` is kept only as an author of these, otherwise it is italic
AUTHOR_PARENTS = frozenset({"blockquote", "aside", "figcaption"})
