"""
Test suite for Pintas 0.1.

Run with:
    pytest test_pintas.py -v
"""

import json
import time
import urllib.request

import pytest
from pintas import (
    THEMES,
    build,
    compile_pintas,
    start_server,
)
from pintas_editor import json_safe, render_editor_html, start_editor_server


def test_basic_page_has_title_and_heading():
    html, _ = compile_pintas('ulo "My Title"\ntexto "Hello"\n')
    assert "<title>My Title</title>" in html
    assert "<h1>Hello</h1>" in html


def test_subtexto_butangan_pagpindutan():
    html, _ = compile_pintas(
        'subtexto "Sub"\nbutangan "Paragraph"\npagpindutan "Click"\n'
    )
    assert "<h2>Sub</h2>" in html
    assert "<p>Paragraph</p>" in html
    assert "<button>Click</button>" in html


def test_text_is_html_escaped():
    html, _ = compile_pintas('texto "<script>alert(1)</script>"\n')
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_valid_silpo_produces_anchor():
    html, _ = compile_pintas('silpo "OpenAI" "https://openai.com"\n')
    assert '<a href="https://openai.com">OpenAI</a>' in html


def test_invalid_silpo_raises_syntax_error():
    with pytest.raises(SyntaxError):
        compile_pintas('silpo "OpenAI"\n')


def test_ladawan_remote_url_not_marked_local():
    html, local_images = compile_pintas('ladawan "https://example.com/a.jpg"\n')
    assert '<img src="https://example.com/a.jpg"' in html
    assert local_images == []


def test_ladawan_local_path_is_tracked_for_copying():
    _, local_images = compile_pintas('ladawan "aso.jpg"\n')
    assert local_images == ["aso.jpg"]


def test_kolor_and_teksto_kolor_and_tengnga():
    html, _ = compile_pintas('kolor "lightblue"\nteksto-kolor "navy"\ntengnga\n')
    assert "background-color: lightblue;" in html
    assert "color: navy;" in html
    assert "text-align: center;" in html


def test_tengnga_requires_exact_match():
    # A line that merely starts with "gitna" but isn't the bare command
    # should NOT silently trigger centering - it's an unrecognized command.
    with pytest.raises(SyntaxError):
        compile_pintas('tengngaan ti balay\n')


def test_estilo_murdong_raw_css_passthrough():
    src = 'estilo\nh1 { font-size: 3em; }\nmurdong\n'
    html, _ = compile_pintas(src)
    assert "h1 { font-size: 3em; }" in html


def test_unclosed_estilo_raises_syntax_error():
    src = 'estilo\nh1 { color: red; }\ntexto "This should not be swallowed"\n'
    with pytest.raises(SyntaxError):
        compile_pintas(src)


def test_style_breakout_is_escaped():
    src = 'kolor "</style><script>alert(1)</script>"\n'
    html, _ = compile_pintas(src)
    assert "</style><script>" not in html


def test_comments_are_skipped():
    html, _ = compile_pintas('# a comment\n// another comment\ntexto "Real"\n')
    assert "<h1>Real</h1>" in html


def test_unrecognized_command_raises_syntax_error():
    with pytest.raises(SyntaxError):
        compile_pintas('hindi-command "value"\n')


def test_garrapon_wraps_content_in_a_div():
    html, _ = compile_pintas('garrapon\ntexto "Inside"\nmurdong\n')
    assert '<div class="garrapon">' in html
    assert "<h1>Inside</h1>" in html
    assert "</div>" in html


def test_garrapon_nesting():
    html, _ = compile_pintas(
        'garrapon\ntexto "Outer"\ngarrapon\nbutangan "Inner"\nmurdong\nmurdong\n'
    )
    assert html.count('<div class="garrapon">') == 2
    assert "<h1>Outer</h1>" in html
    assert "<p>Inner</p>" in html


def test_content_outside_garrapon_is_unaffected():
    html, _ = compile_pintas(
        'texto "Before"\ngarrapon\nbutangan "Inside"\nmurdong\ntexto "After"\n'
    )
    before_idx = html.index("<h1>Before</h1>")
    div_idx = html.index('<div class="garrapon">')
    after_idx = html.index("<h1>After</h1>")
    assert before_idx < div_idx < after_idx


def test_unclosed_garrapon_raises_syntax_error():
    with pytest.raises(SyntaxError):
        compile_pintas('garrapon\ntexto "oops"\n')


def test_dangling_murdong_raises_syntax_error():
    with pytest.raises(SyntaxError):
        compile_pintas('texto "hi"\nmurdong\n')


def test_garrapon_word_inside_estilo_stays_raw_css():
    # A literal "garrapon" appearing as CSS text (e.g. as part of a
    # selector name) must not be misread as the container command.
    html, _ = compile_pintas('estilo\n.garrapon-note { color: red; }\nmurdong\n')
    assert ".garrapon-note { color: red; }" in html


def test_tema_applies_the_named_palette():
    html, _ = compile_pintas('tema "berde"\ntexto "Hello"\n')
    assert "--pintas-accent: #16a34a" in html


def test_tema_unknown_name_raises_with_available_list():
    with pytest.raises(SyntaxError, match="asul"):
        compile_pintas('tema "bughaw"\n')


def test_tema_then_manual_kolor_still_overrides():
    # kolor/teksto-kolor set body properties directly, so they still
    # win over whatever a theme set, same cascade rule as always.
    html, _ = compile_pintas('tema "asul"\nkolor "hotpink"\n')
    assert "body { background-color: hotpink; }" in html
    # the theme's root rule should still appear earlier in the sheet
    assert html.index("--pintas-bg: #f0f6ff") < html.index("background-color: hotpink")


