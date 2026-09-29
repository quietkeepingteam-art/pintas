#!/usr/bin/env python3
"""
Pintas 0.6.1
A tiny Ilokano-inspired language for generating webpages.

Author: James Kenneth Ines
The second Ilokano programming language, and the first Ilokano
programming language built for making webpages, aimed at the layman.
Copyright (c) 2026 James Kenneth Ines. Released under the MIT License (see LICENSE).

Usage:
    python pintas.py hello.pintas
    python pintas.py hello.pintas output/index.html
    python pintas.py hello.pintas --serve
"""

import argparse
import functools
import html
import http.server
import re
import shutil
import threading
import time
import webbrowser
from pathlib import Path


def value(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        return bytes(s[1:-1], "utf-8").decode("unicode_escape")
    return s


def css_safe(s):
    """Prevent a value from prematurely closing the <style> block."""
    return s.replace("</", "<\\/")


# Names for a named `garrapon` and a `pagpindutan` toggle target: kept
# to a strict identifier so they can be embedded directly into an id=
# attribute and an inline onclick handler with zero escaping needed -
# no quotes or backslashes possible means no injection surface, rather
# than trying to escape arbitrary text safely in both contexts at once.
NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")

# Container-opening commands share one stack/toggle mechanism; each just
# picks a different HTML tag and default class. Keys are exact command
# words checked in compile_pintas (not prefixes of one another or of any
# other command, so there's no ambiguity in the parsing loop).
CONTAINER_KINDS = {
    "garrapon": ("div", "garrapon"),
    "immuna": ("header", "pintas-immuna"),
    "udi": ("footer", "pintas-udi"),
    "duakolum": ("div", "pintas-duakolum"),
    "dalan": ("nav", "pintas-dalan"),
    "ladawanan": ("section", "pintas-ladawanan"),
}

# One-line list-item commands. Consecutive lines of the same command are
# grouped into a single list by compile_pintas. Value: (list tag, css class).
LIST_KINDS = {
    "banag": ("ul", "pintas-lista"),                      # bullet
    "bilang": ("ol", "pintas-lista"),                     # numbered
    "naaramid": ("ul", "pintas-lista pintas-naaramid"),  # checklist
}

YOUTUBE_ID = re.compile(
    r"(?:youtube\.com/watch\?(?:[^\"\s]*&)?v=|youtu\.be/|youtube\.com/embed/)"
    r"([A-Za-z0-9_-]{11})"
)


# A tasteful default look, applied to every page before any
# kolor/teksto-kolor/tema/estilo rules are layered on top. Without this,
# an unstyled .pintas file renders in the browser's bare defaults
# (serif font, edge-to-edge text, no spacing) - this is what actually
# makes a plain page look plain, independent of vocabulary.
#
# Colors are CSS custom properties so `tema` can swap the whole palette
# in one rule, the same way a second `body { background-color: ... }`
# from `kolor` already overrides the baseline further down.
BASELINE_CSS = [
    ":root { --pintas-bg: #ffffff; --pintas-text: #1a1a1a; "
    "--pintas-muted: #444444; --pintas-accent: #2563eb; "
    "--pintas-accent-hover: #1d4ed8; --pintas-card-bg: #f8f9fa; "
    '--pintas-font-heading: -apple-system, BlinkMacSystemFont, "Segoe UI", '
    "Roboto, Helvetica, Arial, sans-serif; "
    '--pintas-font-body: -apple-system, BlinkMacSystemFont, "Segoe UI", '
    "Roboto, Helvetica, Arial, sans-serif; "
    "--pintas-radius: 8px; --pintas-card-radius: 12px; "
    "--pintas-card-shadow: 0 1px 3px rgba(0,0,0,0.08); "
    "--pintas-button-shadow: none; --pintas-card-blur: 0px; "
    "--pintas-heading-transform: none; --pintas-heading-tracking: normal; "
    "--pintas-button-text: #ffffff; }",
    "body { font-family: var(--pintas-font-body); line-height: 1.6; "
    "color: var(--pintas-text); background: var(--pintas-bg); "
    "max-width: 720px; margin: 0 auto; padding: 2rem 1.5rem; }",
    "h1, h2 { font-family: var(--pintas-font-heading); "
    "text-transform: var(--pintas-heading-transform); "
    "letter-spacing: var(--pintas-heading-tracking); }",
    "h1 { font-size: 2rem; margin-top: 0; line-height: 1.2; }",
    "h2 { font-size: 1.3rem; color: var(--pintas-muted); font-weight: 500; }",
    "p { margin: 1rem 0; }",
    "button { font: inherit; padding: 0.6rem 1.4rem; border: none; "
    "border-radius: var(--pintas-radius); background: var(--pintas-accent); "
    "color: var(--pintas-button-text); cursor: pointer; "
    "transition: background 0.15s ease; box-shadow: var(--pintas-button-shadow); }",
    "button:hover { background: var(--pintas-accent-hover); }",
    "a { color: var(--pintas-accent); text-decoration: none; }",
    "a:hover { text-decoration: underline; }",
    "img { border-radius: var(--pintas-radius); }",
    ".garrapon { padding: 1.5rem; margin: 1.5rem 0; "
    "border-radius: var(--pintas-card-radius); background: var(--pintas-card-bg); "
    "box-shadow: var(--pintas-card-shadow); "
    "backdrop-filter: blur(var(--pintas-card-blur)); }",
    ".pintas-immuna { text-align: center; padding: 2.5rem 1.5rem; "
    "margin: -2rem -1.5rem 2rem -1.5rem; background: var(--pintas-card-bg); }",
    ".pintas-udi { margin-top: 3rem; padding-top: 1.5rem; "
    "border-top: 1px solid var(--pintas-muted); color: var(--pintas-muted); "
    "font-size: 0.9rem; }",
    ".pintas-badge { display: inline-block; background: var(--pintas-accent); "
    "color: var(--pintas-button-text); padding: 0.2rem 0.7rem; "
    "border-radius: 999px; font-size: 0.8rem; font-weight: 600; }",
    ".pintas-baga { background: var(--pintas-card-bg); "
    "border-left: 4px solid var(--pintas-accent); padding: 0.8rem 1rem; "
    "border-radius: 4px; margin: 1rem 0; text-align: left; }",
    ".pintas-sao { border-left: 4px solid var(--pintas-accent); "
    "padding-left: 1.2rem; margin: 1.5rem 0; font-style: italic; "
    "color: var(--pintas-muted); text-align: left; }",
    ".pintas-sao cite { display: block; margin-top: 0.5rem; "
    "font-style: normal; font-size: 0.85rem; }",
    "hr.pintas-pila { border: none; border-top: 2px solid var(--pintas-accent); "
    "width: 60px; margin: 2rem auto; opacity: 0.6; }",
    ".pintas-lista { margin: 1rem 0; padding-left: 1.4rem; text-align: left; }",
    ".pintas-lista li { margin: 0.35rem 0; }",
    ".pintas-lista li::marker { color: var(--pintas-accent); }",
    ".pintas-naaramid { list-style: none; padding-left: 0; }",
    ".pintas-naaramid li { position: relative; padding-left: 1.8rem; }",
    '.pintas-naaramid li::before { content: "\\2713"; position: absolute; left: 0; '
    "color: var(--pintas-accent); font-weight: 700; }",
    ".pintas-duakolum { display: grid; grid-template-columns: 1fr 1fr; "
    "gap: 1rem; margin: 1.5rem 0; text-align: left; }",
    ".pintas-duakolum > .garrapon { margin: 0; }",
    "@media (max-width: 600px) { .pintas-duakolum { grid-template-columns: 1fr; } }",
    ".pintas-bidyo { position: relative; aspect-ratio: 16 / 9; margin: 1.5rem 0; "
    "border-radius: var(--pintas-card-radius); overflow: hidden; }",
    ".pintas-bidyo iframe { position: absolute; inset: 0; width: 100%; "
    "height: 100%; border: 0; }",
    ".pintas-dalan { position: sticky; top: 0; z-index: 20; display: flex; flex-wrap: wrap; "
    "align-items: center; justify-content: center; gap: 0.35rem 1.2rem; padding: 0.85rem 1rem; "
    "margin: -2rem -1.5rem 2rem -1.5rem; background: color-mix(in srgb, var(--pintas-card-bg) 94%, transparent); "
    "border-bottom: 1px solid color-mix(in srgb, var(--pintas-muted) 25%, transparent); "
    "backdrop-filter: blur(10px); }",
    ".pintas-dalan a { color: var(--pintas-text); font-weight: 600; text-decoration: none; }",
    ".pintas-dalan a:hover { color: var(--pintas-accent); text-decoration: none; }",
    ".pintas-pagimbagan { padding: 1.35rem; border-radius: var(--pintas-card-radius); "
    "background: var(--pintas-card-bg); box-shadow: var(--pintas-card-shadow); "
    "border: 1px solid color-mix(in srgb, var(--pintas-muted) 14%, transparent); }",
    ".pintas-pagimbagan h3 { margin: 0 0 0.4rem; font-size: 1.08rem; font-family: var(--pintas-font-heading); }",
    ".pintas-pagimbagan p { margin: 0; color: var(--pintas-muted); }",
    ".pintas-ayab { display: inline-block; margin: 0.35rem 0.35rem 0.35rem 0; padding: 0.65rem 1.05rem; "
    "border-radius: var(--pintas-radius); background: var(--pintas-accent); color: var(--pintas-button-text); "
    "font-weight: 600; text-decoration: none; box-shadow: var(--pintas-button-shadow); }",
    ".pintas-ayab:hover { background: var(--pintas-accent-hover); color: var(--pintas-button-text); text-decoration: none; }",
    ".pintas-listaan-wrap { overflow-x: auto; margin: 1.5rem 0; }",
    ".pintas-listaan { width: 100%; border-collapse: collapse; background: var(--pintas-card-bg); "
    "border-radius: var(--pintas-card-radius); overflow: hidden; box-shadow: var(--pintas-card-shadow); }",
    ".pintas-listaan th, .pintas-listaan td { padding: 0.8rem 0.9rem; border-bottom: 1px solid color-mix(in srgb, var(--pintas-muted) 18%, transparent); text-align: left; }",
    ".pintas-listaan th { background: var(--pintas-accent); color: var(--pintas-button-text); font-weight: 700; }",
    ".pintas-listaan tr:last-child td { border-bottom: none; }",
    ".pintas-saludsod { margin: 1.5rem 0; }",
    ".pintas-saludsod details { background: var(--pintas-card-bg); border: 1px solid color-mix(in srgb, var(--pintas-muted) 18%, transparent); border-radius: var(--pintas-radius); margin: 0.6rem 0; padding: 0.9rem 1rem; box-shadow: var(--pintas-card-shadow); }",
    ".pintas-saludsod summary { cursor: pointer; font-weight: 700; color: var(--pintas-text); }",
    ".pintas-saludsod .pintas-saludsod-sungbat { color: var(--pintas-muted); margin: 0.7rem 0 0; }",
    ".pintas-pagbilangan { display: flex; justify-content: center; flex-wrap: wrap; gap: 0.7rem; margin: 1.5rem 0; }",
    ".pintas-pagbilangan > p { flex-basis: 100%; margin: 0 0 0.25rem; }",
    ".pintas-pagbilangan .pintas-count-unit { min-width: 74px; padding: 0.8rem 0.7rem; background: var(--pintas-card-bg); border-radius: var(--pintas-card-radius); box-shadow: var(--pintas-card-shadow); text-align: center; }",
    ".pintas-pagbilangan .pintas-count-number { display: block; font-size: 1.7rem; font-weight: 800; line-height: 1.1; }",
    ".pintas-pagbilangan .pintas-count-label { display: block; font-size: 0.72rem; color: var(--pintas-muted); text-transform: uppercase; letter-spacing: 0.08em; }",
    ".pintas-ladawanan { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.8rem; margin: 1.5rem 0; }",
    ".pintas-ladawanan img { width: 100%; aspect-ratio: 4 / 3; object-fit: cover; display: block; transition: transform 0.2s ease; cursor: zoom-in; }",
    ".pintas-ladawanan img:hover { transform: scale(1.02); }",
    ".pintas-pagsuratan { display: block; width: 100%; box-sizing: border-box; margin: 0.7rem 0; padding: 0.75rem 0.9rem; font: inherit; color: var(--pintas-text); background: var(--pintas-bg); border: 1px solid color-mix(in srgb, var(--pintas-muted) 35%, transparent); border-radius: var(--pintas-radius); outline: none; }",
    ".pintas-pagsuratan:focus { border-color: var(--pintas-accent); box-shadow: 0 0 0 3px color-mix(in srgb, var(--pintas-accent) 18%, transparent); }",
    ".pintas-hidden { display: none; }",
]

# Structural defaults, used whenever a theme doesn't override them - the
# original six themes below define none of these, so they keep the exact
# look BASELINE_CSS already had before this was made themeable.
STRUCTURE_DEFAULTS = {
    "radius": "8px",
    "card-radius": "12px",
    "card-shadow": "0 1px 3px rgba(0,0,0,0.08)",
    "button-shadow": "none",
    "card-blur": "0px",
    "heading-transform": "none",
    "heading-tracking": "normal",
    "button-text": "#ffffff",
}

# Curated palettes for `tema`, named after real Ilokano words (asul/
# nangisit/berde/duyaw/labaga/rabii/balitok/danum all confirmed against
# Ilokano sources; puraw is the default light look, included for
# symmetry). Each is a complete, pre-matched combination - background,
# text, muted text, accent, accent-hover, card background, and a
# curated Google Font pairing - so picking one word gets a coherent
# result without needing to choose colors or fonts individually.
# rabii/balitok/danum additionally override the shape variables below
# (radius, shadow, heading treatment) for a genuinely distinct feel,
# not just different colors on the same shape.
# "font-url" is the Google Fonts CSS2 family query for just that
# theme's two fonts, so only the fonts actually used get downloaded.
THEMES = {
    "puraw": {  # white / light (default) - elegant serif/sans editorial pairing
        "bg": "#ffffff", "text": "#1a1a1a", "muted": "#444444",
        "accent": "#2563eb", "accent-hover": "#1d4ed8", "card-bg": "#f8f9fa",
        "font-heading": '"Fraunces", Georgia, serif',
        "font-body": '"Inter", -apple-system, sans-serif',
        "font-url": "family=Fraunces:wght@600;700&family=Inter:wght@400;600",
    },
    "nangisit": {  # black / dark mode - modern geometric tech pairing
        "bg": "#121212", "text": "#f5f5f5", "muted": "#b3b3b3",
        "accent": "#3b82f6", "accent-hover": "#2563eb", "card-bg": "#1e1e1e",
        "font-heading": '"Space Grotesk", sans-serif',
        "font-body": '"Inter", sans-serif',
        "font-url": "family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600",
    },
    "asul": {  # blue - friendly-professional pairing
        "bg": "#f0f6ff", "text": "#0f172a", "muted": "#475569",
        "accent": "#2563eb", "accent-hover": "#1d4ed8", "card-bg": "#ffffff",
        "font-heading": '"Poppins", sans-serif',
        "font-body": '"Source Sans 3", sans-serif',
        "font-url": "family=Poppins:wght@600;700&family=Source+Sans+3:wght@400;600",
    },
    "berde": {  # green - organic/natural pairing
        "bg": "#f3faf5", "text": "#14291c", "muted": "#3f6b4d",
        "accent": "#16a34a", "accent-hover": "#15803d", "card-bg": "#ffffff",
        "font-heading": '"Lora", Georgia, serif',
        "font-body": '"Nunito Sans", sans-serif',
        "font-url": "family=Lora:wght@600;700&family=Nunito+Sans:wght@400;600",
    },
    "duyaw": {  # yellow / gold - warm, sophisticated pairing
        "bg": "#fffaf0", "text": "#2b2210", "muted": "#6b5b2a",
        "accent": "#d97706", "accent-hover": "#b45309", "card-bg": "#ffffff",
        "font-heading": '"DM Serif Display", Georgia, serif',
        "font-body": '"DM Sans", sans-serif',
        "font-url": "family=DM+Serif+Display&family=DM+Sans:wght@400;600",
    },
    "labaga": {  # red - bold, energetic pairing
        "bg": "#fff5f5", "text": "#2b0f0f", "muted": "#6b3a3a",
        "accent": "#dc2626", "accent-hover": "#b91c1c", "card-bg": "#ffffff",
        "font-heading": '"Oswald", sans-serif',
        "font-body": '"Work Sans", sans-serif',
        "font-url": "family=Oswald:wght@600;700&family=Work+Sans:wght@400;600",
    },
    # The three below are a different kind of theme: not just a palette,
    # but a distinct shape language too (radius, shadow, heading
    # treatment) - "crazy, not an eyesore" needs more than new hex codes.
    "rabii": {  # night - neon/cyberpunk: deep dark, glowing magenta, pill buttons
        "bg": "#0a0a12", "text": "#f0eefc", "muted": "#9d94c4",
        "accent": "#e838ff", "accent-hover": "#c91be0", "card-bg": "#16121f",
        "font-heading": '"Orbitron", sans-serif',
        "font-body": '"Rubik", sans-serif',
        "font-url": "family=Orbitron:wght@700;800&family=Rubik:wght@400;600",
        "radius": "999px", "card-radius": "16px",
        "card-shadow": "0 0 24px rgba(232,56,255,0.25)",
        "button-shadow": "0 0 16px rgba(232,56,255,0.5)",
        "heading-transform": "uppercase", "heading-tracking": "0.08em",
    },
    "balitok": {  # gold - opulent: warm black, gold accent, sharp refined corners
        "bg": "#0f0e0c", "text": "#f5f0e6", "muted": "#a8967a",
        "accent": "#d4af37", "accent-hover": "#a8862a", "card-bg": "#1a1815",
        "font-heading": '"Playfair Display", Georgia, serif',
        "font-body": '"Montserrat", sans-serif',
        "font-url": "family=Playfair+Display:wght@600;700&family=Montserrat:wght@400;600",
        "radius": "4px", "card-radius": "4px",
        "card-shadow": "0 0 0 1px rgba(212,175,55,0.35), 0 4px 16px rgba(0,0,0,0.45)",
        "button-shadow": "0 2px 8px rgba(212,175,55,0.3)",
        "heading-transform": "none", "heading-tracking": "0.05em",
        "button-text": "#1a1710",  # gold is too light for white button text
    },
    "danum": {  # water - soft/fluid: aqua gradient, glassy cards, bubbly rounded shapes
        "bg": "linear-gradient(135deg, #e0f7fa 0%, #b2ebf2 50%, #80deea 100%)",
        "text": "#0d3b3e", "muted": "#4a7c82",
        "accent": "#0891b2", "accent-hover": "#0e7490",
        "card-bg": "rgba(255,255,255,0.55)",
        "font-heading": '"Quicksand", sans-serif',
        "font-body": '"Karla", sans-serif',
        "font-url": "family=Quicksand:wght@600;700&family=Karla:wght@400;600",
        "radius": "24px", "card-radius": "24px", "card-blur": "10px",
        "card-shadow": "0 4px 20px rgba(8,145,178,0.2)",
        "button-shadow": "0 4px 14px rgba(8,145,178,0.35)",
        "heading-transform": "none", "heading-tracking": "normal",
    },
}


def root_rule_from_theme(t):
    """The :root variable rule for a theme dict (shipped or generated)."""
    s = STRUCTURE_DEFAULTS
    return (
        ":root { --pintas-bg: %s; --pintas-text: %s; --pintas-muted: %s; "
        "--pintas-accent: %s; --pintas-accent-hover: %s; --pintas-card-bg: %s; "
        "--pintas-font-heading: %s; --pintas-font-body: %s; "
        "--pintas-radius: %s; --pintas-card-radius: %s; "
        "--pintas-card-shadow: %s; --pintas-button-shadow: %s; "
        "--pintas-card-blur: %s; --pintas-heading-transform: %s; "
        "--pintas-heading-tracking: %s; --pintas-button-text: %s; }"
        % (
            t["bg"], t["text"], t["muted"], t["accent"], t["accent-hover"],
            t["card-bg"], t["font-heading"], t["font-body"],
            t.get("radius", s["radius"]),
            t.get("card-radius", s["card-radius"]),
            t.get("card-shadow", s["card-shadow"]),
            t.get("button-shadow", s["button-shadow"]),
            t.get("card-blur", s["card-blur"]),
            t.get("heading-transform", s["heading-transform"]),
            t.get("heading-tracking", s["heading-tracking"]),
            t.get("button-text", s["button-text"]),
        )
    )


def theme_root_rule(name):
    return root_rule_from_theme(THEMES[name])


def theme_font_links(name):
    """<link> tags to load a theme's two Google Fonts, with preconnect."""
    url = f"https://fonts.googleapis.com/css2?{THEMES[name]['font-url']}&display=swap"
    return [
        '  <link rel="preconnect" href="https://fonts.googleapis.com">',
        '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        f'  <link rel="stylesheet" href="{html.escape(url, quote=True)}">',
    ]


def is_remote(src):
    """True for http(s), protocol-relative, or data: image sources."""
    return bool(re.match(r"^(https?:)?//|^data:", src, re.IGNORECASE))


def url_scheme(url):
    """Return the URL's scheme in lowercase, or None for a relative path.

    Browsers ignore whitespace/control characters inside a scheme, so
    "java\tscript:" and " JavaScript:" must count as "javascript".
    """
    cleaned = re.sub(r"[\x00-\x20]", "", url).lower()
    m = re.match(r"([a-z][a-z0-9+.\-]*):", cleaned)
    return m.group(1) if m else None


LINK_SCHEMES = ("http", "https", "mailto", "tel")


def check_link_url(url, line_no):
    """Reject links with a scheme other than http/https/mailto/tel.

    Fragments (#), relative paths (about.html) and protocol-relative
    (//host) links carry no scheme and are always fine.
    """
    scheme = url_scheme(url)
    if scheme is not None and scheme not in LINK_SCHEMES:
        raise SyntaxError(
            f"Linya {line_no}: Ti silpo ket saan a mabalin nga agusar iti "
            f"'{scheme}:'. Usaren: http://, https://, mailto:, tel:, # "
            "wenno relative a path"
        )


def check_image_src(src, line_no):
    """Reject image sources other than http(s), data:image/ or a local path."""
    scheme = url_scheme(src)
    if scheme is None or scheme in ("http", "https"):
        return
    cleaned = re.sub(r"[\x00-\x20]", "", src).lower()
    if scheme == "data" and cleaned.startswith("data:image/"):
        return
    raise SyntaxError(
        f"Linya {line_no}: Ti ladawan ket saan a mabalin nga agusar iti "
        f"'{scheme}:'. Usaren: http://, https://, data:image/ wenno "
        "local a file"
    )


# Injected only when compiling for `--serve`. Polls the page's own
# Last-Modified header (which http.server sends automatically for
# static files) and reloads when it changes - no custom server route
# needed, just a plain HEAD request against the file being served.
LIVE_RELOAD_SCRIPT = """  <script>
  (function () {
    var lastModified = null;
    function poll() {
      fetch(location.href, { method: "HEAD", cache: "no-store" })
        .then(function (res) {
          var lm = res.headers.get("Last-Modified");
          if (lastModified === null) {
            lastModified = lm;
          } else if (lm && lm !== lastModified) {
            location.reload();
          }
        })
        .catch(function () {})
        .finally(function () {
          setTimeout(poll, 1000);
        });
    }
    poll();
  })();
  </script>"""



def _control_literal(token, variables):
    """Resolve a Pintas control-flow value for `no`/`isuble`."""
    token = token.strip()
    if token.startswith('"') and token.endswith('"') and len(token) >= 2:
        return value(token)
    if token in variables:
        return variables[token]
    low = token.lower()
    if low in ("true", "pudno"):
        return True
    if low in ("false", "saan"):
        return False
    try:
        return float(token) if "." in token else int(token)
    except ValueError:
        return token


def _pintas_condition(expression, variables, line_no):
    """Evaluate the small deterministic condition syntax used by `no`."""
    expression = expression.strip()
    if not expression:
        raise SyntaxError(f"Linya {line_no}: Ti 'no' ket kasapulan iti kondisyon")
    m = re.match(r"^(.*?)\s*(==|!=|>=|<=|>|<)\s*(.*?)$", expression)
    if not m:
        return bool(_control_literal(expression, variables))
    left, op, right = m.groups()
    a = _control_literal(left, variables)
    b = _control_literal(right, variables)
    try:
        return {
            "==": lambda: a == b, "!=": lambda: a != b,
            ">": lambda: a > b, "<": lambda: a < b,
            ">=": lambda: a >= b, "<=": lambda: a <= b,
        }[op]()
    except TypeError as exc:
        raise SyntaxError(
            f"Linya {line_no}: Di mabalin a pagkomparaan ti '{left}' ken '{right}'"
        ) from exc


def _pintas_substitute(line, variables):
    """Replace {{name}} with a loop variable's current value."""
    return re.sub(
        r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}",
        lambda m: str(variables[m.group(1)]) if m.group(1) in variables else m.group(0),
        line,
    )


