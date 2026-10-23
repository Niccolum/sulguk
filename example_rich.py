"""Check how Telegram renders sulguk rich output, one small case at a time.

Reads BOT_TOKEN and CHAT_ID from ``.env`` (or the environment):

    uv run python example_rich.py                # check all cases
    uv run python example_rich.py lists table    # only cases of these groups

Every case is sent twice, as ``transform_rich_html`` and as
``transform_rich_blocks``. Telegram answers with the message it has parsed
(``Message.rich_message``), so the two answers are compared in code: they
must be equal.

Messages stay in the chat: a case is a line of dashes, a message with the
source html, the old sulguk mode (for the cases which it knows), then
``html`` and ``blocks``. ``rich_preview.html`` is written to compare with a
browser.

Not here: ``<tg-thinking>`` (Telegram accepts it only in drafts) and a voice
note (``<audio src="x.ogg">`` must be Opus, no public sample found).
"""
import asyncio
import difflib
import json
import os
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import InputRichMessage, LinkPreviewOptions

from sulguk import transform_html, transform_rich_blocks, transform_rich_html

IMG = "https://telegram.org/img/t_logo.png"
VIDEO = "https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4"
GIF = "https://upload.wikimedia.org/wikipedia/commons/2/2c/Rotating_earth_%28large%29.gif"
AUDIO = "https://interactive-examples.mdn.mozilla.net/media/cc0-audio/t-rex-roar.mp3"
DOCUMENT = "https://pdfobject.com/pdf/sample.pdf"
# the emoji from the Bot API documentation
EMOJI_ID = "5368324170671202286"

# seconds between messages, Telegram limits a chat to about one per second
PAUSE = 0.5
SEPARATOR = "-" * 30
PREVIEW = Path("rich_preview.html")


@dataclass
class Case:
    group: str
    name: str
    html: str
    # the old mode (entities) knows the tags of this case
    old: bool = False


