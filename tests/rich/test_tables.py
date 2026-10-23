import pytest

from sulguk import transform_rich_blocks


def conv(html, **kwargs):
    return transform_rich_blocks(html, **kwargs).blocks


def cell(**extra):
    return {"align": "left", "valign": "middle", **extra}


def table(*rows, **extra):
    return [{"type": "table", "cells": list(rows), **extra}]


@pytest.mark.parametrize(
    "html, expected, name",
    [
        (
            "<table><tr><th>h</th></tr>"
            '<tr><td colspan="2" align="center">v</td></tr></table>',
            table(
                [cell(text="h", is_header=True, align="center")],
                [cell(text="v", align="center", colspan=2)],
            ),
            "header and colspan",
        ),
        (
            "<table><caption>c</caption><thead><tr><th>h</th></tr></thead>"
            "<tbody><tr><td>v</td></tr></tbody></table>",
            table(
                [cell(text="h", is_header=True, align="center")],
                [cell(text="v")],
                caption="c",
            ),
            "sections and caption",
        ),
        (
            '<table><tr><th>a</th><th align="right">b</th>'
            '<th align="left">c</th></tr></table>',
            table(
                [
                    cell(text="a", is_header=True, align="center"),
                    cell(text="b", is_header=True, align="right"),
                    cell(text="c", is_header=True, align="left"),
                ]
            ),
            "header align default is center",
        ),
        (
            "<table><tfoot><tr><td>f</td></tr></tfoot></table>",
            table([cell(text="f")]),
            "tfoot",
        ),
        (
            "<table><tr><td>a</td><td>b</td></tr><tr><td>c</td></tr></table>",
            table([cell(text="a"), cell(text="b")], [cell(text="c")]),
            "rows of different length",
        ),
        (
            '<table><tr><td rowspan="3">v</td></tr></table>',
            table([cell(text="v", rowspan=3)]),
            "rowspan",
        ),
        (
            '<table><tr><td valign="top" align="right">v</td></tr></table>',
            table([cell(text="v", align="right", valign="top")]),
            "alignment",
        ),
        (
            "<table><tr><td></td></tr></table>",
            table([cell()]),
            "empty cell has no text",
        ),
        (
            "<table><tr><td><b>x</b> y</td></tr></table>",
            table([cell(text=[{"type": "bold", "text": "x"}, " y"])]),
            "cell formatting",
        ),
        (
            "<table><tr><td>a</td></tr></table>",
            table([cell(text="a")]),
            "no caption by default",
        ),
        (
            "<table><tr><td><ul><li>a</li><li>b</li></ul></td></tr></table>",
            table([cell(text="• a\n• b")]),
            "list in a cell",
        ),
        (
            '<table><tr><td><ol start="3"><li>a</li><li value="10">b</li>'
            "<li>c</li></ol></td></tr></table>",
            table([cell(text="3. a\n10. b\n11. c")]),
            "ordered list in a cell",
        ),
        (
            '<table><tr><td><ol type="i" reversed><li>a</li><li>b</li></ol>'
            "</td></tr></table>",
            table([cell(text="ii. a\ni. b")]),
            "ordered list type and reversed",
        ),
        (
            "<table><tr><td>x<ul><li>a</li></ul>y</td></tr></table>",
            table([cell(text="x\n• a\ny")]),
            "text around a list in a cell",
        ),
        (
            "<table><tr><td><ul><li>a<ul><li>b</li></ul></li></ul></td></tr>"
            "</table>",
            table([cell(text="• a\n\xa0• b")]),
            "nested list in a cell",
        ),
        (
            "<table><tr><td><ul><li><b>a</b> b</li></ul></td></tr></table>",
            table([cell(text=["• ", {"type": "bold", "text": "a"}, " b"])]),
            "formatting in a list item of a cell",
        ),
        (
            "<table><tr><td><ul></ul></td></tr></table>",
            table([cell()]),
            "empty list in a cell",
        ),
        (
            "<table><tr><td><table><tr><td>a</td></tr></table></td></tr>"
            "</table>",
            table([cell(text="a")]),
            "table in a cell",
        ),
        (
            "<table><tr><td>x<table><tr><td>a</td><td>b</td></tr>"
            "<tr><td>c</td></tr></table>y</td></tr></table>",
            table([cell(text="xa b\ncy")]),
            "table in a cell keeps the text around",
        ),
    ],
)
def test_table(html, expected, name):
    assert conv(html) == expected


@pytest.mark.parametrize(
    "html, expected, name",
    [
        (
            "<details><summary>s<ul><li>a</li><li>b</li></ul></summary>"
            "<p>x</p></details>",
            [{"type": "details", "summary": "s\n• a\n• b",
              "blocks": [{"type": "paragraph", "text": "x"}]}],
            "list in a summary",
        ),
        (
            "<table><caption><ol><li>a</li><li>b</li></ol></caption>"
            "<tr><td>c</td></tr></table>",
            table([cell(text="c")], caption="1. a\n2. b"),
            "list in a caption",
        ),
        (
            '<figure><img src="https://e.com/a.png"><figcaption>'
            "<ul><li>a</li></ul></figcaption></figure>",
            [{"type": "photo",
              "photo": {"type": "photo", "media": "https://e.com/a.png"},
              "caption": {"text": "• a"}}],
            "list in a figcaption",
        ),
        (
            "<table><tr><td>до<blockquote>цитата</blockquote>после</td>"
            "</tr></table>",
            table([cell(text="до\n▎ цитата\nпосле")]),
            "quote in a cell is a line of its own",
        ),
        (
            "<table><tr><td><pre>строка 1\nстрока 2</pre></td></tr></table>",
            table([cell(text="строка 1\nстрока 2")]),
            "pre in a cell keeps its line breaks",
        ),
        (
            "<table><tr><td>до<pre>a\n  b</pre>после</td></tr></table>",
            table([cell(text="до\na\n  b\nпосле")]),
            "pre in a cell keeps the text around",
        ),
        (
            "<table><tr><td><blockquote>a<blockquote>b</blockquote>"
            "</blockquote></td></tr></table>",
            table([cell(text="▎ a\n▎ b")]),
            "nested quotes in a cell",
        ),
        (
            "<details><summary>s<blockquote>q</blockquote></summary>"
            "<p>x</p></details>",
            [{"type": "details", "summary": "s\n▎ q",
              "blocks": [{"type": "paragraph", "text": "x"}]}],
            "quote in a summary",
        ),
    ],
)
def test_text_only_parents(html, expected, name):
    assert conv(html) == expected