def _expand_pintas_controls(lines, variables=None):
    """Expand Pintas `no` and `isuble` blocks at compile time.

    Syntax:
        no 5 > 3
          butangan "This appears"
        murdong

        isuble i manipud 1 agingga 5
          butangan "Item {{i}}"
        murdong

    `isuble` ranges are inclusive. `addang` optionally changes the step.
    `isuble 3` is a shorthand for repeating a block three times.
    """
    variables = dict(variables or {})

    def is_container(line):
        return any(
            line == k or line.startswith(k + " ")
            for k in CONTAINER_KINDS
        )

    def is_opener(line):
        return (
            line.startswith("no ")
            or line.startswith("isuble ")
            or line == "estilo"
            or is_container(line)
        )

    def find_end(index):
        """Find the murdong matching the opener at `index`."""
        depth = 1
        i = index + 1
        while i < len(lines):
            stripped = lines[i].strip()

            if stripped == "estilo":
                # Everything up to its next exact murdong is opaque CSS.
                i += 1
                while i < len(lines) and lines[i].strip() != "murdong":
                    i += 1
                if i >= len(lines):
                    return None
                i += 1
                continue

            if is_opener(stripped):
                depth += 1
            elif stripped == "murdong":
                depth -= 1
                if depth == 0:
                    return i
            i += 1
        return None

    def expand(segment, scoped):
        # Recurse with a local view of the source segment.
        old_lines = lines
        try:
            # This helper is defined over the original `lines`, so its
            # operations are implemented directly below instead.
            return _expand_segment(segment, scoped)
        finally:
            pass

    def _expand_segment(segment, scoped):
        result = []
        i = 0
        while i < len(segment):
            raw = segment[i]
            stripped = raw.strip()

            # CSS is opaque to Pintas control syntax.
            if stripped == "estilo":
                result.append(raw)
                i += 1
                while i < len(segment):
                    result.append(segment[i])
                    if segment[i].strip() == "murdong":
                        i += 1
                        break
                    i += 1
                else:
                    raise SyntaxError(
                        "Ti 'estilo' ket awan ti kaparehas a 'murdong'"
                    )
                continue

            # Find block boundaries against this segment, not the original
            # source, so nested controls work correctly.
            if is_opener(stripped):
                depth = 1
                j = i + 1
                while j < len(segment):
                    candidate = segment[j].strip()
                    if candidate == "estilo":
                        j += 1
                        while j < len(segment) and segment[j].strip() != "murdong":
                            j += 1
                        if j >= len(segment):
                            break
                        j += 1
                        continue
                    if is_opener(candidate):
                        depth += 1
                    elif candidate == "murdong":
                        depth -= 1
                        if depth == 0:
                            break
                    j += 1

                if j >= len(segment):
                    keyword = stripped.split()[0]
                    raise SyntaxError(
                        f"Linya {i + 1}: '{keyword}' nga awan ti kaparehas a 'murdong'"
                    )

                inner = segment[i + 1:j]

                if stripped.startswith("no "):
                    condition = _pintas_substitute(stripped[3:].strip(), scoped)
                    if _pintas_condition(condition, scoped, i + 1):
                        result.extend(_expand_segment(inner, scoped))
                elif stripped.startswith("isuble "):
                    spec = _pintas_substitute(stripped[7:].strip(), scoped)

                    if re.fullmatch(r"\d+", spec):
                        count = int(spec)
                        if count > 10000:
                            raise SyntaxError(
                                f"Linya {i + 1}: Dakkel unay ti bilang ti isuble (max 10000)"
                            )
                        for _ in range(count):
                            result.extend(_expand_segment(inner, scoped))
                    else:
                        m = re.fullmatch(
                            r"([A-Za-z_][A-Za-z0-9_]*)\s+manipud\s+(.+?)\s+agingga\s+(.+?)(?:\s+addang\s+(.+))?$",
                            spec,
                        )
                        if not m:
                            raise SyntaxError(
                                f"Linya {i + 1}: Sayop a isuble. Usaren: "
                                "'isuble i manipud 1 agingga 5' wenno 'isuble 5'"
                            )
                        var, start_s, end_s, step_s = m.groups()
                        start = _control_literal(start_s, scoped)
                        end = _control_literal(end_s, scoped)
                        step = _control_literal(step_s, scoped) if step_s else 1

                        if not all(
                            isinstance(x, (int, float)) and not isinstance(x, bool)
                            for x in (start, end, step)
                        ):
                            raise SyntaxError(
                                f"Linya {i + 1}: Dagiti bilang iti isuble ket masapul a numero"
                            )
                        if step == 0:
                            raise SyntaxError(
                                f"Linya {i + 1}: Ti addang iti isuble ket saan a mabalin a 0"
                            )

                        current = start
                        guard = 0
                        while (current <= end if step > 0 else current >= end):
                            child_vars = dict(scoped)
                            child_vars[var] = (
                                int(current) if float(current).is_integer() else current
                            )
                            result.extend(_expand_segment(inner, child_vars))
                            current += step
                            guard += 1
                            if guard > 10000:
                                raise SyntaxError(
                                    f"Linya {i + 1}: Dakkel unay ti isuble (max 10000 iterations)"
                                )
                else:
                    # Existing Pintas containers remain containers; only their
                    # contents are recursively expanded.
                    result.append(_pintas_substitute(raw, scoped))
                    result.extend(_expand_segment(inner, scoped))
                    result.append(segment[j])

                i = j + 1
                continue

            result.append(_pintas_substitute(raw, scoped))
            i += 1

        return result

    return _expand_segment(lines, variables)