def _cases() -> list[Case]:
    return [
        # ---- text
        Case("text", "headings",
          "<h1>h1</h1><h2>h2</h2><h3>h3</h3><h4>h4</h4><h5>h5</h5>"
          "<h6>h6</h6>", old=True),
        Case("text", "formatting",
          "<p><b>b</b> <strong>strong</strong> <i>i</i> <em>em</em> "
          "<cite>cite</cite> <var>var</var> <tt>tt</tt> <u>u</u> "
          "<ins>ins</ins> <s>s</s> <strike>strike</strike> <del>del</del> "
          "<mark>mark</mark> <kbd>kbd</kbd> "
          "<samp>samp</samp> <code>code</code></p>", old=True),
        Case("text", "sub-sup", "<p>H<sub>2</sub>O x<sup>2</sup></p>"),
        Case("text", "spoiler-quote-break",
          '<p><tg-spoiler>tg-spoiler</tg-spoiler> <span class="tg-spoiler">'
          "span</span> <q>q</q> строка<br>перенос, невидимый<wbr>перенос"
          "</p>", old=True),
        Case("text", "links",
          '<p><a href="https://example.com">url</a>, '
          '<a href="tg://user?id=CHAT_ID">упоминание</a>, '
          "<a>a без href</a></p>", old=True),
        # the old mode turns any href into a url entity, and Telegram rejects
        # "#top" and "tel:", so this case has no old mode
        Case("text", "links-special",
          '<p><a name="top"></a><a href="#top">якорь</a>, '
          '<a href="mailto:a@example.com">mailto</a>, '
          '<a href="tel:+10000000000">tel</a></p>'),
        Case("text", "time-reference-math",
          '<p><tg-time unix="1767225600">1 января 2026</tg-time>'
          ' <tg-reference name="ref1">сноска</tg-reference> '
          "<tg-math>E=mc^2</tg-math></p>"),
        Case("text", "math-block",
          "<tg-math-block>\\int_0^1 x\\,dx = \\frac12</tg-math-block>"),
        Case("text", "emoji",
          f'<p>Эмодзи: <tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji></p>'),
        Case("text", "hr-footer", "<p>до</p><hr><p>после</p><footer>footer"
          "</footer>", old=True),
        Case("text", "progress-meter",
          '<p><progress value="3" max="10"></progress> '
          '<meter min="0" max="5" value="4"></meter></p>', old=True),
        # ---- lists
        Case("lists", "unordered",
          "<ul><li>один</li><li>два<ul><li>вложенный</li></ul></li></ul>",
          old=True),
        Case("lists", "ordered-start-value",
          '<ol start="3"><li>три</li><li value="10">десять</li>'
          "<li>одиннадцать</li></ol>", old=True),
        Case("lists", "ordered-reversed",
          "<ol reversed><li>c</li><li>b</li><li>a</li></ol>", old=True),
        Case("lists", "ordered-type",
          '<ol type="a"><li>a</li><li>b</li></ol>'
          '<ol type="I"><li>I</li><li>II</li></ol>', old=True),
        Case("lists", "checkboxes",
          '<ul><li><input type="checkbox" checked> сделано</li>'
          '<li><input type="checkbox"> не сделано</li></ul>', old=True),
        # ---- inputs
        Case("inputs", "inputs-in-text",
          '<p><input type="checkbox" checked> <input type="checkbox"> '
          '<input type="radio" checked> <input type="radio"> '
          '<input value="значение"> <input></p>', old=True),
        Case("inputs", "submit-is-button",
          '<p><input type="submit"> <input type="button" name="go" '
          'value="Go"> <input type="reset"></p>'),
        # ---- quotes and blocks
        Case("quotes", "blockquote",
          "<blockquote>blockquote<cite>автор</cite></blockquote>", old=True),
        Case("quotes", "expandable",
          "<blockquote expandable>expandable<br>строка 2<br>строка 3<br>"
          "строка 4<br>строка 5</blockquote>", old=True),
        Case("quotes", "pullquote", "<aside>pull quote<cite>автор</cite></aside>"),
        Case("quotes", "details",
          "<details open><summary>details open</summary><p>скрытый текст"
          "</p></details>", old=True),
        Case("quotes", "pre",
          '<pre>pre без языка</pre><pre class="language-python">'
          'print("pre с языком")</pre><pre><code class="language-js">'
          'console.log("pre > code")</code></pre>', old=True),
        # ---- table
        Case("table", "table",
          '<table><caption>table caption</caption>'
          '<thead><tr><th>h1</th><th align="center">h2</th></tr></thead>'
          '<tbody><tr><td colspan="2" align="right">colspan</td></tr>'
          '<tr><td rowspan="2" valign="top">rowspan</td><td>b</td></tr>'
          "<tr><td>c</td></tr></tbody>"
          "<tfoot><tr><td>tfoot</td><td>x</td></tr></tfoot></table>"),
        # a cell holds a text only and Telegram glues the items of a list in
        # it, so sulguk writes such a list as lines with marks, in both modes
        Case("table", "table-with-list",
          "<table><caption>Покупки</caption>"
          "<thead><tr><th>Раздел</th><th>Список</th></tr></thead>"
          "<tbody>"
          "<tr><td>Фрукты</td><td><ul><li>яблоко</li><li>груша</li></ul></td></tr>"
          "<tr><td>Шаги</td><td><ol><li>купить</li><li>помыть</li></ol></td></tr>"
          "</tbody></table>"),
        # ---- media
        Case("media", "photo", f'<img src="{IMG}">', old=True),
        Case("media", "video", f'<video src="{VIDEO}"></video>'),
        Case("media", "animation", f'<video src="{GIF}"></video>'),
        Case("media", "audio", f'<audio src="{AUDIO}"></audio>'),
        Case("media", "document",
          f'<tg-document src="{DOCUMENT}"></tg-document>'),
        Case("media", "figure",
          f'<figure><img src="{IMG}" tg-spoiler><figcaption>figure caption'
          "<cite>credit</cite></figcaption></figure>"),
        Case("media", "map", '<tg-map lat="55.7558" long="37.6173" zoom="10"/>'),
        Case("media", "figure-map",
          '<figure><tg-map lat="48.8566" long="2.3522" zoom="10"/>'
          "<figcaption>map caption</figcaption></figure>"),
        Case("media", "collage",
          f'<tg-collage><img src="{IMG}"><img src="{IMG}">'
          "<figcaption>collage</figcaption></tg-collage>"),
        Case("media", "slideshow",
          f'<tg-slideshow><img src="{IMG}"><img src="{IMG}">'
          "<figcaption>slideshow</figcaption></tg-slideshow>"),
        # ---- buttons
        Case("buttons", "inline-button",
          '<p>Кнопка в тексте: <tg-button type="url" '
          'url="https://example.com">url</tg-button></p>'),
        Case("buttons", "styles",
          '<tg-button-row align="center">'
          '<tg-button type="url" style="primary" url="https://example.com">'
          "primary</tg-button>"
          '<tg-button type="callback_data" style="success" data="ok">'
          "success</tg-button>"
          '<tg-button type="callback_data" style="danger" data="no">'
          "danger</tg-button>"
          '<tg-button type="url" style="link" url="https://example.com">'
          "link</tg-button></tg-button-row>"),
        Case("buttons", "actions",
          '<tg-button-row>'
          '<tg-button type="copy_text" text="скопировано">copy_text'
          "</tg-button>"
          '<tg-button type="switch_inline_query" query="q">inline'
          "</tg-button>"
          '<tg-button type="switch_inline_query_current_chat" query="q">'
          "current</tg-button>"
          '<tg-button type="switch_inline_query_chosen_chat" query="q" '
          "allow-user-chats allow-bot-chats>chosen</tg-button>"
          '<tg-button type="disabled">disabled</tg-button></tg-button-row>'),
        # ---- nested rich text: block fields which hold rich text, not blocks
        Case("nested", "paragraph-all-inline",
          '<p><b>b</b> <strong>strong</strong> <i>i</i> <em>em</em> '
          "<u>u</u> <ins>ins</ins> <s>s</s> <del>del</del> "
          "<mark>mark</mark> <code>code</code> <kbd>kbd</kbd> "
          "<sub>2</sub><sup>2</sup> "
          '<tg-spoiler>spoiler</tg-spoiler> '
          '<a href="https://example.com">url</a> '
          '<a href="mailto:a@example.com">mailto</a> '
          '<a href="tel:+10000000000">tel</a> '
          '<a href="tg://user?id=CHAT_ID">mention</a> '
          f'<tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji> '
          '<tg-time unix="1767225600">дата</tg-time> '
          "<tg-math>E=mc^2</tg-math> "
          '<tg-reference name="ref1">сноска</tg-reference></p>'),
        Case("nested", "heading-inline",
          f"<h2>Заголовок <b>bold</b> <code>code</code> "
          f'<tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji></h2>'),
        Case("nested", "footer-inline",
          '<footer>Подпись <b>bold</b> '
          '<a href="https://example.com">url</a></footer>'),
        Case("nested", "anchor-flow",
          '<a name="top"></a><p>Текст с якорем '
          '<a href="#top">наверх</a> и сноской '
          '<a href="#ref2">к сноске</a></p>'
          '<p><tg-reference name="ref2">Текст сноски</tg-reference></p>'),
        Case("nested", "quote-blocks",
          "<blockquote><p>абзац с <b>bold</b></p>"
          "<ul><li>пункт <code>code</code></li></ul>"
          "<pre>код</pre><cite>автор <i>ital</i></cite></blockquote>"),
        Case("nested", "expandable-credit",
          "<blockquote expandable>строка с <b>bold</b><br>"
          'и <a href="https://example.com">ссылкой</a>'
          "<cite>автор <s>strike</s></cite></blockquote>"),
        Case("nested", "pullquote-credit",
          "<aside><mark>pull</mark> с <code>code</code>"
          "<cite><b>автор</b></cite></aside>"),
        Case("nested", "details-nested",
          "<details open><summary><b>Заголовок</b> с <code>code</code>"
          "</summary><p>абзац</p><blockquote>цитата</blockquote>"
          "<ol><li>пункт</li></ol></details>"),
        Case("nested", "list-item-blocks",
          "<ul><li><b>пункт</b> с <code>code</code>"
          "<ul><li><tg-spoiler>вложенный</tg-spoiler></li></ul></li>"
          "<li><blockquote>цитата в пункте</blockquote></li>"
          "<li><pre>код в пункте</pre></li></ul>"),
        Case("nested", "list-item-media", f"<ul><li>фото:<img src=\"{IMG}\">"
          "</li></ul>"),
        Case("nested", "table-caption-inline",
          '<table><caption><b>Таблица</b> с <code>code</code></caption>'
          "<tr><th><i>h</i></th></tr><tr><td>v</td></tr></table>"),
        Case("nested", "table-cell-inline",
          "<table><tr><td><b>b</b> <i>i</i> <u>u</u> <s>s</s> "
          "<mark>mark</mark> <code>code</code> <sub>2</sub><sup>2</sup> "
          "<tg-spoiler>spoiler</tg-spoiler> "
          '<a href="https://example.com">url</a> '
          '<tg-emoji emoji-id="' + EMOJI_ID + '">🙂</tg-emoji> '
          "<tg-math>E=mc^2</tg-math></td></tr></table>"),
        Case("nested", "media-caption-inline",
          f"<figure><img src=\"{IMG}\"><figcaption><b>Фото</b> с "
          f'<tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji> '
          '<a href="https://example.com">ссылкой</a>'
          "<cite><i>автор</i></cite></figcaption></figure>"),
        Case("nested", "gallery-caption-inline",
          f"<tg-slideshow><img src=\"{IMG}\"><img src=\"{IMG}\">"
          "<figcaption><b>Слайдшоу</b> с <code>code</code>"
          "<cite>автор</cite></figcaption></tg-slideshow>"),
        Case("nested", "map-caption-inline",
          '<figure><tg-map lat="55.7558" long="37.6173" zoom="10"/>'
          "<figcaption><b>Карта</b><cite><i>автор</i></cite>"
          "</figcaption></figure>"),
        Case("nested", "button-text-inline",
          "<tg-button-row>"
          '<tg-button type="callback_data" data="cb">'
          f'<b>bold</b> <code>code</code> '
          f'<tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji> '
          '<tg-time unix="1767225600">дата</tg-time></tg-button>'
          "</tg-button-row>"),
        Case("nested", "button-in-paragraph",
          '<p>До <tg-button type="url" url="https://example.com">'
          "<b>кнопка</b></tg-button> после</p>"),
        Case("edge", "blockquote-in-blockquote",
          "<blockquote>внешняя<blockquote>внутренняя<cite>автор</cite>"
          "</blockquote></blockquote>"),
        Case("edge", "blockquote-depth-15",
          "<blockquote>" * 15 + "дно" + "</blockquote>" * 15),
        Case("edge", "details-in-list",
          "<ul><li><details open><summary>details</summary>"
          "<p>текст</p></details></li></ul>"),
        Case("edge", "details-in-blockquote",
          "<blockquote><details><summary>details</summary>"
          "<p>текст</p></details></blockquote>"),
        Case("edge", "media-in-blockquote",
          f"<blockquote><img src=\"{IMG}\"></blockquote>"),
        Case("edge", "collage-in-blockquote",
          f"<blockquote><tg-collage><img src=\"{IMG}\"><img src=\"{IMG}\">"
          "</tg-collage></blockquote>"),
        Case("edge", "heading-in-list-item",
          "<ul><li><h3>заголовок</h3><p>текст</p></li></ul>"),
        Case("edge", "blockquote-in-cell",
          "<table><tr><td>до<blockquote>цитата</blockquote>после</td>"
          "</tr></table>"),
        Case("edge", "nested-table-in-cell",
          "<table><tr><td><table><tr><td>внутри</td></tr></table></td>"
          "</tr></table>"),
        Case("edge", "pre-in-cell",
          "<table><tr><td><pre>строка 1\nстрока 2</pre></td></tr></table>"),
        Case("edge", "list-in-summary",
          "<details><summary>Список:<ul><li>a</li><li>b</li></ul>"
          "</summary><p>x</p></details>"),
        Case("edge", "buttons-in-list-item",
          "<ul><li><tg-button-row>"
          '<tg-button type="callback_data" data="a">a</tg-button>'
          "</tg-button-row></li></ul>"),
        Case("edge", "button-in-cell",
          '<table><tr><td><tg-button type="url" '
          'url="https://example.com">b</tg-button></td></tr></table>'),
        Case("edge", "anchor-in-blockquote",
          '<blockquote><a name="quote"></a>цитата</blockquote>'
          '<p><a href="#quote">к цитате</a></p>'),
        Case("edge", "reference-in-cell",
          '<table><tr><td><tg-reference name="cellref">метка'
          "</tg-reference></td></tr></table>"
          '<p><a href="#cellref">ссылка</a></p>'),
        Case("edge", "table-caption-credit",
          "<table><caption>Подпись<cite>автор</cite></caption>"
          "<tr><td>v</td></tr></table>"),
        Case("edge", "divider-in-list-item", "<ul><li>a<hr>b</li></ul>"),
        Case("edge", "footer-in-list-item",
          "<ul><li>a<footer>footer</footer></li></ul>"),
        Case("edge", "figure-in-list-item",
          f"<ul><li><figure><img src=\"{IMG}\"><figcaption>cap"
          "</figcaption></figure></li></ul>"),
        Case("edge", "empty-summary",
          "<details><summary> </summary><p>x</p></details>"),
        Case("edge", "empty-containers",
          "<blockquote> </blockquote><p>a</p><ul><li> </li></ul>"),
        Case("edge", "time-emoji-in-caption",
          f"<figure><img src=\"{IMG}\"><figcaption>"
          '<tg-time unix="1767225600">дата</tg-time> '
          f'<tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji>'
          "</figcaption></figure>"),
        Case("edge", "multiple-buttons-in-paragraph",
          '<p>a <tg-button type="callback_data" data="1">1</tg-button> '
          '<tg-button type="callback_data" data="2">2</tg-button> b</p>'),
        Case("edge", "all-blocks-in-blockquote",
          "<blockquote><h3>h</h3><p>p</p><hr><footer>f</footer>"
          "<tg-math-block>x</tg-math-block></blockquote>"),
        # does Telegram draw a divider inside of a quote at all
        Case("edge", "divider-in-blockquote",
          "<blockquote><p>a</p><hr><p>b</p></blockquote>"),
        # ---- containers
        Case("containers", "containers",
          "<div>div</div><section><p>section</p></section><main>main</main>"
          "<nav>nav</nav><header>header</header>", old=True),
        Case("containers", "transparent",
          '<p><noscript>noscript</noscript> <output>output</output> '
          '<data value="1">data</data> <time>time</time></p>', old=True),
        Case("containers", "ignored",
          "<script>ignored()</script><style>p {}</style>"
          "<template>ignored</template><p>виден только этот абзац</p>",
          old=True),
        Case("containers", "head-stylesheet",
          '<head><link rel="stylesheet" href="styles.css"></head>'
          "<p>виден только этот абзац, head со стилями игнорируется</p>", old=True),
    ]


