import urllib.parse
from typing import List, Optional, Tuple

from lxml.etree import Element

from sulguk.data import LANG_CLASS_PREFIX, NumberFormat
from sulguk.entities import Progress
from sulguk.mapper import OL_FORMAT
from sulguk.render import State
from sulguk.render.numbers import int_to_number
from .dom import children
from .html_parsing import parse_int_attr


class RichConverter:
    """What both converters need to know about an element."""

    def __init__(self, base_url: Optional[str]) -> None:
        self._base_url = base_url

    def url(self, url: str) -> str:
        """Make a relative url absolute, anchors are kept as is.

        Unlike the old mode, which joins ``#name`` with ``base_url`` as a
        browser does with ``<base>``, in a rich message such a link points
        to an anchor of the message itself.
        """
        if self._base_url is None or url.startswith("#"):
            return url
        return urllib.parse.urljoin(self._base_url, url)

    def language(self, elem: Element) -> Optional[str]:
        """Programming language from a ``language-<name>`` class."""
        for cls in elem.get("class", "").split():
            if cls.startswith(LANG_CLASS_PREFIX):
                return cls[len(LANG_CLASS_PREFIX):]
        return None

    def single_code(self, pre: Element) -> Optional[Element]:
        """``<code>`` if it is the only content of ``<pre>``."""
        kids = children(pre)
        if (
            len(kids) == 1
            and kids[0].tag == "code"
            and not (pre.text or "").strip()
            and not (kids[0].tail or "").strip()
        ):
            return kids[0]
        return None

    def leading_checkbox(self, li: Element) -> Optional[Element]:
        """``<input type="checkbox">`` which starts ``<li>``.

        Telegram shows it as the checkbox of the list item. Any other input
        is shown as text or as a button.
        """
        kids = children(li)
        if (
            kids
            and not (li.text or "").strip()
            and kids[0].tag == "input"
            and kids[0].get("type") == "checkbox"
        ):
            return kids[0]
        return None

    def flat_list_depth(self, lst: Element) -> Optional[int]:
        """Nesting of a list in a table cell, ``None`` outside of a cell.

        A cell holds only a text, so Telegram glues the items of a list in
        it together. Such a list is written as lines, see ``list_marks``.
        """
        depth = 0
        for parent in lst.iterancestors():
            if parent.tag in ("td", "th"):
                return depth
            if parent.tag in ("ul", "ol"):
                depth += 1
        return None

    def has_content_before(self, elem: Element) -> bool:
        parent = elem.getparent()
        return elem.getprevious() is not None or bool(
            parent is not None and (parent.text or "").strip(),
        )

    def has_content_after(self, elem: Element) -> bool:
        return elem.getnext() is not None or bool((elem.tail or "").strip())

    def list_marks(self, lst: Element) -> List[Tuple[Element, str]]:
        """Items of ``<ul>``/``<ol>`` with their marks: ``• `` or ``1. ``,
        numbered as in the old mode."""
        items = [c for c in children(lst) if c.tag == "li"]
        if lst.tag == "ul":
            return [(li, "• ") for li in items]
        reverse = "reversed" in lst.attrib
        counter = parse_int_attr(lst.get("start"))
        if counter is None:
            counter = len(items) if reverse else 1
        step = -1 if reverse else 1
        result = []
        for li in items:
            if li.get("value"):
                counter = int(li.get("value"))
            number_format = OL_FORMAT.get(
                li.get("type") or lst.get("type") or "1",
                NumberFormat.DECIMAL,
            )
            result.append((li, f"{int_to_number(counter, number_format)}. "))
            counter += step
        return result

    def input_symbol(self, elem: Element) -> Optional[str]:
        """Emoji of a checkbox or a radio, ``None`` for other inputs."""
        checked = "checked" in elem.attrib
        kind = elem.get("type", "")
        if kind == "checkbox":
            return "☑️" if checked else "◻️"
        if kind == "radio":
            return "🔘" if checked else "⚪️"
        return None

    def input_button(self, elem: Element) -> tuple[str, dict[str, str]]:
        """Label and ``<tg-button>`` attributes of ``<input type="submit">``.

        The button has no action of its own, so it sends ``name`` (or the
        type of the input) as callback data.
        """
        kind = elem.get("type", "")
        label = elem.get("value") or kind.capitalize()
        return label, {
            "type": "callback_data",
            "data": elem.get("name") or kind,
        }

    def progress_text(self, elem: Element) -> str:
        """Emoji bar for ``<progress>`` and ``<meter>``."""
        is_meter = elem.tag == "meter"
        progress = Progress(
            value=float(elem.get("value", "0")),
            min=float(elem.get("min", "0")) if is_meter else 0,
            max=float(elem.get("max", "1")),
            is_meter=is_meter,
        )
        state = State()
        progress.render(state)
        return state.canvas.text
