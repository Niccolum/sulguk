import pytest

from sulguk import transform_rich_html

BASE = "https://e.com/"


def conv(html, **kwargs):
    return transform_rich_html(html, **kwargs).html


@pytest.mark.parametrize(
    "html, expected, name",
    [
        ("", "", "empty"),
        ("  \n ", "", "blank"),
        (None, "", "none"),
        ("<b>a</b>\n\n   <i>b</i>", "<b>a</b> <i>b</i>", "spaces"),
        ("<p>1 &lt; 2 &amp; 3</p>", "<p>1 &lt; 2 &amp; 3</p>", "escape"),
        ('<b class="x" id="y" onclick="z">t</b>', "<b>t</b>", "attrs"),
        (
            '<a href="/p" title="t">x</a>',
            '<a href="https://e.com/p">x</a>',
            "base url",
        ),
        (
            '<a name="c1"></a><a href="#c1">go</a>',
            '<a name="c1"></a><a href="#c1">go</a>',
            "anchors not rebased",
        ),
        (
            '<span class="tg-spoiler">s</span>',
            "<tg-spoiler>s</tg-spoiler>",
            "span spoiler",
        ),
        ("<span>s</span>", "s", "span plain"),
        ("<cite>c</cite>", "<i>c</i>", "cite italic"),
        ("<kbd>k</kbd>", "<code>k</code>", "kbd code"),
        (
            "<blockquote>q<cite>A</cite></blockquote>",
            "<blockquote>q<cite>A</cite></blockquote>",
            "cite author",
        ),
        ("<div>text</div>", "<p>text</p>", "div to p"),
        ("<div><p>a</p><p>b</p></div>", "<p>a</p><p>b</p>", "div transparent"),
        (
            '<pre class="language-python">x = 1</pre>',
            '<pre><code class="language-python">x = 1</code></pre>',
            "pre class language",
        ),
        (
            '<pre><code class="language-go">a</code></pre>',
            '<pre><code class="language-go">a</code></pre>',
            "pre nested code",
        ),
        ("<pre>a\n  b</pre>", "<pre>a\n  b</pre>", "pre whitespace"),
        (
            '<code class="language-go">a</code>',
            "<code>a</code>",
            "code no language",
        ),
        (
            '<ol start="3" type="a" foo="1"><li value="7">x</li></ol>'
            '<ul><li><input type="checkbox" checked>done</li></ul>',
            '<ol start="3" type="a"><li value="7">x</li></ol>'
            '<ul><li><input type="checkbox" checked>done</li></ul>',
            "lists",
        ),
        (
            "<ol reversed><li>x</li><li>y</li><li>z</li></ol>",
            '<ol reversed start="3"><li>x</li><li>y</li><li>z</li></ol>',
            "reversed starts from the count",
        ),
        (
            '<ol reversed start="7"><li>x</li></ol>',
            '<ol reversed start="7"><li>x</li></ol>',
            "reversed keeps start",
        ),
        (
            "<blockquote expandable>q</blockquote>"
            "<details open><summary>s</summary>c</details>",
            "<blockquote expandable>q</blockquote>"
            "<details open><summary>s</summary>c</details>",
            "expandable and details",
        ),
        ("<p><q>x</q></p>", "<p>“x”</p>", "quote"),
        ("<script>alert(1)</script><p>a</p>", "<p>a</p>", "script"),
        (
            "<p>a<noscript>hidden</noscript> b</p>",
            "<p>a b</p>",
            "noscript dropped",
        ),
        (
            '<p><output>o</output> <data value="1">d</data> '
            "<time>t</time></p>",
            "<p>o d t</p>",
            "transparent",
        ),
        ("<p>a<wbr>b</p>", "<p>a​b</p>", "wbr"),
        ("<p>H<sub>2</sub>O</p>", "<p>H<sub>2</sub>O</p>", "sub"),
        ("<p><sup>x</sup></p>", "<p><sup>x</sup></p>", "sup"),
        ("<p><mark>m</mark></p>", "<p><mark>m</mark></p>", "mark"),
        (
            '<p><tg-time unix="1" format="wDT">t</tg-time></p>',
            '<p><tg-time unix="1" format="wDT">t</tg-time></p>',
            "time",
        ),
        (
            '<tg-map lat="1" long="2" zoom="3"/>',
            '<tg-map lat="1" long="2" zoom="3"/>',
            "map",
        ),
        (
            "<table><tr><th>h</th></tr></table>",
            "<table><tbody><tr><th>h</th></tr></tbody></table>",
            "table header",
        ),
        (
            '<table><tr><td align="center" x="1">v</td></tr></table>',
            '<table><tbody><tr><td align="center">v</td></tr></tbody></table>',
            "table cell attrs",
        ),
        (
            '<p><progress value="5" max="10"></progress> x</p>',
            "<p>🟦🟦🟦🟦🟦🟩⬜⬜⬜⬜ x</p>",
            "space after progress",
        ),
        ("<p><q> x</q></p>", "<p>“ x”</p>", "space in quote"),
        (
            '<p><progress value="5" max="10"></progress></p>',
            "<p>🟦🟦🟦🟦🟦🟩⬜⬜⬜⬜</p>",
            "progress",
        ),
    ],
)
def test_conversion(html, expected, name):
    assert conv(html, base_url=BASE) == expected


