"""Convert sulguk-flavoured HTML into Telegram Rich Message HTML.

Telegram (Bot API 10.1+) parses rich message HTML on its own, so no entities
are produced here. We only normalize the input: unknown attributes are
dropped, non-Telegram tags are mapped to supported ones, ``base_url`` is
applied, text is escaped and whitespace is collapsed like a browser does.
"""
from dataclasses import dataclass
from html import escape
from typing import Optional

from lxml.etree import Element

from sulguk.data import LANG_CLASS_PREFIX
from sulguk.wrapper import parse_html
from .converter import RichConverter
from .dom import children
from .tags import (
    AUTHOR_PARENTS,
    CONTAINER_TAGS,
    DROPPED_TAGS,
    HTML_BLOCK_TAGS,
    HTML_TRANSPARENT_TAGS,
    PLAIN_TAGS,
    RENAMED_TAGS,
    TAG_ATTRS,
    VISIBLE_EMPTY_TAGS,
    VOID_TAGS,
)
from .html_parsing import (
    BUTTON_LIKE_INPUT_TYPES,
    HTML_SPACE_CHARS,
    ZERO_WIDTH_SPACE,
    collapse_html_spaces,
)


@dataclass
class RichResult:
    html: str


class HtmlRenderer(RichConverter):
    def __init__(self, base_url: Optional[str]) -> None:
        super().__init__(base_url)
        self._out: list[str] = []
        # True at the start and after a block or a line break: spaces
        # there are not shown, so they are dropped
        self._at_boundary = True
        # the last text written ends with a space, the next one must not
        # start with another
        self._ends_with_space = False

    def render(self, root: Element) -> str:
        self._visit(root, parent_tag=None, pre=False)
        return "".join(self._out).strip()

    # ---- output

    def _text(self, text: Optional[str], pre: bool) -> None:
        if not text:
            return
        if not pre:
            text = collapse_html_spaces(text)
            if self._at_boundary or self._ends_with_space:
                text = text.lstrip(" ")
            if not text:
                return
        self._at_boundary = False
        self._ends_with_space = not pre and text.endswith(" ")
        self._out.append(escape(text, quote=False))

    def _open(
        self, tag: str, attrs: dict[str, str], self_closing: bool = False,
    ) -> None:
        parts = [tag]
        for key, value in attrs.items():
            if value:
                parts.append(f'{key}="{escape(value, quote=True)}"')
            else:
                parts.append(key)
        end = "/>" if self_closing else ">"
        self._out.append("<" + " ".join(parts) + end)
        self._at_boundary = tag in HTML_BLOCK_TAGS or tag == "br"

    def _close(self, tag: str) -> None:
        self._out.append(f"</{tag}>")
        self._at_boundary = tag in HTML_BLOCK_TAGS

    def _children(self, elem: Element, pre: bool) -> None:
        self._text(elem.text, pre)
        for child in children(elem):
            self._visit(child, parent_tag=str(elem.tag), pre=pre)
            self._text(child.tail, pre)

    def _wrap(
        self,
        tag: str,
        attrs: dict[str, str],
        elem: Element,
        pre: bool,
    ) -> None:
        """Write ``elem`` content inside of ``<tag>``."""
        self._open(tag, attrs)
        self._children(elem, pre)
        self._close(tag)

    # ---- elements

    def _visit(
        self, elem: Element, parent_tag: Optional[str], pre: bool,
    ) -> None:
        tag = str(elem.tag)
        if tag in DROPPED_TAGS:
            return
        if tag in HTML_TRANSPARENT_TAGS:
            self._children(elem, pre)
        elif tag in CONTAINER_TAGS:
            self._visit_container(elem, pre)
        elif tag == "span":
            self._visit_span(elem, pre)
        elif tag == "wbr":
            self._out.append(ZERO_WIDTH_SPACE)
            self._ends_with_space = False
        elif tag == "q":
            self._out.append("“")
            self._at_boundary = False
            self._ends_with_space = False
            self._children(elem, pre)
            self._out.append("”")
            self._ends_with_space = False
        elif tag in ("progress", "meter"):
            self._out.append(escape(self.progress_text(elem), quote=False))
            self._at_boundary = False
            self._ends_with_space = False
        elif tag == "pre":
            self._visit_pre(elem)
        elif tag in ("ul", "ol") and self.flat_list_depth(elem) is not None:
            self._visit_flat_list(elem, pre)
        elif tag == "input":
            self._visit_input(elem, pre)
        elif tag == "code":
            self._visit_code(elem, parent_tag, pre)
        elif tag == "cite" and parent_tag in AUTHOR_PARENTS:
            self._wrap("cite", {}, elem, pre)
        elif tag == "cite":
            self._wrap("i", {}, elem, pre)
        elif tag in RENAMED_TAGS:
            self._wrap(RENAMED_TAGS[tag], {}, elem, pre)
        elif tag in PLAIN_TAGS or tag in TAG_ATTRS or tag == "tg-button":
            self._visit_passed(tag, elem, pre)
        else:
            raise ValueError(f"Unsupported tag: {tag}")

    def _is_blank(self, elem: Element) -> bool:
        """Nothing is shown in the element: no text and no inline media."""
        if "".join(elem.itertext()).strip(HTML_SPACE_CHARS):
            return False
        return not any(
            child.tag in VISIBLE_EMPTY_TAGS for child in elem.iterdescendants()
        )

    def _is_text_container(self, elem: Optional[Element]) -> bool:
        """Container which becomes a paragraph made of its text only."""
        return (
            elem is not None
            and elem.tag in CONTAINER_TAGS
            and not any(
                child.tag in HTML_BLOCK_TAGS for child in children(elem)
            )
            and not self._is_blank(elem)
        )

    def _visit_container(self, elem: Element, pre: bool) -> None:
        if elem.tag in CONTAINER_TAGS and self._is_blank(elem) and not any(
            child.tag in HTML_BLOCK_TAGS for child in children(elem)
        ):
            # an empty container is skipped, it also separates its
            # neighbours as in the ``blocks`` mode
            return
        if not self._is_text_container(elem):
            self._children(elem, pre)
            return
        # as in the old mode, neighbour containers are lines of one block,
        # only a real <p> is a paragraph of its own
        if (
            self._out[-1:] == ["</p>"]
            and self._is_text_container(elem.getprevious())
        ):
            self._out.pop()
            self._out.append("<br>")
            self._at_boundary = True
            self._children(elem, pre)
            self._close("p")
        else:
            self._wrap("p", {}, elem, pre)

    def _visit_span(self, elem: Element, pre: bool) -> None:
        if "tg-spoiler" in elem.get("class", "").split():
            self._wrap("tg-spoiler", {}, elem, pre)
        else:
            self._children(elem, pre)

    def _visit_code(
        self,
        elem: Element,
        parent_tag: Optional[str],
        pre: bool,
        lang: Optional[str] = None,
    ) -> None:
        """``lang`` is the language of the parent ``<pre>``, the language of
        the ``<code>`` itself is preferred."""
        attrs = {}
        if parent_tag == "pre":
            lang = self.language(elem) or lang
        else:
            lang = None
        if lang:
            attrs["class"] = LANG_CLASS_PREFIX + lang
        self._wrap("code", attrs, elem, pre)

    def _visit_pre(self, elem: Element) -> None:
        self._out.append("<pre>")
        code = self.single_code(elem)
        if code is not None:
            self._visit_code(code, "pre", pre=True, lang=self.language(elem))
        else:
            # the language of ``<pre>`` goes to a ``<code>`` made for it
            lang = self.language(elem)
            if lang:
                class_ = escape(LANG_CLASS_PREFIX + lang)
                self._out.append(f'<code class="{class_}">')
            self._children(elem, pre=True)
            if lang:
                self._out.append("</code>")
        self._out.append("</pre>")

    def _visit_flat_list(self, elem: Element, pre: bool) -> None:
        """A list in a table cell is written as lines, the same text as the
        ``blocks`` mode makes: Telegram glues the items of such a list."""
        marks = self.list_marks(elem)
        if not marks:
            return
        indent = "\xa0" * (self.flat_list_depth(elem) or 0)
        if self.has_content_before(elem):
            self._line_break()
        for index, (li, mark) in enumerate(marks):
            if index:
                self._line_break()
            self._text(indent + mark, pre=True)
            # the item text must not start with a second space
            self._ends_with_space = True
            self._children(li, pre)
        if self.has_content_after(elem):
            self._line_break()

    def _line_break(self) -> None:
        self._out.append("<br>")
        self._at_boundary = True
        self._ends_with_space = False

    def _visit_input(self, elem: Element, pre: bool) -> None:
        """Telegram shows only the checkbox of a list item, as ``blocks``
        does everything else is text or a button."""
        parent = elem.getparent()
        if (
            parent is not None
            and parent.tag == "li"
            and self.leading_checkbox(parent) is elem
            and self.flat_list_depth(parent.getparent()) is None
        ):
            self._visit_passed("input", elem, pre)
        elif elem.get("type") in BUTTON_LIKE_INPUT_TYPES:
            label, attrs = self.input_button(elem)
            self._open("tg-button", attrs)
            self._text(label, pre=True)
            self._close("tg-button")
        elif symbol := self.input_symbol(elem):
            self._text(symbol, pre=True)
        elif value := elem.get("value"):
            self._open("u", {})
            self._text(value, pre=True)
            self._close("u")
        else:
            self._text("________", pre=True)

    def _visit_passed(self, tag: str, elem: Element, pre: bool) -> None:
        attrs = self._attrs(tag, elem)
        if tag == "a" and not attrs:
            self._children(elem, pre)
        elif tag == "a" and "href" not in attrs:
            # only an anchor: ``<a name="..."></a>``
            self._open("a", attrs)
            self._out.append("</a>")
        elif tag in VOID_TAGS:
            # ``<tg-map/>`` is the only void tag Telegram documents as
            # self-closing
            self._open(tag, attrs, self_closing=tag == "tg-map")
        else:
            self._wrap(tag, attrs, elem, pre)

    def _attrs(self, tag: str, elem: Element) -> dict[str, str]:
        """Attributes which Telegram knows, urls are made absolute."""
        allowed = TAG_ATTRS.get(tag, frozenset())
        result = {}
        for key, value in elem.attrib.items():
            # <tg-button> has many type-specific attributes, all are kept
            if tag != "tg-button" and key not in allowed:
                continue
            if key in ("href", "src"):
                if not value:
                    # an empty link is no link, as in the blocks mode
                    continue
                value = self.url(value)
            result[key] = value
        if tag == "ol" and "reversed" in result and "start" not in result:
            # Telegram counts down from 1, a browser from the number of items
            items = [c for c in children(elem) if c.tag == "li"]
            result["start"] = str(len(items))
        return result


def transform_rich_html(
    raw_html: Optional[str],
    base_url: Optional[str] = None,
    strict: bool = False,
) -> RichResult:
    """Normalize HTML for ``InputRichMessage.html``."""
    if raw_html is None or raw_html.strip() == "":
        return RichResult(html="")
    doc = parse_html(raw_html, strict=strict)
    return RichResult(html=HtmlRenderer(base_url).render(doc.getroot()))