def compile_pintas(source, live_reload=False):
    """Compile Pintas source into an HTML string.

    Returns (html_string, local_images) where local_images is the list
    of relative image paths referenced by `ladawan` that aren't remote
    URLs, so the caller can copy them alongside the generated HTML.

    live_reload=True appends a small polling script that reloads the
    page when the served file's Last-Modified header changes - used
    only by `--serve`, never written into a normal compiled file.
    """
    lines = _expand_pintas_controls(source.splitlines())
    out = [
        "<!DOCTYPE html>",
        '<html lang="ilo">',
        "<head>",
        '  <meta charset="UTF-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">',
    ]
    body = []
    title = "Pintas Webpage"
    css = list(BASELINE_CSS)
    local_images = []
    in_style = False
    estilo_line = None
    containers = []  # stack of {"line", "buffer", "name", "kind"} for garrapon/immuna/udi
    selected_theme = None  # last `tema` wins, same as its CSS variables do
    container_names = {}  # name -> line declared, shared across ALL container kinds
    toggle_targets = {}  # target name -> line referenced, validated after the loop
    visibility_placeholders = []  # [(token, name), ...] resolved after the loop
    next_placeholder = 0

    pending_list = None  # {"kind": "banag", "items": [...]} while grouping list items
    table = None  # {"line": int, "rows": [...]} while collecting a `listaan`

    def flush_list():
        nonlocal pending_list
        if pending_list:
            tag, cls = LIST_KINDS[pending_list["kind"]]
            emit(f'  <{tag} class="{cls}">')
            for item in pending_list["items"]:
                emit(f"    <li>{item}</li>")
            emit(f"  </{tag}>")
            pending_list = None

    def flush_table():
        nonlocal table
        if table is not None:
            rows = table["rows"]
            emit('  <div class="pintas-listaan-wrap"><table class="pintas-listaan">')
            for r_index, cells in enumerate(rows):
                tag = "th" if r_index == 0 else "td"
                emit("    <tr>" + "".join(f"<{tag}>{html.escape(c)}</{tag}>" for c in cells) + "</tr>")
            emit("  </table></div>")
            table = None

    def emit(html_line):
        """Send a body-level HTML line to the innermost open container, or body."""
        if containers:
            containers[-1]["buffer"].append(html_line)
        else:
            body.append(html_line)

    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue

        # Comments beginning with // are also accepted.
        if line.startswith("//"):
            continue

        if pending_list and not (
            not in_style and line.startswith(pending_list["kind"] + " ")
        ):
            flush_list()

        if table is not None and not line.startswith("ringgor "):
            flush_table()

        if line.startswith("panid "):
            continue

        if line.startswith("ulo "):
            title = value(line[4:])
            continue

        if line == "estilo":
            in_style = True
            estilo_line = line_no
            continue

        if line == "murdong":
            if in_style:
                in_style = False
                estilo_line = None
            elif containers:
                finished = containers.pop()
                name = finished["name"]
                tag, base_class = CONTAINER_KINDS[finished["kind"]]
                if name:
                    next_placeholder += 1
                    token = f"PINTASVIS{next_placeholder}TOKEN"
                    visibility_placeholders.append((token, name))
                    emit(f'  <{tag} class="{base_class}{token}" id="pintas-{name}">')
                else:
                    emit(f'  <{tag} class="{base_class}">')
                for inner in finished["buffer"]:
                    emit("  " + inner)
                emit(f"  </{tag}>")
            else:
                raise SyntaxError(
                    f"Linya {line_no}: 'murdong' nga awan ti nailukatan "
                    "('estilo', 'garrapon', 'immuna', 'udi' wenno 'duakolum')"
                )
            continue

        # Raw CSS passthrough must win over the container check below, so a
        # literal word like "garrapon" appearing inside an estilo block is
        # still treated as CSS text, not as a command.
        if in_style:
            css.append(css_safe(line))
            continue

        container_kind = next(
            (k for k in CONTAINER_KINDS if line == k or line.startswith(k + " ")),
            None,
        )
        if container_kind:
            name = None
            rest = line[len(container_kind):].strip()
            if rest:
                name = value(rest)
                if not NAME_PATTERN.match(name):
                    raise SyntaxError(
                        f"Linya {line_no}: Ti nagan ket letra, numero, "
                        f"wenno - _ laeng: '{name}'"
                    )
                if name in container_names:
                    raise SyntaxError(
                        f"Linya {line_no}: Naus-usar en ti nagan a '{name}' "
                        f"(immuna iti Linya {container_names[name]})"
                    )
                container_names[name] = line_no
            containers.append(
                {"line": line_no, "buffer": [], "name": name, "kind": container_kind}
            )
            continue

        list_kind = next((k for k in LIST_KINDS if line.startswith(k + " ")), None)
        if list_kind:
            item = html.escape(value(line[len(list_kind) + 1:]))
            if pending_list is None:
                pending_list = {"kind": list_kind, "items": []}
            pending_list["items"].append(item)
            continue

        if line == "listaan":
            if table is not None:
                flush_table()
            table = {"line": line_no, "rows": []}
            continue

        if line.startswith("ringgor "):
            if table is None:
                raise SyntaxError(
                    f"Linya {line_no}: Ti 'ringgor' ket masapul iti baba ti 'listaan'"
                )
            parts = re.findall(r'"(.*?)"', line[8:])
            if not parts or " ".join(parts).strip() != line[8:].strip().replace('"', ''):
                # The simple quoted-cell syntax is intentionally strict.
                pass
            if len(parts) < 2:
                raise SyntaxError(
                    f"Linya {line_no}: Ti 'ringgor' ket kasapulan iti dua wenno ad-adu a cell"
                )
            cells = [bytes(x, "utf-8").decode("unicode_escape") for x in parts]
            table["rows"].append(cells)
            continue

        if line.startswith("pagimbagan "):
            parts = re.findall(r'"(.*?)"', line[11:])
            if len(parts) != 2:
                raise SyntaxError(
                    f"Linya {line_no}: Ti 'pagimbagan' ket kasapulan iti titulo ken deskripsion"
                )
            title, desc = [bytes(x, "utf-8").decode("unicode_escape") for x in parts]
            emit(
                '  <article class="pintas-pagimbagan">'
                f'<h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p></article>'
            )
            continue

        if line.startswith("ayab "):
            parts = re.findall(r'"(.*?)"', line[5:])
            if len(parts) != 2:
                raise SyntaxError(
                    f"Linya {line_no}: Ti 'ayab' ket kasapulan iti nagan ken URL/email"
                )
            label, target = [bytes(x, "utf-8").decode("unicode_escape") for x in parts]
            if not (target.startswith(("http://", "https://", "mailto:", "tel:", "#"))):
                raise SyntaxError(
                    f"Linya {line_no}: Ti ayab ket masapul iti http://, https://, mailto:, tel: wenno #"
                )
            emit(
                f'  <a class="pintas-ayab" href="{html.escape(target, quote=True)}">'
                f'{html.escape(label)}</a>'
            )
            continue

        if line.startswith("saludsod "):
            parts = re.findall(r'"(.*?)"', line[9:])
            if len(parts) != 2:
                raise SyntaxError(f"Linya {line_no}: Ti 'saludsod' ket kasapulan iti saludsod ken sungbat")
            question, answer = [bytes(x, "utf-8").decode("unicode_escape") for x in parts]
            emit(
                '  <div class="pintas-saludsod"><details>'
                f'<summary>{html.escape(question)}</summary>'
                f'<p class="pintas-saludsod-sungbat">{html.escape(answer)}</p>'
                '</details></div>'
            )
            continue

        if line.startswith("pagbilangan "):
            parts = re.findall(r'"(.*?)"', line[12:])
            if not parts or len(parts) > 2:
                raise SyntaxError(f"Linya {line_no}: Ti 'pagbilangan' ket kasapulan iti petsa ken mabalin a nagan")
            target = bytes(parts[0], "utf-8").decode("unicode_escape")
            label = bytes(parts[1], "utf-8").decode("unicode_escape") if len(parts) == 2 else ""
            try:
                from datetime import datetime
                datetime.fromisoformat(target.replace("Z", "+00:00"))
            except ValueError:
                raise SyntaxError(f"Linya {line_no}: Ti pagbilangan ket masapul iti ISO 8601 a petsa, kas iti 2026-12-31T23:59:59")
            token = f"pintasPagbilangan{line_no}"
            label_html = f'<p>{html.escape(label)}</p>' if label else ''
            emit(
                f'  <div class="pintas-pagbilangan" id="{token}" data-target="{html.escape(target, quote=True)}">'
                f'{label_html}'
                '<div class="pintas-count-unit"><span class="pintas-count-number" data-unit="days">0</span><span class="pintas-count-label">Aldaw</span></div>'
                '<div class="pintas-count-unit"><span class="pintas-count-number" data-unit="hours">0</span><span class="pintas-count-label">Oras</span></div>'
                '<div class="pintas-count-unit"><span class="pintas-count-number" data-unit="minutes">0</span><span class="pintas-count-label">Minuto</span></div>'
                '<div class="pintas-count-unit"><span class="pintas-count-number" data-unit="seconds">0</span><span class="pintas-count-label">Segundo</span></div>'
                '</div>'
            )
            continue

        if line.startswith("pagsuratan "):
            parts = re.findall(r'"(.*?)"', line[11:])
            if len(parts) not in (1, 2):
                raise SyntaxError(f"Linya {line_no}: Ti 'pagsuratan' ket kasapulan iti nagan ken mabalin a placeholder")
            label = bytes(parts[0], "utf-8").decode("unicode_escape")
            placeholder = bytes(parts[1], "utf-8").decode("unicode_escape") if len(parts) == 2 else ""
            emit(
                f'  <label>{html.escape(label)}</label>'
                f'<input class="pintas-pagsuratan" type="text" placeholder="{html.escape(placeholder, quote=True)}">'
            )
            continue

        if line.startswith("bidyo "):
            m = YOUTUBE_ID.search(value(line[6:]))
            if not m:
                raise SyntaxError(
                    f"Linya {line_no}: Ti bidyo ket YouTube link laeng "
                    "(kas iti https://youtu.be/...)"
                )
            emit(
                '  <div class="pintas-bidyo"><iframe '
                f'src="https://www.youtube-nocookie.com/embed/{m.group(1)}" '
                'title="Bidyo" loading="lazy" allowfullscreen></iframe></div>'
            )
            continue

        if line.startswith("texto "):
            emit(f"  <h1>{html.escape(value(line[6:]))}</h1>")
        elif line.startswith("subtexto "):
            emit(f"  <h2>{html.escape(value(line[9:]))}</h2>")
        elif line.startswith("butangan "):
            emit(f"  <p>{html.escape(value(line[9:]))}</p>")
        elif line.startswith("pagpindutan "):
            m = re.match(r'pagpindutan\s+"(.*?)"(?:\s+"(.*?)")?$', line)
            if not m:
                raise SyntaxError(f"Linya {line_no}: Sayop a pagpindutan: {line}")
            label, target = m.groups()
            label = bytes(label, "utf-8").decode("unicode_escape")
            if target:
                if not NAME_PATTERN.match(target):
                    raise SyntaxError(
                        f"Linya {line_no}: Ti puntero ti pagpindutan ket letra, "
                        f"numero, wenno - _ laeng: '{target}'"
                    )
                toggle_targets[target] = line_no
                emit(
                    f"  <button onclick=\"document.getElementById('pintas-{target}')"
                    f".classList.toggle('pintas-hidden')\">{html.escape(label)}</button>"
                )
            else:
                emit(f"  <button>{html.escape(label)}</button>")
        elif line.startswith("silpo "):
            m = re.match(r'silpo\s+"(.*?)"\s+"(.*?)"$', line)
            if not m:
                raise SyntaxError(f"Linya {line_no}: Sayop a silpo: {line}")
            label, url = m.groups()
            check_link_url(url, line_no)
            if containers and containers[-1]["kind"] == "dalan":
                containers[-1]["buffer"].append(
                    f'  <a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>'
                )
            else:
                emit(
                    f'  <p><a href="{html.escape(url, quote=True)}">{html.escape(label)}</a></p>'
                )
        elif line.startswith("ladawan "):
            src = value(line[8:])
            check_image_src(src, line_no)
            if not is_remote(src):
                local_images.append(src)
            emit(
                f'  <img src="{html.escape(src, quote=True)}" '
                f'alt="Ladawan" style="max-width:100%;height:auto;">'
            )
        elif line.startswith("pagtudo "):
            emit(f'  <span class="pintas-badge">{html.escape(value(line[8:]))}</span>')
        elif line.startswith("baga "):
            emit(f'  <p class="pintas-baga">{html.escape(value(line[5:]))}</p>')
        elif line.startswith("sao "):
            m = re.match(r'sao\s+"(.*?)"(?:\s+"(.*?)")?$', line)
            if not m:
                raise SyntaxError(f"Linya {line_no}: Sayop a sao: {line}")
            quote, author = m.groups()
            quote = bytes(quote, "utf-8").decode("unicode_escape")
            inner = f"<p>{html.escape(quote)}</p>"
            if author:
                author = bytes(author, "utf-8").decode("unicode_escape")
                inner += f"<cite>\u2014 {html.escape(author)}</cite>"
            emit(f'  <blockquote class="pintas-sao">{inner}</blockquote>')
        elif line == "pila":
            emit('  <hr class="pintas-pila">')
        elif line.startswith("kolor "):
            color = value(line[6:])
            css.append(css_safe(f"body {{ background-color: {color}; }}"))
        elif line.startswith("teksto-kolor "):
            color = value(line[13:])
            css.append(css_safe(f"body {{ color: {color}; }}"))
        elif line.startswith("tema "):
            name = value(line[5:])
            if name not in THEMES:
                available = ", ".join(sorted(THEMES))
                raise SyntaxError(
                    f"Linya {line_no}: Awan ti tema a '{name}'. Adda: {available}"
                )
            css.append(theme_root_rule(name))
            selected_theme = name
        elif line == "tengnga":
            css.append("body { text-align: center; }")
        else:
            raise SyntaxError(f"Linya {line_no}: Diak maawatan: {line}")

    flush_list()
    if table is not None:
        flush_table()
    if in_style:
        raise SyntaxError(
            f"Linya {estilo_line}: 'estilo' nga awan ti kaparehas a 'murdong'"
        )
    if containers:
        raise SyntaxError(
            f"Linya {containers[-1]['line']}: '{containers[-1]['kind']}' nga awan "
            "ti kaparehas a 'murdong'"
        )
    for target, target_line in toggle_targets.items():
        if target not in container_names:
            raise SyntaxError(
                f"Linya {target_line}: Awan ti garrapon (wenno immuna/udi) "
                f"nga addaan iti nagan a '{target}'"
            )

    out.append(f"  <title>{html.escape(title)}</title>")
    if selected_theme:
        out += theme_font_links(selected_theme)
    if css:
        out += ["  <style>"]
        out += ["    " + rule for rule in css]
        out += ["  </style>"]
    out += ["</head>", "<body>"]
    out += body
    if any('class="pintas-pagbilangan"' in line for line in body):
        out.append("  <script>document.querySelectorAll('.pintas-pagbilangan').forEach(function(el){var target=new Date(el.dataset.target).getTime();function tick(){var d=Math.max(0,target-Date.now()),s=Math.floor(d/1000),days=Math.floor(s/86400);s%=86400;var hours=Math.floor(s/3600);s%=3600;var mins=Math.floor(s/60);s%=60;el.querySelector('[data-unit=days]').textContent=days;el.querySelector('[data-unit=hours]').textContent=hours;el.querySelector('[data-unit=minutes]').textContent=mins;el.querySelector('[data-unit=seconds]').textContent=s;if(d<=0)clearInterval(timer)}var timer=setInterval(tick,1000);tick()});</script>")
    if live_reload:
        out.append(LIVE_RELOAD_SCRIPT)
    out += ["</body>", "</html>"]
    result = "\n".join(out)
    for token, name in visibility_placeholders:
        result = result.replace(token, " pintas-hidden" if name in toggle_targets else "")
    return result, local_images