def test_every_theme_has_a_distinct_font_pairing():
    seen = set()
    for name, t in THEMES.items():
        pair = (t["font-heading"], t["font-body"])
        assert pair not in seen, f"{name} reuses a font pairing"
        seen.add(pair)
        assert "font-url" in t


def test_tema_loads_only_its_own_two_fonts():
    html, _ = compile_pintas('tema "duyaw"\ntexto "Hi"\n')
    assert "fonts.googleapis.com/css2?family=DM+Serif+Display" in html
    # a different theme's fonts must not also be pulled in
    assert "Oswald" not in html
    assert "Fraunces" not in html


def test_no_theme_means_no_external_font_request():
    html, _ = compile_pintas('texto "Plain"\n')
    assert "fonts.googleapis.com" not in html


def test_live_reload_script_only_when_requested():
    with_reload, _ = compile_pintas('texto "Hi"\n', live_reload=True)
    without_reload, _ = compile_pintas('texto "Hi"\n', live_reload=False)
    assert "Last-Modified" in with_reload
    assert "Last-Modified" not in without_reload


def test_build_writes_html_and_copies_local_images(tmp_path):
    src_dir = tmp_path / "site"
    src_dir.mkdir()
    (src_dir / "aso.jpg").write_bytes(b"fake image bytes")
    source_path = src_dir / "page.pintas"
    source_path.write_text('texto "Has a dog"\nladawan "aso.jpg"\n')
    output_path = tmp_path / "out" / "index.html"

    build(source_path, output_path)

    assert output_path.exists()
    assert (output_path.parent / "aso.jpg").read_bytes() == b"fake image bytes"
    assert "<h1>Has a dog</h1>" in output_path.read_text()


def test_start_server_serves_the_output_directory(tmp_path):
    (tmp_path / "index.html").write_text("<h1>Served</h1>")
    port = start_server(tmp_path, 8210)
    time.sleep(0.2)
    with urllib.request.urlopen(f"http://localhost:{port}/index.html", timeout=2) as res:
        body = res.read().decode()
        last_modified = res.headers.get("Last-Modified")
    assert "<h1>Served</h1>" in body
    assert last_modified is not None


def test_json_safe_escapes_script_breakout():
    assert "</script>" not in json_safe('{"x": "</script><script>bad"}')


def test_render_editor_html_embeds_current_file_content(tmp_path):
    src = tmp_path / "page.pintas"
    src.write_text('texto "Hello there"\n')
    page = render_editor_html(src)
    assert "Pintas Editor" in page
    assert "Hello there" in page


def test_render_editor_html_missing_file_does_not_crash(tmp_path):
    page = render_editor_html(tmp_path / "does_not_exist.pintas")
    assert "Pintas Editor" in page


def _post_json(url, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=2) as res:
        return json.loads(res.read().decode())


def test_editor_server_compile_and_save(tmp_path):
    source_path = tmp_path / "site.pintas"
    source_path.write_text('texto "Original"\n')
    preview_dir = tmp_path / "out"

    port = start_editor_server(source_path, preview_dir, 8220)
    time.sleep(0.2)

    # GET / serves the editor shell with the current file's content embedded
    with urllib.request.urlopen(f"http://localhost:{port}/", timeout=2) as res:
        page = res.read().decode()
    assert "Pintas Editor" in page
    assert "Original" in page

    # A valid /compile updates the served preview file
    result = _post_json(f"http://localhost:{port}/compile", {"source": 'texto "Changed"\n'})
    assert result == {"ok": True}
    with urllib.request.urlopen(f"http://localhost:{port}/index.html", timeout=2) as res:
        assert "Changed" in res.read().decode()

    # An invalid /compile reports the error and does not clobber the
    # last good preview
    bad = _post_json(f"http://localhost:{port}/compile", {"source": "garrapon\n"})
    assert bad["ok"] is False
    assert "murdong" in bad["error"]
    with urllib.request.urlopen(f"http://localhost:{port}/index.html", timeout=2) as res:
        assert "Changed" in res.read().decode()  # still the last good render

    # /save writes straight back to the real source file
    saved = _post_json(f"http://localhost:{port}/save", {"source": 'texto "Saved!"\n'})
    assert saved == {"ok": True}
    assert "Saved!" in source_path.read_text()


def test_toggle_button_wires_up_named_garrapon():
    html, _ = compile_pintas(
        'pagpindutan "Show" "faq1"\n'
        'garrapon "faq1"\n'
        'butangan "Hidden answer."\n'
        'murdong\n'
    )
    assert "onclick=\"document.getElementById('pintas-faq1')" in html
    assert 'class="garrapon pintas-hidden" id="pintas-faq1"' in html


def test_unreferenced_named_garrapon_stays_visible():
    html, _ = compile_pintas('garrapon "card1"\ntexto "Visible"\nmurdong\n')
    # the utility class is always *defined* in the baseline stylesheet,
    # so check the div's actual class attribute, not substring presence
    assert 'class="garrapon" id="pintas-card1"' in html
    assert 'class="garrapon pintas-hidden" id="pintas-card1"' not in html


def test_bare_pagpindutan_unaffected_by_toggle_feature():
    html, _ = compile_pintas('pagpindutan "Just a button"\n')
    assert "<button>Just a button</button>" in html
    assert "onclick" not in html


def test_duplicate_garrapon_name_raises():
    with pytest.raises(SyntaxError, match="Naus-usar en"):
        compile_pintas('garrapon "x"\nmurdong\ngarrapon "x"\nmurdong\n')


