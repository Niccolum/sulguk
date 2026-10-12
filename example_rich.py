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
    c = Case
    return [
        # ---- text
        c("text", "headings",
          "<h1>h1</h1><h2>h2</h2><h3>h3</h3><h4>h4</h4><h5>h5</h5>"
          "<h6>h6</h6>", old=True),
        c("text", "formatting",
          "<p><b>b</b> <strong>strong</strong> <i>i</i> <em>em</em> "
          "<cite>cite</cite> <var>var</var> <tt>tt</tt> <u>u</u> "
          "<ins>ins</ins> <s>s</s> <strike>strike</strike> <del>del</del> "
          "<mark>mark</mark> <kbd>kbd</kbd> "
          "<samp>samp</samp> <code>code</code></p>", old=True),
        c("text", "sub-sup", "<p>H<sub>2</sub>O x<sup>2</sup></p>"),
        c("text", "spoiler-quote-break",
          '<p><tg-spoiler>tg-spoiler</tg-spoiler> <span class="tg-spoiler">'
          "span</span> <q>q</q> строка<br>перенос, невидимый<wbr>перенос"
          "</p>", old=True),
        c("text", "links",
          '<p><a href="https://example.com">url</a>, '
          '<a href="tg://user?id=CHAT_ID">упоминание</a>, '
          "<a>a без href</a></p>", old=True),
        # the old mode turns any href into a url entity, and Telegram rejects
        # "#top" and "tel:", so this case has no old mode
        c("text", "links-special",
          '<p><a name="top"></a><a href="#top">якорь</a>, '
          '<a href="mailto:a@example.com">mailto</a>, '
          '<a href="tel:+10000000000">tel</a></p>'),
        c("text", "time-reference-math",
          '<p><tg-time unix="1767225600">1 января 2026</tg-time>'
          ' <tg-reference name="ref1">сноска</tg-reference> '
          "<tg-math>E=mc^2</tg-math></p>"),
        c("text", "math-block",
          "<tg-math-block>\\int_0^1 x\\,dx = \\frac12</tg-math-block>"),
        c("text", "emoji",
          f'<p>Эмодзи: <tg-emoji emoji-id="{EMOJI_ID}">🙂</tg-emoji></p>'),
        c("text", "hr-footer", "<p>до</p><hr><p>после</p><footer>footer"
          "</footer>", old=True),
        c("text", "progress-meter",
          '<p><progress value="3" max="10"></progress> '
          '<meter min="0" max="5" value="4"></meter></p>', old=True),
        # ---- lists
        c("lists", "unordered",
          "<ul><li>один</li><li>два<ul><li>вложенный</li></ul></li></ul>",
          old=True),
        c("lists", "ordered-start-value",
          '<ol start="3"><li>три</li><li value="10">десять</li>'
          "<li>одиннадцать</li></ol>", old=True),
        c("lists", "ordered-reversed",
          "<ol reversed><li>c</li><li>b</li><li>a</li></ol>", old=True),
        c("lists", "ordered-type",
          '<ol type="a"><li>a</li><li>b</li></ol>'
          '<ol type="I"><li>I</li><li>II</li></ol>', old=True),
        c("lists", "checkboxes",
          '<ul><li><input type="checkbox" checked> сделано</li>'
          '<li><input type="checkbox"> не сделано</li></ul>', old=True),
        # ---- inputs
        c("inputs", "inputs-in-text",
          '<p><input type="checkbox" checked> <input type="checkbox"> '
          '<input type="radio" checked> <input type="radio"> '
          '<input value="значение"> <input></p>', old=True),
        c("inputs", "submit-is-button",
          '<p><input type="submit"> <input type="button" name="go" '
          'value="Go"> <input type="reset"></p>'),
        # ---- quotes and blocks
        c("quotes", "blockquote",
          "<blockquote>blockquote<cite>автор</cite></blockquote>", old=True),
        c("quotes", "expandable",
          "<blockquote expandable>expandable<br>строка 2<br>строка 3<br>"
          "строка 4<br>строка 5</blockquote>", old=True),
        c("quotes", "pullquote", "<aside>pull quote<cite>автор</cite></aside>"),
        c("quotes", "details",
          "<details open><summary>details open</summary><p>скрытый текст"
          "</p></details>", old=True),
        c("quotes", "pre",
          '<pre>pre без языка</pre><pre class="language-python">'
          'print("pre с языком")</pre><pre><code class="language-js">'
          'console.log("pre > code")</code></pre>', old=True),
        # ---- table
        c("table", "table",
          '<table><caption>table caption</caption>'
          '<thead><tr><th>h1</th><th align="center">h2</th></tr></thead>'
          '<tbody><tr><td colspan="2" align="right">colspan</td></tr>'
          '<tr><td rowspan="2" valign="top">rowspan</td><td>b</td></tr>'
          "<tr><td>c</td></tr></tbody>"
          "<tfoot><tr><td>tfoot</td><td>x</td></tr></tfoot></table>"),
        # ---- media
        c("media", "photo", f'<img src="{IMG}">', old=True),
        c("media", "video", f'<video src="{VIDEO}"></video>'),
        c("media", "animation", f'<video src="{GIF}"></video>'),
        c("media", "audio", f'<audio src="{AUDIO}"></audio>'),
        c("media", "document",
          f'<tg-document src="{DOCUMENT}"></tg-document>'),
        c("media", "figure",
          f'<figure><img src="{IMG}" tg-spoiler><figcaption>figure caption'
          "<cite>credit</cite></figcaption></figure>"),
        c("media", "map", '<tg-map lat="55.7558" long="37.6173" zoom="10"/>'),
        c("media", "figure-map",
          '<figure><tg-map lat="48.8566" long="2.3522" zoom="10"/>'
          "<figcaption>map caption</figcaption></figure>"),
        c("media", "collage",
          f'<tg-collage><img src="{IMG}"><img src="{IMG}">'
          "<figcaption>collage</figcaption></tg-collage>"),
        c("media", "slideshow",
          f'<tg-slideshow><img src="{IMG}"><img src="{IMG}">'
          "<figcaption>slideshow</figcaption></tg-slideshow>"),
        # ---- buttons
        c("buttons", "inline-button",
          '<p>Кнопка в тексте: <tg-button type="url" '
          'url="https://example.com">url</tg-button></p>'),
        c("buttons", "styles",
          '<tg-button-row align="center">'
          '<tg-button type="url" style="primary" url="https://example.com">'
          "primary</tg-button>"
          '<tg-button type="callback_data" style="success" data="ok">'
          "success</tg-button>"
          '<tg-button type="callback_data" style="danger" data="no">'
          "danger</tg-button>"
          '<tg-button type="url" style="link" url="https://example.com">'
          "link</tg-button></tg-button-row>"),
        c("buttons", "actions",
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
        # ---- containers
        c("containers", "containers",
          "<div>div</div><section><p>section</p></section><main>main</main>"
          "<nav>nav</nav><header>header</header>", old=True),
        c("containers", "transparent",
          '<p><noscript>noscript</noscript> <output>output</output> '
          '<data value="1">data</data> <time>time</time></p>', old=True),
        c("containers", "ignored",
          "<script>ignored()</script><style>p {}</style>"
          "<template>ignored</template><p>виден только этот абзац</p>",
          old=True),
        c("containers", "head-stylesheet",
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

    async def check(self, case: Case, html: str) -> tuple[str, str]:
        """Send both modes and compare the answers of Telegram.

        ``status`` is ``ok``, ``fail`` or ``empty``: a rich message without
        blocks means Telegram has dropped the content, it must not pass as
        ``ok`` even when both modes are equally empty.
        """
        try:
            by_html = await self._send_rich(InputRichMessage(
                html=transform_rich_html(labeled("html", html)).html,
            ))
            by_blocks = await self._send_rich(InputRichMessage(
                blocks=transform_rich_blocks(labeled("blocks", html)).blocks,
            ))
        except (TelegramAPIError, ValueError) as e:
            return "fail", f"error: {e}"
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
