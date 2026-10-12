import urllib.parse
from typing import Optional

from lxml.etree import Element

from sulguk.entities import Progress
from sulguk.render import State
from .dom import children
from .utils import LANG_CLASS_PREFIX


class RichConverter:
    """What both converters need to know about an element."""

    def __init__(self, base_url: Optional[str]) -> None:
        self._base_url = base_url

    def url(self, url: str) -> str:
        """Make a relative url absolute, anchors are kept as is."""
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
