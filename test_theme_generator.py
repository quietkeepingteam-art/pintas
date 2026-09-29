"""
Tests for theme_generator.py - kept separate from test_pintas.py since
this is separate software, not part of the Pintas compiler itself.

Run with:
    pytest test_theme_generator.py -v
"""

import random

from theme_generator import (
    best_button_text,
    contrast_ratio,
    format_as_theme_entry,
    generate_palette,
    verify_palette,
)


def test_contrast_ratio_extremes():
    assert abs(contrast_ratio("#000000", "#ffffff") - 21.0) < 0.01
    assert abs(contrast_ratio("#2563eb", "#2563eb") - 1.0) < 0.01


def test_best_button_text_picks_higher_contrast_option():
    # Dark accent -> white text wins
    assert best_button_text("#0a0a12") == "#ffffff"
    # Gold-like light accent -> dark text should win (the balitok lesson)
    assert best_button_text("#d4af37") == "#1a1710"


def test_generate_palette_is_reproducible_with_same_seed():
    p1 = generate_palette(random.Random(123))
    p2 = generate_palette(random.Random(123))
    assert p1 == p2


def test_generate_palette_varies_with_different_seeds():
    p1 = generate_palette(random.Random(1))
    p2 = generate_palette(random.Random(2))
    assert p1["accent"] != p2["accent"]


def test_generate_palette_produces_valid_hex_codes():
    p = generate_palette(random.Random(99))
    for key in ("bg", "text", "muted", "accent", "accent-hover", "card-bg"):
        val = p[key]
        assert val.startswith("#") and len(val) == 7
        int(val[1:], 16)  # raises if not valid hex


def test_verify_palette_catches_bad_contrast():
    bad = {
        "bg": "#ffffff", "text": "#fefefe", "muted": "#fdfdfd",
        "accent": "#ffff00", "button-text": "#ffffff",
    }
    checks = verify_palette(bad)
    assert not all(checks.values())


def test_verify_palette_passes_a_known_good_palette():
    good = {
        "bg": "#ffffff", "text": "#111111", "muted": "#444444",
        "accent": "#2563eb", "button-text": "#ffffff",
    }
    checks = verify_palette(good)
    assert all(checks.values())


def test_random_generated_palettes_that_pass_verification_actually_pass():
    # Not every seed produces a passing palette (that's the point - bad
    # ones get rejected), but across many seeds most should pass, and
    # every one that reports passing must actually satisfy the checks.
    passed = 0
    for seed in range(30):
        p = generate_palette(random.Random(seed))
        checks = verify_palette(p)
        if all(checks.values()):
            passed += 1
            assert contrast_ratio(p["bg"], p["text"]) >= 7.0
            assert contrast_ratio(p["bg"], p["muted"]) >= 4.5
            assert contrast_ratio(p["accent"], p["button-text"]) >= 4.5
    assert passed >= 15  # most seeds should yield a usable palette


def test_format_as_theme_entry_is_valid_python_syntax():
    p = generate_palette(random.Random(5))
    entry_text = format_as_theme_entry("candidate", p)
    # Wrap in a dict literal and exec it - raises SyntaxError if malformed
    code = "d = {\n" + entry_text + "\n}"
    namespace = {}
    exec(code, namespace)
    assert "candidate" in namespace["d"]