def test_toggle_target_must_exist():
    with pytest.raises(SyntaxError, match="Awan ti garrapon"):
        compile_pintas('pagpindutan "Click" "nope"\n')


def test_garrapon_name_rejects_unsafe_characters():
    with pytest.raises(SyntaxError):
        compile_pintas('garrapon "bad name"\nmurdong\n')


def test_toggle_target_rejects_unsafe_characters():
    # Also doubles as an injection-attempt check: a target containing
    # quotes/parens can never reach the generated onclick attribute.
    with pytest.raises(SyntaxError):
        compile_pintas('pagpindutan "Click" "x\')//"\n')


def test_two_buttons_can_target_the_same_garrapon():
    html, _ = compile_pintas(
        'pagpindutan "Open" "menu"\n'
        'pagpindutan "Close" "menu"\n'
        'garrapon "menu"\n'
        'texto "Menu content"\n'
        'murdong\n'
    )
    assert html.count("pintas-menu") >= 3  # 2 onclick refs + 1 id


def test_original_themes_keep_default_structural_values():
    # rabii/balitok/danum introduced per-theme shape overrides; the six
    # original themes must keep looking exactly as before (no regression).
    for name in ["puraw", "nangisit", "asul", "berde", "duyaw", "labaga"]:
        html, _ = compile_pintas(f'tema "{name}"\ntexto "x"\n')
        assert "--pintas-radius: 8px;" in html
        assert "--pintas-card-radius: 12px;" in html
        assert "--pintas-heading-transform: none;" in html
        assert "--pintas-button-text: #ffffff;" in html


def test_new_themes_have_distinct_structural_personality():
    rabii, _ = compile_pintas('tema "rabii"\ntexto "x"\n')
    assert "--pintas-radius: 999px;" in rabii  # pill buttons
    assert "--pintas-heading-transform: uppercase;" in rabii

    balitok, _ = compile_pintas('tema "balitok"\ntexto "x"\n')
    assert "--pintas-radius: 4px;" in balitok  # sharp, refined
    assert "--pintas-button-text: #1a1710;" in balitok  # dark text on gold

    danum, _ = compile_pintas('tema "danum"\ntexto "x"\n')
    assert "linear-gradient" in danum  # the only gradient background
    assert "--pintas-card-blur: 10px;" in danum  # glassmorphism


def test_balitok_button_text_has_real_contrast_against_gold():
    # Gold (#d4af37) against white text was a real legibility problem
    # (contrast ratio ~2.1) until button-text was made themeable.
    def hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    def luminance(rgb):
        def lin(c):
            c = c / 255
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        r, g, b = rgb
        return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)

    def contrast(h1, h2):
        l1, l2 = luminance(hex_to_rgb(h1)), luminance(hex_to_rgb(h2))
        lighter, darker = max(l1, l2), min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    accent = THEMES["balitok"]["accent"]
    button_text = THEMES["balitok"]["button-text"]
    assert contrast(accent, button_text) >= 4.5  # WCAG AA for normal text


def test_all_nine_themes_produce_valid_css():
    tinycss2 = pytest.importorskip("tinycss2", reason="optional: pip install tinycss2")

    for name in THEMES:
        html, _ = compile_pintas(f'tema "{name}"\ntexto "x"\ngarrapon "c"\nbutangan "y"\nmurdong\n')
        style_block = html.split("<style>")[1].split("</style>")[0]
        rules = tinycss2.parse_stylesheet(style_block, skip_whitespace=True, skip_comments=True)
        errors = [r for r in rules if r.type == "error"]
        assert not errors, f"{name} produced invalid CSS: {errors}"


# ---------- new UI components: immuna, udi, pagtudo, baga, sao, pila ----------

def test_immuna_renders_a_header_element():
    html, _ = compile_pintas('immuna\ntexto "Welcome"\nmurdong\n')
    assert '<header class="pintas-immuna">' in html
    assert "<h1>Welcome</h1>" in html
    assert "</header>" in html


def test_udi_renders_a_footer_element():
    html, _ = compile_pintas('udi\nbutangan "c 2026"\nmurdong\n')
    assert '<footer class="pintas-udi">' in html
    assert "</footer>" in html


def test_pagtudo_renders_a_badge_and_escapes_html():
    html, _ = compile_pintas('pagtudo "<b>Baro!</b>"\n')
    assert '<span class="pintas-badge">&lt;b&gt;Baro!&lt;/b&gt;</span>' in html


def test_baga_renders_an_alert_paragraph():
    html, _ = compile_pintas('baga "Napateg"\n')
    assert '<p class="pintas-baga">Napateg</p>' in html


def test_sao_without_and_with_attribution():
    plain, _ = compile_pintas('sao "Ti kinapudno"\n')
    assert '<blockquote class="pintas-sao"><p>Ti kinapudno</p></blockquote>' in plain
    assert "<cite>" not in plain

    attributed, _ = compile_pintas('sao "Ti kinapudno" "Apo Lam-ang"\n')
    assert "<cite>\u2014 Apo Lam-ang</cite>" in attributed


def test_sao_malformed_line_raises():
    with pytest.raises(SyntaxError, match="Sayop a sao"):
        compile_pintas("sao unquoted text\n")


def test_pila_renders_a_divider():
    html, _ = compile_pintas("pila\n")
    assert '<hr class="pintas-pila">' in html


def test_containers_of_different_kinds_can_nest():
    html, _ = compile_pintas('immuna\ngarrapon\ntexto "Nested"\nmurdong\nmurdong\n')
    assert html.index("<header") < html.index('<div class="garrapon">') < html.index("</header>")


def test_unclosed_immuna_error_names_its_own_kind():
    with pytest.raises(SyntaxError, match="'immuna'"):
        compile_pintas('immuna\ntexto "oops"\n')