def copy_local_images(local_images, source_dir, output_dir):
    """Copy each referenced local image next to the compiled HTML.

    Missing images are reported but don't stop the build - the HTML
    still compiles, it will just have a broken <img> tag, same as if
    you forgot to include an asset in a regular static site.
    """
    output_root = output_dir.resolve()
    for rel_src in local_images:
        src_path = (source_dir / rel_src).resolve()
        if not src_path.is_file():
            print(f"Babala: hindi nakita ang larawan: {rel_src}")
            continue
        dest_path = (output_dir / rel_src).resolve()
        if dest_path == src_path:
            # Output sits next to the source (or the path lines up): the
            # image is already where the HTML will look for it.
            continue
        try:
            dest_path.relative_to(output_root)
        except ValueError:
            # Never write outside the output folder (e.g. "../x.png").
            print(f"Babala: ti ladawan ket adda iti ruar ti output folder, "
                  f"saan a nakopia: {rel_src}")
            continue
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src_path, dest_path)


def build(source_path, output_path, live_reload=False):
    """Compile one .pintas file to HTML and copy its local images.

    Shared by a normal one-shot run and each recompile inside --serve.
    """
    source = source_path.read_text(encoding="utf-8")
    result, local_images = compile_pintas(source, live_reload=live_reload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(result, encoding="utf-8")
    copy_local_images(local_images, source_path.parent, output_path.parent)


def _serve_with_handler(handler, port):
    """Bind `handler` to the first free port from `port` upward (20 tries),
    serving in a background thread. Returns the port actually bound.
    """
    for candidate in range(port, port + 20):
        try:
            httpd = http.server.ThreadingHTTPServer(("localhost", candidate), handler)
        except OSError:
            continue
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return candidate
    raise OSError(f"Awan ti nawaya a port iti nagbaetan ti {port} ken {port + 19}")


def start_server(directory, port):
    """Serve `directory` over local HTTP, trying a few ports if busy.

    Plain stdlib static file serving - this is what gives the page an
    accurate Last-Modified header for free, which LIVE_RELOAD_SCRIPT
    polls. Returns the port actually bound.
    """
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(directory)
    )
    return _serve_with_handler(handler, port)