def load_env(path: str = ".env") -> None:
    """Put ``KEY=VALUE`` lines of the file to the environment."""
    file = Path(path)
    if not file.exists():
        return
    for line in file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def dump(message) -> list[dict]:
    """What Telegram has parsed, as plain data, without the first block:
    it is the label of the mode, see ``labeled``."""
    blocks = message.rich_message.blocks if message.rich_message else []
    return [
        b.model_dump(mode="json", exclude_none=True) for b in blocks[1:]
    ]


def labeled(mode: str, html: str) -> str:
    """The html with the name of the mode as the first paragraph."""
    return f"<p><b>▼ {mode}</b></p>{html}"


def diff(left: list[dict], right: list[dict]) -> str:
    def lines(data):
        return json.dumps(data, ensure_ascii=False, indent=1).splitlines()

    return "\n".join(difflib.unified_diff(
        lines(left), lines(right), "html", "blocks", lineterm="", n=2,
    ))


class Checker:
    def __init__(self, bot: Bot, chat_id: int) -> None:
        self.bot = bot
        self.chat_id = chat_id
        # errors of the modes of the case being checked
        self.errors: list[str] = []

    async def _call(self, method, **kwargs):
        """Call and wait if Telegram asks to; the pause keeps the limit."""
        while True:
            try:
                result = await method(chat_id=self.chat_id, **kwargs)
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            else:
                await asyncio.sleep(PAUSE)
                return result

    async def _send_rich(self, rich: InputRichMessage) -> list[dict]:
        message = await self._call(self.bot.send_rich_message,
                                   rich_message=rich)
        return dump(message)

    async def _send_mode(self, rich: InputRichMessage) -> list[dict]:
        """Nothing for a mode which Telegram or sulguk has rejected."""
        try:
            return await self._send_rich(rich)
        except (TelegramAPIError, ValueError) as e:
            self.errors.append(f"error: {e}")
            return []

    async def check(self, case: Case, html: str) -> tuple[str, str]:
        """Send both modes and compare the answers of Telegram.

        A mode may fail while the other one is fine, so they are sent
        separately: the answer of the fine one is compared with what the
        failed one was meant to make, that shows where the two diverge.

        ``status`` is ``ok``, ``fail`` or ``empty``: a rich message without
        blocks means Telegram has dropped the content, it must not pass as
        ``ok`` even when both modes are equally empty.
        """
        self.errors = []
        by_html = await self._send_mode(InputRichMessage(
            html=transform_rich_html(labeled("html", html)).html,
        ))
        by_blocks = await self._send_mode(InputRichMessage(
            blocks=transform_rich_blocks(labeled("blocks", html)).blocks,
        ))
        errors = self.errors
        if errors:
            if by_html and by_blocks:
                return "fail", "\n".join(errors)
            survived = json.dumps(
                by_html or by_blocks, ensure_ascii=False, indent=2,
            )
            errors = [*errors, f"the other mode is parsed as:\n{survived}"]
            return "fail", "\n".join(errors)
        if not by_html and not by_blocks:
            return "empty", "Telegram has parsed no blocks"
        if by_html == by_blocks:
            return "ok", ""
        return "fail", diff(by_html, by_blocks)

    async def show(self, case: Case, html: str) -> None:
        """One message with the separator and the source html, then the
        old mode. The rich messages are sent by ``check`` after it."""
        # plain text: the html is shown as it is written
        await self._call(
            self.bot.send_message,
            text=f"{SEPARATOR}\n{case.group} / {case.name}\n{SEPARATOR}\n\n{html.strip()}",
            link_preview_options=LinkPreviewOptions(is_disabled=True),
        )
        if case.old:
            # the old mode knows fewer tags, a failure here must be loud
            result = transform_html(labeled("old", html))
            await self._call(
                self.bot.send_message,
                text=result.text,
                entities=result.entities,
                link_preview_options=LinkPreviewOptions(is_disabled=True),
            )


