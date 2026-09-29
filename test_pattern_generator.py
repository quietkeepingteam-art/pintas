"""
Tests for pattern_generator.py - kept separate from test_pintas.py
since this is separate software, not part of the Pintas compiler.

Run with:
    pytest test_pattern_generator.py -v
"""

import base64
import xml.etree.ElementTree as ET

from pattern_generator import as_data_uri, estilo_snippet, generate_pattern_svg
from pintas import compile_pintas


def test_generated_svg_is_well_formed_xml():
    svg, _ = generate_pattern_svg(seed=1, grid_size=4, line_color="#000000", bg_color="#ffffff")
    ET.fromstring(svg)  # raises ParseError if malformed


def test_reproducible_with_same_seed():
    svg1, _ = generate_pattern_svg(seed=42, grid_size=5, line_color="#2563eb", bg_color="#fff")
    svg2, _ = generate_pattern_svg(seed=42, grid_size=5, line_color="#2563eb", bg_color="#fff")
    assert svg1 == svg2


def test_different_seeds_produce_different_patterns():
    svg1, _ = generate_pattern_svg(seed=1, grid_size=5, line_color="#2563eb", bg_color="#fff")
    svg2, _ = generate_pattern_svg(seed=2, grid_size=5, line_color="#2563eb", bg_color="#fff")
    assert svg1 != svg2


def test_unit_size_matches_grid_and_tile_size():
    _, unit = generate_pattern_svg(seed=1, grid_size=6, line_color="#000", bg_color="#fff", tile_size=40)
    assert unit == 6 * 40


def test_colors_appear_in_output():
    svg, _ = generate_pattern_svg(seed=1, grid_size=3, line_color="#123456", bg_color="#abcdef")
    assert "#123456" in svg
    assert "#abcdef" in svg


def test_data_uri_round_trips_to_original_svg():
    svg, _ = generate_pattern_svg(seed=9, grid_size=4, line_color="#000", bg_color="#fff")
    uri = as_data_uri(svg)
    assert uri.startswith("data:image/svg+xml;base64,")
    encoded = uri.split(",", 1)[1]
    decoded = base64.b64decode(encoded).decode("utf-8")
    assert decoded == svg


def test_estilo_snippet_compiles_through_real_pintas_compiler():
    svg, unit = generate_pattern_svg(seed=3, grid_size=4, line_color="#dc2626", bg_color="#fff5f5")
    snippet = estilo_snippet(svg, unit, "body")
    assert snippet.startswith("estilo\n")
    assert snippet.endswith("murdong")

    source = f'texto "Test"\n{snippet}\n'
    html, _ = compile_pintas(source)  # raises if the snippet doesn't actually compile
    assert "background-image" in html
    assert "background-repeat: repeat" in html


def test_estilo_snippet_targets_garrapon_when_requested():
    svg, unit = generate_pattern_svg(seed=3, grid_size=4, line_color="#000", bg_color="#fff")
    snippet = estilo_snippet(svg, unit, ".garrapon")
    assert ".garrapon {" in snippet