def watch_and_serve(source_path, output_path, port):
    """Serve output_path's folder, open a browser tab, and recompile
    source_path whenever it changes - the reload script in the page
    picks up the change automatically. Stop with Ctrl+C.
    """
    served_port = start_server(output_path.parent, port)
    url = f"http://localhost:{served_port}/{output_path.name}"
    print(f"Agserserbi iti {url} (Ctrl+C tapno agsardeng)")
    # Backgrounded: on some setups a browser launcher can block instead
    # of returning immediately, which must never freeze the watch loop.
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()

    last_mtime = source_path.stat().st_mtime
    try:
        while True:
            time.sleep(0.5)
            try:
                mtime = source_path.stat().st_mtime
            except OSError:
                continue
            if mtime == last_mtime:
                continue
            last_mtime = mtime
            try:
                build(source_path, output_path, live_reload=True)
                print(f"Na-update: {source_path} -> {output_path}")
            except (OSError, SyntaxError) as e:
                print(f"Sayop: {e}")
    except KeyboardInterrupt:
        print("\nNagsardeng.")


def main():
    parser = argparse.ArgumentParser(
        description="I-compile dagiti .pintas a files nga agbalin a webpage."
    )
    parser.add_argument("source", help="Ti input a .pintas file")
    parser.add_argument(
        "output",
        nargs="?",
        default="output/index.html",
        help="Ti pagturungan nga .html file (kasapulan: output/index.html)",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Agserbi iti lokal a webpage ken automatiko nga i-refresh "
        "no adda mabaliwan iti source file",
    )
    parser.add_argument(
        "--editor",
        action="store_true",
        help="Ilukat ti browser-based nga editor nga adda toolbar ken "
        "agango a preview - saanen a masapul nga isuratmo a mismo ti "
        "linya ti Pintas",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port a pagserbian iti --serve/--editor (kasapulan: 8000)",
    )
    args = parser.parse_args()

    source_path = Path(args.source)
    output_path = Path(args.output)

    if args.editor:
        from pintas_editor import run_editor  # only the editor needs the web UI

        run_editor(source_path, output_path, args.port)
        return

    try:
        build(source_path, output_path, live_reload=args.serve)
    except (OSError, SyntaxError) as e:
        print(f"Sayop: {e}")
        raise SystemExit(1)

    print(f"Nabuo: {output_path}")
    if args.serve:
        watch_and_serve(source_path, output_path, args.port)


if __name__ == "__main__":
    main()