@pytest.mark.parametrize(
    "html, expected, name",
    [
        (
            '<input type="submit" value="Send">',
            '<tg-button type="callback_data" data="submit">Send</tg-button>',
            "submit",
        ),
        (
            '<input type="button" name="go" value="Go">',
            '<tg-button type="callback_data" data="go">Go</tg-button>',
            "button name",
        ),
        (
            '<input type="reset">',
            '<tg-button type="callback_data" data="reset">Reset</tg-button>',
            "no value",
        ),
        ('<input type="checkbox" checked>', "☑️", "checkbox"),
        ('<input type="radio">', "⚪️", "radio"),
        ('<input type="text" value="v">', "<u>v</u>", "text value"),
        ('<input type="text">', "________", "text empty"),
        # only a checkbox which starts <li> is a real checkbox
        (
            '<ul><li><input type="checkbox" checked>x</li></ul>',
            '<ul><li><input type="checkbox" checked>x</li></ul>',
            "list checkbox",
        ),
        (
            '<ul><li>x <input type="checkbox"></li></ul>',
            "<ul><li>x ◻️</li></ul>",
            "checkbox in text",
        ),
    ],
)
def test_input(html, expected, name):
    assert conv(html) == expected


def test_unsupported_tag_raises():
    with pytest.raises(ValueError, match="Unsupported tag"):
        conv("<foo>x</foo>")


@pytest.mark.parametrize(
    "html, expected, name",
    [
        ("<div>a<b>b</b></div>", "<p>a<b>b</b></p>", "text"),
        ("<div><div>x</div></div>", "<p>x</p>", "nested"),
        # a block inside makes the container transparent
        ("<div>text<p>x</p></div>", "text<p>x</p>", "block"),
        # <img> is not a block here, so <div> still becomes a paragraph
        # as in the old mode, neighbour containers are lines of one block
        (
            "<div>a</div><main>b</main><nav>c</nav>",
            "<p>a<br>b<br>c</p>",
            "neighbours are lines",
        ),
        (
            "<div>a</div><div>b</div><p>c</p><div>d</div><div>e</div>",
            "<p>a<br>b</p><p>c</p><p>d<br>e</p>",
            "paragraph splits lines",
        ),
        (
            "<div><b>a</b></div><div>b <i>i</i></div>",
            "<p><b>a</b><br>b <i>i</i></p>",
            "neighbours keep formatting",
        ),
        (
            "<div>a</div><section><p>s</p></section><div>b</div>",
            "<p>a</p><p>s</p><p>b</p>",
            "container with block splits",
        ),
        (
            '<div><img src="https://e.com/a.png"></div>',
            '<p><img src="https://e.com/a.png"></p>',
            "media",
        ),
    ],
)
def test_container(html, expected, name):
    assert conv(html) == expected


def test_summary_outside_of_details_is_kept():
    assert conv("<summary>s</summary>") == "<summary>s</summary>"