def test_container_names_are_one_shared_namespace_across_kinds():
    with pytest.raises(SyntaxError, match="Naus-usar en"):
        compile_pintas('garrapon "x"\nmurdong\nudi "x"\nmurdong\n')


def test_a_named_footer_can_be_a_toggle_target():
    html, _ = compile_pintas(
        'pagpindutan "Show" "foot"\nudi "foot"\nbutangan "hi"\nmurdong\n'
    )
    assert 'class="pintas-udi pintas-hidden" id="pintas-foot"' in html


def test_container_words_inside_estilo_stay_raw_css():
    html, _ = compile_pintas('estilo\nudi\nimmuna\nmurdong\ntexto "ok"\n')
    assert "<h1>ok</h1>" in html
    assert "<footer" not in html and "<header" not in html


def test_new_components_produce_valid_css_under_every_theme():
    tinycss2 = pytest.importorskip("tinycss2", reason="optional: pip install tinycss2")
    for name in THEMES:
        html, _ = compile_pintas(f'tema "{name}"\ntexto "x"\npagtudo "b"\nbaga "a"\npila\n')
        style_block = html.split("<style>")[1].split("</style>")[0]
        rules = tinycss2.parse_stylesheet(style_block, skip_whitespace=True, skip_comments=True)
        assert not [r for r in rules if r.type == "error"], name


def _toolbar_buttons():
    """Every toolbar button in the real editor page, as (kind, text) where
    `text` is exactly what a click inserts into the editor."""
    import html as html_lib
    import re
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    found = re.findall(r'<button class="tb"[^>]*?data-kind="(\w+)"([^>]*)>', page)

    def attr(attrs, name):
        m = re.search(rf'data-{name}="([^"]*)"', attrs)
        return html_lib.unescape(m.group(1)) if m else ""

    out = []
    for kind, attrs in found:
        if kind == "snippet":
            text = attr(attrs, "prefix") + attr(attrs, "placeholder") + attr(attrs, "suffix")
        elif kind == "block":
            body = attr(attrs, "body")
            text = attr(attrs, "open") + "\n" + body + "\n" + attr(attrs, "close")
        elif kind == "line":
            text = attr(attrs, "line")
        else:
            continue  # "toggle" builds its own pair in JavaScript
        out.append((kind, text))
    return out


def test_every_editor_toolbar_button_inserts_valid_pintas():
    # Pull each button's insertion text straight out of the real editor
    # page and compile it through the real compiler, so a toolbar
    # button can never silently drift out of sync with the language.
    buttons = _toolbar_buttons()
    assert len(buttons) >= 30  # guard: the parsing must actually find the toolbar

    for kind, text in buttons:
        try:
            compile_pintas(text + "\n")
        except SyntaxError as e:
            raise AssertionError(f"toolbar button {kind} {text!r} does not compile: {e}")


def test_editor_toolbar_has_a_button_for_every_command():
    words = {text.split()[0] for _, text in _toolbar_buttons()}
    expected = {
        "panid", "ulo", "texto", "subtexto", "butangan", "silpo", "ladawan",
        "kolor", "teksto-kolor", "tengnga", "estilo", "garrapon", "immuna",
        "udi", "pagtudo", "baga", "sao", "pila", "banag", "bilang",
        "naaramid", "duakolum", "bidyo", "saludsod", "pagbilangan",
        "ladawanan", "pagsuratan", "dalan", "pagimbagan", "listaan",
        "ayab", "no", "isuble", "pagpindutan",
    }
    assert expected <= words, f"no toolbar button for: {sorted(expected - words)}"


def test_editor_toolbar_buttons_are_all_icons_with_labels():
    import re
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    buttons = re.findall(r'<button class="tb".*?</button>', page, re.DOTALL)
    assert len(buttons) >= 35
    for b in buttons:
        assert "<svg" in b and 'class="lbl"' in b, b[:80]
        assert "aria-label=" in b and "title=" in b, b[:80]


def test_editor_toolbar_has_no_emoji():
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    assert not [c for c in page if ord(c) > 0x2000 and ord(c) not in (0x2022, 0x2713)], \
        "emoji render differently on every device; use the SVG icon set"


def test_editor_theme_swatches_match_real_themes():
    import re
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    block = re.search(r"var THEMES = \[(.*?)\];", page, re.DOTALL).group(1)
    swatch_names = re.findall(r'\["(\w+)",', block)
    assert set(swatch_names) == set(THEMES)


# ---------- editor generator integration ----------

import pintas
import pintas_editor

def test_generated_theme_snippet_compiles_and_overrides_theme():
    snippet, accent, bg = pintas_editor.generate_theme_snippet(seed=11)
    html, _ = pintas.compile_pintas(snippet + '\ntexto "Kumusta"\n')
    assert accent in html and bg in html
    assert "fonts.googleapis.com" in html  # donor theme loads the fonts


def test_generated_theme_is_reproducible_per_seed():
    assert pintas_editor.generate_theme_snippet(4) == pintas_editor.generate_theme_snippet(4)


def test_generated_pattern_snippet_compiles_for_page_and_card():
    for target in ("body", ".garrapon"):
        snippet = pintas_editor.generate_pattern_snippet(3, 4, "#2563eb", "#f0f6ff", target)
        html, _ = pintas.compile_pintas(snippet + '\ngarrapon\ntexto "x"\nmurdong\n')
        assert "data:image/svg+xml;base64," in html


