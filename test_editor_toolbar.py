"""Tests for the editor's SVG toolbar (editor_toolbar.py).

Run with:
    pytest test_editor_toolbar.py -v
"""

import re
import xml.etree.ElementTree as ET

import editor_toolbar as et


def test_every_icon_is_valid_svg_on_the_24_grid():
    for key in et.ICONS:
        svg = et.icon_svg(key)
        root = ET.fromstring(svg)  # raises on malformed markup
        assert root.tag.endswith("svg"), key
        assert root.attrib["viewBox"] == "0 0 24 24", key


def test_icons_use_currentcolor_so_they_follow_the_theme():
    for key in et.ICONS:
        assert "#" not in et.ICONS[key], f"{key} hard-codes a color"


def test_every_button_references_an_existing_icon():
    every = [t for g in et.GROUPS for t in g] + list(et.GENERATORS)
    for t in every:
        assert t["icon"] in et.ICONS, t["label"]


def test_no_icon_is_unused():
    used = {t["icon"] for g in et.GROUPS for t in g} | {t["icon"] for t in et.GENERATORS}
    used |= {"save", "undo", "redo", "chevron"}  # header / toggle buttons, outside GROUPS
    assert set(et.ICONS) == used


def test_labels_are_unique():
    labels = [t["label"] for g in et.GROUPS for t in g] + [t["label"] for t in et.GENERATORS]
    assert len(labels) == len(set(labels))


def test_button_ids_used_by_the_editor_script_exist():
    html = et.build_toolbar_html()
    for ident in ("toggle-btn", "gen-theme-btn", "gen-pattern-btn",
                  "gen-pattern-card-btn", "theme-group"):
        assert f'id="{ident}"' in html, ident


def test_block_select_text_is_inside_the_opening_line():
    for g in et.GROUPS:
        for t in g:
            d = t.get("data", {})
            if d.get("select"):
                assert d["select"] in d["open"], t["label"]


def test_markup_escapes_attribute_values():
    html = et.build_toolbar_html()
    # every attribute value is double-quoted and free of raw quotes
    assert not re.search(r'data-\w+="[^"]*"[^ >]', html.replace('"  ', '" '))
