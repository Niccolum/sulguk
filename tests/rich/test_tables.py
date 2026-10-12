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
    ],
)
def test_table(html, expected, name):
    assert conv(html) == expected