def write_preview(cases: list[Case], chat: str) -> None:
    """Page with the source html of every case, for a browser."""
    rows = []
    for case in cases:
        html = case.html.replace("CHAT_ID", chat)
        rich = transform_rich_html(html).html
        rows.append(
            f"<section><h3>{case.group} / {case.name}</h3>"
            f"<div class=cols><div>{html}</div>"
            f"<pre>{escape(rich)}</pre></div></section>",
        )
    PREVIEW.write_text(
        "<meta charset=utf-8><style>.cols{display:flex;gap:2em}"
        ".cols>*{flex:1}section{border-top:1px solid #ccc}"
        "pre{white-space:pre-wrap}</style>" + "".join(rows),
        encoding="utf-8",
    )


async def main() -> None:
    load_env()
    token = os.getenv("BOT_TOKEN")
    chat = os.getenv("CHAT_ID")
    if not (token and chat):
        sys.exit("Set BOT_TOKEN and CHAT_ID in .env")

    wanted = set(sys.argv[1:])
    cases = [
        case for case in _cases()
        if not wanted or case.group in wanted or case.name in wanted
    ]
    if not cases:
        sys.exit("No such cases")

    bot = Bot(token=token)
    checker = Checker(bot, int(chat))
    failed = []
    labels = {"ok": " OK ", "fail": "FAIL", "empty": "EMPTY"}
    try:
        for case in cases:
            html = case.html.replace("CHAT_ID", chat)
            await checker.show(case, html)
            status, details = await checker.check(case, html)
            print(f"[{labels[status]}] {case.group} / {case.name}")
            if status != "ok":
                failed.append(case)
                print("\n".join("       " + line
                                for line in details.splitlines()))
    finally:
        await bot.session.close()

    write_preview(cases, chat)
    print(f"Open {PREVIEW} in a browser")
    print(f"\n{len(cases) - len(failed)}/{len(cases)} cases are the same")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