def test_generated_pattern_rejects_bad_input():
    import pytest
    with pytest.raises(ValueError):
        pintas_editor.generate_pattern_snippet(1, 4, "red;}", "#ffffff", "body")
    with pytest.raises(ValueError):
        pintas_editor.generate_pattern_snippet(1, 4, "#2563eb", "#ffffff", "html")


def test_generate_ui_source_returns_a_compilable_whole_page():
    import re

    r = pintas_editor.generate_ui_source(seed=7)
    html, _ = pintas.compile_pintas(r["source"])
    assert r["name"] in html and r["accent"] in html and r["bg"] in html
    assert r["source"].lstrip().startswith("#")          # a whole file, not a block
    assert "# >>>" not in r["source"]                     # not a replace-in-place block
    assert re.fullmatch(r"#[0-9a-fA-F]{6}", r["accent"]) and re.fullmatch(r"#[0-9a-fA-F]{6}", r["bg"])


def test_generate_ui_source_is_reproducible_per_seed_and_varies():
    assert pintas_editor.generate_ui_source(5) == pintas_editor.generate_ui_source(5)
    assert pintas_editor.generate_ui_source(1)["source"] != pintas_editor.generate_ui_source(2)["source"]


def test_generate_ui_source_without_a_seed_still_works_and_bad_seed_is_rejected():
    assert pintas_editor.generate_ui_source(None)["source"]
    import pytest
    for bad in ("abc", True, [1], {"a": 1}, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            pintas_editor.generate_ui_source(bad)


def test_editor_server_generate_ui_round_trip(tmp_path):
    source_path = tmp_path / "site.pintas"
    source_path.write_text('texto "old"\n', encoding="utf-8")
    port = start_editor_server(source_path, tmp_path / "preview", 8231)
    ok = _post_json(f"http://localhost:{port}/generate-ui", {"seed": 9})
    assert ok["ok"] is True and ok["source"] and ok["name"]
    assert ok["source"] == pintas_editor.generate_ui_source(9)["source"]
    # the reply must compile exactly like the editor will compile it
    compiled = _post_json(f"http://localhost:{port}/compile", {"source": ok["source"]})
    assert compiled["ok"] is True
    # bad input comes back as a JSON error, not a crashed request
    bad = _post_json(f"http://localhost:{port}/generate-ui", {"seed": "abc"})
    assert bad["ok"] is False and bad["error"]
    import urllib.request as _u
    req = _u.Request(f"http://localhost:{port}/generate-ui", data=b'{"seed": 1e999}',
                     headers={"Content-Type": "application/json"})
    with _u.urlopen(req, timeout=2) as res:
        assert json.loads(res.read())["ok"] is False
    # generating never touches the file on disk (only I-save does)
    assert source_path.read_text(encoding="utf-8") == 'texto "old"\n'


def test_editor_page_has_a_baro_a_ui_button_wired_to_generate_ui():
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    assert 'id="gen-ui-btn"' in page and "Baro a UI" in page
    assert '"/generate-ui"' in page
    # replaces the whole text through commit() so it is one undo step
    js = page.split('getElementById("gen-ui-btn")', 1)[1]
    assert "editor.value = data.source" in js and "commit()" in js


# ---------- lists, columns, video ----------

def test_consecutive_list_items_group_into_one_list():
    html, _ = compile_pintas('banag "a"\nbanag "b"\nbilang "c"\nbutangan "x"\nbanag "d"\n')
    assert html.count("<ul") == 2 and html.count("<ol") == 1
    assert html.index("<li>a</li>") < html.index("<li>b</li>") < html.index("</ul>")


def test_list_items_are_html_escaped_and_work_inside_containers():
    html, _ = compile_pintas('garrapon\nbanag "<b>x</b>"\nmurdong\n')
    assert "&lt;b&gt;x&lt;/b&gt;" in html and "<b>x</b>" not in html
    assert html.index('class="garrapon"') < html.index("<li>") < html.index("</div>")


def test_list_command_word_inside_estilo_is_css_not_a_list():
    html, _ = compile_pintas("estilo\nbanag { color: red; }\nmurdong\n")
    assert "<li>" not in html and "banag { color: red; }" in html


def test_duakolum_wraps_cards_and_requires_murdong():
    html, _ = compile_pintas("duakolum\ngarrapon\nmurdong\ngarrapon\nmurdong\nmurdong\n")
    assert 'class="pintas-duakolum"' in html and html.count('class="garrapon"') == 2
    with pytest.raises(SyntaxError):
        compile_pintas("duakolum\n")


def test_bidyo_embeds_youtube_only():
    for url in ("https://youtu.be/aqz-KE-bpKQ", "https://www.youtube.com/watch?v=aqz-KE-bpKQ&t=9"):
        html, _ = compile_pintas(f'bidyo "{url}"\n')
        assert "youtube-nocookie.com/embed/aqz-KE-bpKQ" in html
    with pytest.raises(SyntaxError):
        compile_pintas('bidyo "https://vimeo.com/123"\n')


# ---------- karusel (carousel) ----------

def test_karusel_makes_a_slide_strip_with_controls_and_script():
    src = (
        "karusel\n"
        'ladawan "https://example.com/1.jpg"\n'
        'ladawan "https://example.com/2.jpg"\n'
        'ladawan "https://example.com/3.jpg"\n'
        "murdong\n"
    )
    html, _ = compile_pintas(src)
    assert '<section class="pintas-karusel">' in html
    assert html.count('class="pintas-karusel-slide"') == 3
    assert 'data-dir="prev"' in html and 'data-dir="next"' in html
    assert html.count('alt="Ladawan ') == 3  # one alt per slide
    assert html.count('aria-label="Ladawan ') == 3  # one dot per slide
    assert "querySelectorAll('.pintas-karusel')" in html
    # slides must not carry the plain-image inline style
    assert "max-width:100%" not in html


def test_karusel_with_one_picture_has_no_controls():
    html, _ = compile_pintas('karusel\nladawan "https://example.com/1.jpg"\nmurdong\n')
    assert 'class="pintas-karusel-slide"' in html
    assert 'data-dir="prev"' not in html and "pintas-karusel-tuldo\"" not in html


def test_karusel_script_only_added_when_used():
    html, _ = compile_pintas('butangan "hi"\n')
    assert "querySelectorAll('.pintas-karusel')" not in html


def test_karusel_only_accepts_ladawan_and_needs_at_least_one():
    with pytest.raises(SyntaxError):
        compile_pintas("karusel\nmurdong\n")
    with pytest.raises(SyntaxError):
        compile_pintas('karusel\nladawan "https://example.com/1.jpg"\nbutangan "no"\nmurdong\n')
    with pytest.raises(SyntaxError):
        compile_pintas('karusel\nmurdong\ngarrapon\nladawan "https://example.com/1.jpg"\nmurdong\n')
    with pytest.raises(SyntaxError):
        compile_pintas('karusel\nladawan "https://example.com/1.jpg"\n')  # unclosed


def test_karusel_works_with_isuble_nested_and_named_toggle():
    src = (
        'pagpindutan "Ipakita" "galeria"\n'
        'garrapon\n'
        'karusel "galeria"\n'
        'isuble i manipud 1 agingga 4\n'
        'ladawan "https://example.com/{{i}}.jpg"\n'
        'murdong\n'
        'murdong\n'
        'murdong\n'
    )
    html, _ = compile_pintas(src)
    assert html.count('class="pintas-karusel-slide"') == 4
    assert 'id="pintas-galeria"' in html and "pintas-hidden" in html


def test_karusel_reports_local_images_for_copying():
    _, local = compile_pintas('karusel\nladawan "foto1.jpg"\nladawan "foto2.jpg"\nmurdong\n')
    assert local == ["foto1.jpg", "foto2.jpg"]


def test_karusel_rejects_unsafe_image_sources():
    with pytest.raises(SyntaxError):
        compile_pintas('karusel\nladawan "javascript:alert(1)"\nmurdong\n')


# ---------- mapa (Google Maps) ----------

def test_mapa_embeds_google_maps_and_keeps_non_ascii():
    html, _ = compile_pintas('mapa "Peñablanca, Cagayan"\n')
    assert 'src="https://www.google.com/maps?q=Pe%C3%B1ablanca%2C%20Cagayan&amp;output=embed"' in html
    assert 'title="Mapa: Peñablanca, Cagayan"' in html
    assert "maps/search/?api=1&amp;query=Pe%C3%B1ablanca" in html
    assert 'loading="lazy"' in html


def test_mapa_accepts_zoom_and_coordinates():
    html, _ = compile_pintas('mapa "7.0731,125.6128" "15"\n')
    assert "q=7.0731%2C125.6128&amp;output=embed&amp;z=15" in html


@pytest.mark.parametrize("bad", ['mapa ""', "mapa", 'mapa "a" "b" "c"', 'mapa "a" "0"',
                                 'mapa "a" "22"', 'mapa "a" "abc"', 'mapa "a" "-3"',
                                 'mapa "' + "x" * 201 + '"'])
def test_mapa_rejects_bad_input(bad):
    with pytest.raises(SyntaxError):
        compile_pintas(bad + "\n")


def test_mapa_place_is_escaped_and_cannot_break_out_of_the_attribute():
    html, _ = compile_pintas('mapa "<script>alert(1)</script> & co"\n')
    assert "<script>alert(1)" not in html
    assert "%3Cscript%3E" in html and "&lt;script&gt;" in html


# ---------- Ilokano-only command vocabulary ----------

def test_naaramid_makes_checklist():
    html, _ = compile_pintas('naaramid "a"\nnaaramid "b"\n')
    assert 'pintas-naaramid' in html and html.count("<li>") == 2


def test_dalan_is_nav_and_silpo_inside_it_becomes_nav_link():
    html, _ = compile_pintas('dalan\nsilpo "Umuna" "#umuna"\nmurdong\n')
    assert '<nav class="pintas-dalan">' in html and '<a href="#umuna">Umuna</a>' in html


def test_listaan_ringgor_makes_table_and_ringgor_needs_listaan():
    html, _ = compile_pintas('listaan\nringgor "A" "B"\nringgor "1" "2"\n')
    assert "<th>A</th>" in html and "<td>1</td>" in html
    with pytest.raises(SyntaxError):
        compile_pintas('ringgor "A" "B"\n')


def test_pagimbagan_ayab_saludsod_pagbilangan_pagsuratan_ladawanan():
    src = (
        'pagimbagan "T" "D"\n'
        'ayab "Email" "mailto:a@b.com"\n'
        'saludsod "Q?" "A."\n'
        'pagbilangan "2099-12-31T23:59:59" "Dandani"\n'
        'pagsuratan "Nagan" "Isurat ditoy"\n'
        'ladawanan\nladawan "https://example.com/a.jpg"\nmurdong\n'
    )
    html, _ = compile_pintas(src)
    for cls in ("pintas-pagimbagan", "pintas-ayab", "pintas-saludsod",
                "pintas-pagbilangan", "pintas-pagsuratan", "pintas-ladawanan"):
        assert cls in html
    assert ">Aldaw<" in html and ">Oras<" in html


@pytest.mark.parametrize("old", [
    'link "a" "b"', 'faq "q" "a"', 'countdown "2099-01-01T00:00:00"',
    'textbox "x"', 'kontak "a" "#b"', 'pasilidad "a" "b"', 'punto "a"',
    'tsek "a"', 'nabigasyon', 'galeria', 'talaan',
])
def test_old_english_and_tagalog_commands_are_rejected(old):
    with pytest.raises(SyntaxError):
        compile_pintas(old + "\n")


def test_error_messages_are_ilokano_not_tagalog():
    with pytest.raises(SyntaxError) as e:
        compile_pintas("kagagara\n")
    assert "Diak maawatan" in str(e.value) and "Hindi" not in str(e.value)


def test_no_if_command_renders_only_when_condition_is_true():
    html, _ = compile_pintas(
        'no 5 > 3\ntexto "Shown"\nmurdong\n'
        'no 2 > 3\ntexto "Hidden"\nmurdong\n'
    )
    assert "<h1>Shown</h1>" in html
    assert "<h1>Hidden</h1>" not in html


def test_isuble_for_loop_is_inclusive_and_substitutes_variable():
    html, _ = compile_pintas(
        'isuble i manipud 1 agingga 3\n'
        'butangan "Item {{i}}"\n'
        'murdong\n'
    )
    assert html.count("<p>Item 1</p>") == 1
    assert html.count("<p>Item 2</p>") == 1
    assert html.count("<p>Item 3</p>") == 1


def test_no_and_isuble_can_nest():
    html, _ = compile_pintas(
        'isuble i manipud 1 agingga 3\n'
        'no {{i}} == 2\n'
        'butangan "Duapulo"\n'
        'murdong\n'
        'murdong\n'
    )
    assert "<p>Duapulo</p>" in html
    assert html.count("<p>Duapulo</p>") == 1


def test_isuble_numeric_shorthand():
    html, _ = compile_pintas(
        'isuble 3\nbutangan "Repeat"\nmurdong\n'
    )
    assert html.count("<p>Repeat</p>") == 3


def test_isuble_rejects_zero_step():
    with pytest.raises(SyntaxError):
        compile_pintas(
            'isuble i manipud 1 agingga 3 addang 0\n'
            'butangan "x"\n'
            'murdong\n'
        )


# --- URL scheme safety (silpo / ladawan) and image copying ---------------

@pytest.mark.parametrize("url", [
    "javascript:alert(1)",
    "JavaScript:alert(1)",
    " javascript:alert(1)",
    "java\tscript:alert(1)",
    "vbscript:msgbox(1)",
    "data:text/html,<script>alert(1)</script>",
])
def test_silpo_rejects_dangerous_schemes(url):
    with pytest.raises(SyntaxError):
        compile_pintas(f'silpo "x" "{url}"\n')


@pytest.mark.parametrize("url", [
    "https://example.com",
    "http://example.com",
    "mailto:a@example.com",
    "tel:+639000000000",
    "#umuna",
    "about.html",
    "../index.html",
    "/kontak",
    "//example.com/x",
])
def test_silpo_accepts_normal_links(url):
    html, _ = compile_pintas(f'silpo "x" "{url}"\n')
    assert f'href="{url}"' in html


def test_silpo_inside_dalan_is_also_checked():
    with pytest.raises(SyntaxError):
        compile_pintas('dalan\nsilpo "x" "javascript:alert(1)"\nmurdong\n')


@pytest.mark.parametrize("src", [
    "javascript:alert(1)",
    "JAVASCRIPT:alert(1)",
    "data:text/html;base64,PHNjcmlwdD4=",
    "file:///etc/passwd",
])
def test_ladawan_rejects_dangerous_sources(src):
    with pytest.raises(SyntaxError):
        compile_pintas(f'ladawan "{src}"\n')


@pytest.mark.parametrize("src", [
    "aso.jpg",
    "assets/aso.png",
    "https://example.com/a.jpg",
    "//example.com/a.jpg",
    "data:image/png;base64,AAAA",
])
def test_ladawan_accepts_normal_sources(src):
    html, _ = compile_pintas(f'ladawan "{src}"\n')
    assert f'src="{src}"' in html


def test_build_with_output_next_to_source_does_not_crash(tmp_path):
    (tmp_path / "aso.jpg").write_bytes(b"fake image bytes")
    source_path = tmp_path / "page.pintas"
    source_path.write_text('ladawan "aso.jpg"\n')

    build(source_path, tmp_path / "page.html")

    assert (tmp_path / "page.html").exists()
    assert (tmp_path / "aso.jpg").read_bytes() == b"fake image bytes"


def test_build_never_writes_images_outside_output_folder(tmp_path):
    site = tmp_path / "site"
    (site / "output").mkdir(parents=True)
    (tmp_path / "secret.png").write_bytes(b"outside")
    source_path = site / "page.pintas"
    source_path.write_text('ladawan "../secret.png"\n')

    build(source_path, site / "output" / "index.html")

    # Nothing may appear outside output/ (site/secret.png would be the leak).
    assert not (site / "secret.png").exists()


def test_editor_has_syntax_highlight_layer_covering_every_command():
    from pathlib import Path
    from pintas import CONTAINER_KINDS, LIST_KINDS
    from pintas_editor import EDITOR_KEYWORDS

    page = render_editor_html(Path("/nonexistent.pintas"))
    assert 'id="hl"' in page and 'id="editor"' in page
    known = {w for words in EDITOR_KEYWORDS.values() for w in words}
    # every container/list the compiler knows, plus the block/control words
    assert set(CONTAINER_KINDS) | set(LIST_KINDS) | {"estilo", "murdong", "no", "isuble"} <= known
    # every toolbar button's command must be recognised, or it would show as an error
    for _, text in _toolbar_buttons():
        for line in text.splitlines():
            first = line.split()[0] if line.split() else ""
            assert not first or first in known or first.startswith("#"), first


def test_playground_build_swaps_server_for_pyodide(tmp_path, monkeypatch):
    from pathlib import Path

    import build_playground

    monkeypatch.chdir(Path(__file__).parent)
    out = build_playground.build(tmp_path / "docs")
    page = (out / "index.html").read_text(encoding="utf-8")
    assert "loadPyodide" in page and "preview.srcdoc = data.html" in page
    assert "/index.html?t=" not in page
    for name in build_playground.PY_FILES:
        assert (out / "py" / name).exists()
    assert (out / ".nojekyll").exists()


def test_app_launcher_routes_arguments(monkeypatch, tmp_path):
    import pintas_app

    opened, cli = [], []
    monkeypatch.setattr(pintas_app, "launch_editor", lambda p: opened.append(str(p)))
    monkeypatch.setattr(pintas_app.pintas, "main", lambda: cli.append(True))

    pintas_app.main(["Pintas.exe"])                      # double-click
    pintas_app.main(["Pintas.exe", "site.PINTAS"])       # drag-and-drop / Open with
    pintas_app.main(["Pintas.exe", "a.pintas", "o.html"])  # command line
    assert opened == [str(pintas_app.default_source()), "site.PINTAS"]
    assert cli == [True]
    assert pintas_app.default_source().parts[-3:] == ("Documents", "Pintas", "panid.pintas")


def test_toolbar_shows_only_essentials_and_tucks_the_rest_in_a_collapsible_panel():
    import re
    from pathlib import Path

    import editor_toolbar as et

    page = render_editor_html(Path("/nonexistent.pintas"))
    visible, panel = page.split('id="more-panel"', 1)
    visible_cmds = set(re.findall(r'class="tb"[^>]*?data-kind="\w+"[^>]*?aria-label="([^"]+)"', visible))
    panel_cmds = set(re.findall(r'class="tb"[^>]*?data-kind="\w+"[^>]*?aria-label="([^"]+)"', panel))
    essentials = {t["label"] for g in et.GROUPS for t in g if t["icon"] in et.ESSENTIAL}
    assert visible_cmds == essentials and 8 <= len(visible_cmds) <= 12
    assert len(panel_cmds) > len(visible_cmds)          # the long tail is in the panel
    assert visible_cmds.isdisjoint(panel_cmds)          # nothing is shown twice
    assert 'id="more-panel" hidden' in page                     # collapsed by default
    for ident in ("more-toggle", "toolbar-toggle", "toolbar"):
        assert f'id="{ident}"' in page


def test_editor_has_undo_redo_buttons_and_keyboard_shortcuts():
    from pathlib import Path

    page = render_editor_html(Path("/nonexistent.pintas"))
    for ident in ("undo-btn", "redo-btn"):
        assert f'id="{ident}"' in page
    assert 'e.key.toLowerCase()' in page and "historyUndo" in page


def test_pattern_recipes_cover_every_style_and_symmetry():
    import pattern_generator as pg

    recipes = [pg.random_recipe(s) for s in range(80)]
    assert {r["style"] for r in recipes} == set(pg.STYLES)
    assert {r["symmetric"] for r in recipes} == {True, False}
    assert pg.random_recipe(5) == pg.random_recipe(5)  # deterministic per seed


def test_symmetric_pattern_grid_mirrors_with_flipped_variants():
    import random

    import pattern_generator as pg

    n = 6
    g = pg._flip_grid(random.Random(9), n, True)
    for r in range(n):
        for c in range(n):
            assert g[r][n - 1 - c] == 1 - g[r][c]      # left/right mirror swaps the variant
            assert g[n - 1 - r][c] == 1 - g[r][c]      # top/bottom mirror swaps the variant
            assert g[n - 1 - r][n - 1 - c] == g[r][c]  # both = 180 degree turn keeps it


def test_every_pattern_style_is_valid_svg_and_seeds_look_different():
    import xml.etree.ElementTree as ET

    import pattern_generator as pg

    for style in pg.STYLES:
        for sym in (False, True):
            svg, unit = pg.generate_pattern_svg(3, 6, "#123456", "#ffffff", 40, 3, style, sym)
            ET.fromstring(svg)
            assert unit == 240
        a = pg.generate_pattern_svg(1, 6, "#123456", "#ffffff", style=style)[0]
        b = pg.generate_pattern_svg(2, 6, "#123456", "#ffffff", style=style)[0]
        assert a != b


def test_editor_pattern_button_gives_varied_visible_results():
    import base64
    import re

    import pintas_editor

    def contrast(a, b):
        def lum(h):
            f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            r, g, bl = (f(int(h[i:i + 2], 16) / 255) for i in (1, 3, 5))
            return 0.2126 * r + 0.7152 * g + 0.0722 * bl
        hi, lo = sorted((lum(a), lum(b)), reverse=True)
        return (hi + 0.05) / (lo + 0.05)

    svgs = set()
    for seed in range(40):
        snip = pintas_editor.generate_pattern_snippet(seed, None, "#2563eb", "#f0f6ff", "body")
        payload = re.search(r"base64,([A-Za-z0-9+/=]+)", snip).group(1)
        svgs.add(base64.b64decode(payload).decode())
        compile_pintas(snip)  # still valid Pintas
    assert len(svgs) == 40
    # thin-line looks must be clearly visible against the background, not 1.35:1 washed out
    line = pintas_editor._mix_hex("#2563eb", "#f0f6ff", 0.40)
    assert contrast(line, "#f0f6ff") >= 1.5
