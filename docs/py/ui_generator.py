#!/usr/bin/env python3
"""
UI Generator for Pintas - separate software, not part of pintas.py.
Part of the Pintas project by James Kenneth Ines.

One click (or one command) produces a COMPLETE, ready-to-use Pintas page
whose look is unique and whose name is a Philippine mythical creature -
or a combination of two:

    Bakunawa            Ibong Adarna            Bakunawa-adarna

What "unique UI" means here, precisely. Each generated UI is a seeded
combination of independent choices that are then merged into one .pintas
file, so the pieces always fit together:

- NAME      a creature (or a hybrid of two). The creature also steers the
            design: its mood picks the hue family, light/dark preference,
            font pairing and shape language. A hybrid takes its colours
            and fonts from the first creature and its signature accent
            colour from the second.
- PALETTE   built with theme_generator.py's contrast tools and VERIFIED
            (text 7:1, muted 4.5:1, button text 4.5:1, links 3:1).
- PATTERN   a kusikus/Truchet tile from pattern_generator.py, placed on
            the page, the hero or the cards.
- FAVICON   a monogram of the name's first letter in the accent colour
            (made by favicon_generator.py), added with `ladawan-ulo`.
- SIGIL     a small round emblem drawn from the same tile family, so every
            UI carries its own badge.
- LAYOUT    one of four page archetypes, with optional sections switched
            on or off, plus nav / hero / card styling variants.

Everything is written as ordinary Pintas commands plus one `estilo`
block, so the output compiles with an unmodified pintas.py. Images are
generated in-file (data: URIs): no external assets, no network needed.

Names are curated, not invented: every creature below is a documented
figure of Philippine folklore (Ilokano ones are marked). Like the theme
generator, this script never makes up a plausible-sounding word.

Usage:
    python ui_generator.py                         # one random UI
    python ui_generator.py --seed 7 --count 3
    python ui_generator.py --name Bakunawa-adarna  # choose the name
    python ui_generator.py --gui                   # click "Baro a UI" in the browser
    python ui_generator.py --list-names
"""

import argparse
import base64
import colorsys  # noqa: F401  (kept importable for callers extending palettes)
import functools
import http.server
import json
import random
import re
import sys
import threading
import webbrowser
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import favicon_generator as fg  # noqa: E402
import pattern_generator as pg  # noqa: E402
import theme_generator as tg  # noqa: E402
from pintas import THEMES, compile_pintas, root_rule_from_theme  # noqa: E402


# ---------------------------------------------------------------------------
# Creatures. Curated, documented figures of Philippine folklore.
#   short    : the lowercase-able token used inside hybrid names
#   epithet  : one factual clause, used in the page copy
#   hue      : (lo, hi) base colour family in degrees
#   accent   : (lo, hi) signature accent hue when used on its own
#   dark     : probability the UI is a dark-mode design
#   shape    : index into theme_generator.STRUCTURE_PRESETS
#   fonts    : indexes into theme_generator.FONT_PAIRINGS
#   styles   : pattern looks that suit the creature
# Bakunawa is Bisaya rather than Tagalog/Ilokano; it is included because
# it was asked for by name, and its origin is labelled honestly.
# ---------------------------------------------------------------------------

CREATURES = [
    dict(display="Bakunawa", short="Bakunawa", origin="Bisaya",
         epithet="the moon-eating sea serpent",
         hue=(228, 262), accent=(40, 52), dark=0.9, shape=1, fonts=(6, 0),
         styles=("diamonds", "ribbon")),
    dict(display="Ibong Adarna", short="Adarna", origin="Tagalog",
         epithet="the enchanted bird whose songs heal",
         hue=(285, 320), accent=(165, 185), dark=0.35, shape=3, fonts=(4, 6, 0),
         styles=("curves", "ribbon")),
    dict(display="Tikbalang", short="Tikbalang", origin="Tagalog",
         epithet="the tall, horse-headed trickster who leads travelers astray",
         hue=(95, 130), accent=(18, 30), dark=0.6, shape=2, fonts=(5, 1),
         styles=("diamonds", "curves")),
    dict(display="Kapre", short="Kapre", origin="Tagalog",
         epithet="the tree-dwelling giant who smokes tobacco",
         hue=(110, 150), accent=(30, 42), dark=0.8, shape=0, fonts=(3, 0),
         styles=("blobs", "curves")),
    dict(display="Manananggal", short="Manananggal", origin="Tagalog",
         epithet="the night-flying aswang that severs its own body",
         hue=(346, 360), accent=(0, 10), dark=0.95, shape=2, fonts=(6, 4),
         styles=("diamonds", "ribbon")),
    dict(display="Batibat", short="Batibat", origin="Ilokano",
         epithet="the tree-dwelling spirit that haunts sleepers with nightmares",
         hue=(25, 38), accent=(100, 120), dark=0.75, shape=0, fonts=(0, 3),
         styles=("blobs", "curves")),
    dict(display="Marukos", short="Marukos", origin="Ilokano",
         epithet="the crossroads demon of Ilokano legend",
         hue=(12, 24), accent=(200, 215), dark=0.7, shape=2, fonts=(5, 1),
         styles=("diamonds", "ribbon")),
    dict(display="Lakay", short="Lakay", origin="Ilokano",
         epithet="the dwarf-like mound dweller, kin to the nuno sa punso",
         hue=(35, 45), accent=(8, 16), dark=0.3, shape=0, fonts=(3, 4),
         styles=("blobs", "curves")),
    dict(display="Pugot", short="Pugot", origin="Ilokano",
         epithet="the towering night spirit, frightening but seldom harmful",
         hue=(215, 235), accent=(190, 200), dark=0.95, shape=1, fonts=(1, 5),
         styles=("ribbon", "diamonds")),
    dict(display="Nuno sa Punso", short="Nuno", origin="Tagalog",
         epithet="the dwarf of the termite mound",
         hue=(20, 32), accent=(85, 105), dark=0.3, shape=0, fonts=(3, 7),
         styles=("blobs", "curves")),
    dict(display="Santelmo", short="Santelmo", origin="Tagalog",
         epithet="the wandering fireball spirit",
         hue=(10, 22), accent=(35, 48), dark=0.95, shape=1, fonts=(5, 6),
         styles=("blobs", "ribbon")),
    dict(display="Diwata", short="Diwata", origin="Tagalog",
         epithet="the guardian spirit of forests and mountains",
         hue=(300, 330), accent=(150, 170), dark=0.1, shape=3, fonts=(7, 3, 4),
         styles=("curves", "ribbon")),
    dict(display="Lambana", short="Lambana", origin="Tagalog",
         epithet="the tiny fairy of Tagalog lore",
         hue=(170, 190), accent=(300, 320), dark=0.2, shape=3, fonts=(7, 2),
         styles=("curves", "blobs")),
    dict(display="Duwende", short="Duwende", origin="Tagalog",
         epithet="the small, magical spirit of the land",
         hue=(0, 12), accent=(95, 110), dark=0.3, shape=0, fonts=(3, 7),
         styles=("blobs", "diamonds")),
    dict(display="Sirena", short="Sirena", origin="Tagalog",
         epithet="the mermaid of Philippine waters",
         hue=(180, 195), accent=(330, 345), dark=0.25, shape=3, fonts=(7, 2),
         styles=("curves", "ribbon")),
    dict(display="Siyokoy", short="Siyokoy", origin="Tagalog",
         epithet="the scaled, sea-dwelling humanoid",
         hue=(195, 215), accent=(140, 160), dark=0.85, shape=1, fonts=(1, 2),
         styles=("ribbon", "diamonds")),
    dict(display="Bungisngis", short="Bungisngis", origin="Tagalog",
         epithet="the one-eyed, laughing giant",
         hue=(45, 60), accent=(10, 20), dark=0.2, shape=2, fonts=(2, 7),
         styles=("blobs", "diamonds")),
]

HYBRID_CHANCE = 0.4
LAYOUTS = ("kaharian", "kwento", "paglusad", "tindahan")


def list_names():
    return [c["display"] for c in CREATURES]


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def hybrid_name(a, b):
    """Bakunawa + Ibong Adarna -> 'Bakunawa-adarna'."""
    return f"{a['short'].capitalize()}-{b['short'].lower()}"


def find_creature(token):
    """Match a display name, short token or slug, case-insensitively."""
    key = slugify(token)
    for c in CREATURES:
        if key in (slugify(c["display"]), slugify(c["short"])):
            return c
    return None


def parse_name(text):
    """Turn a requested name into (creature_a, creature_b_or_None).

    Accepts 'Bakunawa', 'Ibong Adarna', 'Bakunawa-adarna', 'kapre-nuno'.
    """
    text = text.strip()
    if not text:
        raise ValueError("Awan ti nagan.")
    whole = find_creature(text)
    if whole:
        return whole, None
    parts = [p for p in text.split("-") if p.strip()]
    found = [find_creature(p) for p in parts]
    if len(parts) == 2 and all(found) and found[0] is not found[1]:
        return found[0], found[1]
    raise ValueError(
        f"Diak am-ammo ti '{text}'. Usaren ti maysa wenno dua a nagan manipud: "
        + ", ".join(list_names())
    )


def pick_creatures(rng):
    if rng.random() < HYBRID_CHANCE:
        a, b = rng.sample(CREATURES, 2)
        return a, b
    return rng.choice(CREATURES), None


# ---------------------------------------------------------------------------
# Palette: same verified-contrast approach as theme_generator.py, but the
# hues come from the creature instead of a random roll.
# ---------------------------------------------------------------------------

def mix_hex(a, b, weight_a):
    """Blend hex colour `a` toward `b` (weight_a is a's share)."""
    ca, cb = tg.hex_to_rgb(a), tg.hex_to_rgb(b)
    return tg.rgb_to_hex(
        [x * weight_a + y * (1 - weight_a) for x, y in zip(ca, cb)]
    )


def verify_ui_palette(p):
    """theme_generator's three checks, plus two the UI needs: links
    (accent on background) and the hover state of buttons."""
    checks = dict(tg.verify_palette(p))
    checks["accent/bg >= 3:1"] = tg.contrast_ratio(p["accent"], p["bg"]) >= 3.0
    checks["accent/card >= 3:1"] = tg.contrast_ratio(p["accent"], p["card-bg"]) >= 3.0
    checks["hover/button-text >= 4.5:1"] = (
        tg.contrast_ratio(p["accent-hover"], p["button-text"]) >= 4.5
    )
    return checks


def _palette_attempt(rng, a, b):
    dark = rng.random() < a["dark"]
    base_hue = rng.uniform(*a["hue"])
    accent_hue = rng.uniform(*(b["hue"] if b else a["accent"]))

    if dark:
        bg_l = rng.uniform(0.05, 0.09)
        bg = tg.hsl_to_hex(base_hue, 0.35, bg_l)
        card_bg = tg.hsl_to_hex(base_hue, 0.30, bg_l + 0.045)
        text = tg.nudge_for_contrast(base_hue, 0.08, bg, 7.0, 0.92, +0.02)
        muted = tg.nudge_for_contrast(base_hue, 0.12, bg, 4.5, 0.70, +0.02)
        acc_l0, acc_step = rng.uniform(0.55, 0.68), +0.02
    else:
        bg = tg.hsl_to_hex(base_hue, rng.uniform(0.30, 0.50), rng.uniform(0.95, 0.975))
        card_bg = tg.hsl_to_hex(base_hue, 0.30, 0.99)
        text = tg.nudge_for_contrast(base_hue, 0.15, bg, 7.0, 0.12, -0.02)
        muted = tg.nudge_for_contrast(base_hue, 0.15, bg, 4.5, 0.40, -0.02)
        acc_l0, acc_step = rng.uniform(0.36, 0.50), -0.02

    sat = rng.uniform(0.55, 0.85)
    accent = tg.nudge_for_contrast(accent_hue, sat, bg, 3.0, acc_l0, acc_step)
    button_text = tg.best_button_text(accent)
    # hover moves away from the button text so their contrast never drops
    r, g, bl = [c / 255 for c in tg.hex_to_rgb(accent)]
    _, l, s = colorsys.rgb_to_hls(r, g, bl)
    l2 = max(0.05, l - 0.08) if button_text == "#ffffff" else min(0.95, l + 0.06)
    accent_hover = tg.hsl_to_hex(accent_hue, s, l2)

    font_h, font_b, font_url = tg.FONT_PAIRINGS[rng.choice(a["fonts"])]
    shape_idx = rng.choice((a["shape"], (b or a)["shape"]))
    structure = dict(tg.STRUCTURE_PRESETS[shape_idx])
    glow = structure.pop("glow")
    ar, ag, ab = tg.hex_to_rgb(accent)
    if glow:
        card_shadow = f"0 0 22px rgba({ar},{ag},{ab},0.28)"
        button_shadow = f"0 0 14px rgba({ar},{ag},{ab},0.45)"
    else:
        card_shadow = "0 2px 10px rgba(0,0,0,0.35)" if dark else "0 1px 3px rgba(0,0,0,0.08)"
        button_shadow = "none"

    return {
        "bg": bg, "text": text, "muted": muted, "accent": accent,
        "accent-hover": accent_hover, "card-bg": card_bg,
        "button-text": button_text,
        "font-heading": font_h, "font-body": font_b, "font-url": font_url,
        **structure,
        "card-shadow": card_shadow, "button-shadow": button_shadow,
        "_dark": dark, "_hue": round(base_hue), "_accent_hue": round(accent_hue),
    }


def make_palette(rng, a, b):
    """Retry until every contrast check passes (they almost always do on
    the first few tries; the cap keeps it terminating)."""
    last = None
    for _ in range(200):
        last = _palette_attempt(rng, a, b)
        if all(verify_ui_palette(last).values()):
            return last
    raise ValueError("Awan ti nagballigi a palette. Padasem manen.")


def theme_palette(p):
    """The palette without the generator's private '_' bookkeeping keys."""
    return {k: v for k, v in p.items() if not k.startswith("_")}


# ---------------------------------------------------------------------------
# Pattern, sigil and look (nav / hero / cards) - all written as plain CSS.
# ---------------------------------------------------------------------------

def make_pattern_css(rng, p, a, b):
    """A tileable kusikus background on the page, the hero or the cards."""
    target = rng.choice(("body", "hero", "cards"))
    selector = {"body": "body", "hero": ".pintas-immuna",
                "cards": ".garrapon, .pintas-pagimbagan"}[target]
    ground = p["bg"] if target == "body" else p["card-bg"]
    seed = rng.randrange(10**9)
    recipe = pg.random_recipe(seed)
    recipe["style"] = rng.choice((b or a)["styles"])
    # Text sits right on top of the hero and the cards, so the pattern is
    # kept fainter there than on the bare page background.
    strength = pg.STYLE_STRENGTH[recipe["style"]] * {"body": 1.0, "hero": 0.5, "cards": 0.75}[target]
    line = mix_hex(p["accent"], ground, strength)
    svg, unit = pg.generate_pattern_svg(seed, line_color=line, bg_color=ground, **recipe)
    css = [
        f"{selector} {{",
        f'  background-image: url("{pg.as_data_uri(svg)}");',
        f"  background-size: {unit}px {unit}px;",
        "  background-repeat: repeat;",
        "}",
    ]
    return target, recipe["style"], css


def sigil_svg(seed, accent, ink):
    """A round emblem: a symmetric weaving tile clipped to a circle."""
    rng = random.Random(f"sigil:{seed}")
    inner, unit = pg.generate_pattern_svg(
        seed, 6, ink, accent, tile_size=20, stroke_width=3,
        style=rng.choice(("curves", "diamonds", "ribbon")), symmetric=True,
    )
    h = unit / 2
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{unit}" height="{unit}" '
        f'viewBox="0 0 {unit} {unit}"><defs><clipPath id="s">'
        f'<circle cx="{h}" cy="{h}" r="{h - 3}"/></clipPath></defs>'
        f'<g clip-path="url(#s)">{inner}</g>'
        f'<circle cx="{h}" cy="{h}" r="{h - 3}" fill="none" stroke="{ink}" '
        f'stroke-width="3"/></svg>'
    )


def make_look(rng, p, pattern_target):
    """Structural variety on top of the palette. Only existing Pintas
    class names are targeted, and no CSS line starts with '#'
    (Pintas treats such lines as comments even inside `estilo`)."""
    width = rng.choice((720, 860, 980))
    hero = rng.choice(("plain", "banner", "framed"))
    if pattern_target == "hero" and hero == "banner":
        hero = "plain"  # the pattern already dresses the hero
    nav = rng.choice(("bar", "pills", "underline"))
    cards = rng.choice(("raised", "outlined", "edge"))
    flourish = rng.random() < 0.7

    css = [f"body {{ max-width: {width}px; }}"]
    if hero == "banner":
        css.append(
            ".pintas-immuna { background: linear-gradient(135deg, "
            "color-mix(in srgb, var(--pintas-accent) 24%, var(--pintas-card-bg)), "
            "var(--pintas-card-bg) 70%); }"
        )
    elif hero == "framed":
        css.append(
            ".pintas-immuna { border: 2px solid var(--pintas-accent); "
            "border-radius: var(--pintas-card-radius); margin: 0 0 2rem 0; }"
        )
    if nav == "pills":
        css += [
            ".pintas-dalan a { padding: 0.3rem 0.95rem; border-radius: 999px; }",
            ".pintas-dalan a:hover { background: var(--pintas-accent); "
            "color: var(--pintas-button-text); }",
        ]
    elif nav == "underline":
        css += [
            ".pintas-dalan a { padding-bottom: 2px; border-bottom: 2px solid transparent; }",
            ".pintas-dalan a:hover { border-bottom-color: var(--pintas-accent); }",
        ]
    if cards == "outlined":
        css.append(".garrapon, .pintas-pagimbagan { box-shadow: none; "
                   "border: 1.5px solid var(--pintas-accent); }")
    elif cards == "edge":
        css.append(".garrapon, .pintas-pagimbagan { border-top: 5px solid var(--pintas-accent); }")
    if flourish:
        css.append(
            ".pintas-immuna h1::after { content: \"\"; display: block; width: 64px; "
            "height: 4px; margin: 0.7rem auto 0; background: var(--pintas-accent); "
            "border-radius: var(--pintas-radius); }"
        )
    return dict(width=width, hero=hero, nav=nav, cards=cards, flourish=flourish), css


# ---------------------------------------------------------------------------
# Page sections. Each returns Pintas source lines. ASCII only on purpose:
# the compiler decodes quoted strings with unicode_escape, which garbles
# characters like the peso sign.
# ---------------------------------------------------------------------------

FEATURE_POOL = [
    ("Napardas", "Simple commands compile into clean HTML."),
    ("Napintas", "Themes and responsive cards make pages look polished."),
    ("Nalaka", "Write a few lines and get a complete, responsive page."),
    ("Naisangsangayan", "Every generated look is different, from colors to shapes."),
    ("Natalged", "Plain HTML and CSS, with nothing extra to maintain."),
    ("Naimbag", "Readable on phones, tablets and desktops."),
]
TAGLINES = [
    "A legend from Philippine folklore, turned into a page.",
    "Aramiden ti napintas a webpage babaen iti Ilokano.",
    "Old stories, fresh design.",
    "Made in Pintas, named after a creature of the islands.",
]
NAV_LABELS = {
    "features": "Features", "kwento": "Kwento", "pricing": "Pricing",
    "ladawan": "Ladawan", "faq": "FAQ", "kontak": "Kontak",
}


def sec_nav(names):
    lines = ["dalan", 'silpo "Umuna" "#pintas-umuna"']
    lines += [f'silpo "{NAV_LABELS[n]}" "#pintas-{n}"' for n in names]
    lines.append("murdong")
    return lines


def sec_hero(ctx, first_anchor, countdown):
    lines = [
        "immuna umuna",
        f'pagtudo "{ctx["origin_label"]}"',
        f'texto "{ctx["name"]}"',
        f'subtexto "{ctx["tagline"]}"',
        f'butangan "{ctx["blurb"]}"',
        f'ayab "Learn More" "#pintas-{first_anchor}"',
        'ayab "Contact Us" "mailto:hello@example.com"',
    ]
    if countdown:
        lines.append(f'pagbilangan "{ctx["launch"]}" "Launching soon"')
    lines.append("murdong")
    return lines


def sec_features(ctx, rng):
    picks = rng.sample(FEATURE_POOL, rng.choice((2, 4)))
    lines = ["garrapon features", 'pagtudo "FEATURES"',
             f'texto "Why {ctx["name"]}?"', "duakolum"]
    lines += [f'pagimbagan "{t}" "{d}"' for t, d in picks]
    lines += ["murdong", "murdong"]
    return lines


def sec_kwento(ctx, rng):
    items = rng.sample([
        "Complete pages from a handful of short commands",
        "Colors and fonts checked for readable contrast",
        "A background pattern woven from the kusikus motif",
        "Works offline: no images or scripts to download",
    ], 3)
    lines = ["garrapon kwento", 'pagtudo "KWENTO"', f'texto "The story of {ctx["name"]}"',
             f'butangan "{ctx["blurb"]}"']
    lines += [f'naaramid {i}' for i in items]
    lines += ['sao "Write a short, memorable line here." "Your name"', "murdong"]
    return lines


def sec_pricing(ctx, rng):
    return [
        "garrapon pricing", 'texto "Pricing"', "listaan",
        'ringgor "Plano" "Presyo" "Kasapulan"',
        'ringgor "Basic" "Libre" "Umuna a proyekto"',
        'ringgor "Pro" "PHP 499" "Ad-adu a features"',
        'ringgor "Business" "PHP 999" "Para kadagiti team"',
        "pila", "murdong",
    ]


def sec_faq(ctx, rng):
    lines = ["garrapon faq", 'pagtudo "FAQ"', 'texto "Questions"',
             f'saludsod "Ania ti {ctx["name"]}?" "{ctx["blurb"]}"',
             'saludsod "Can I change the text?" "Yes. Every word lives in the .pintas file."']
    if rng.random() < 0.6:
        lines.append('saludsod "Does it need the internet?" '
                     '"Only for the web fonts. The pattern and images are built in."')
    lines.append("murdong")
    return lines


def sec_ladawan(ctx, rng, p):
    lines = ["ladawanan ladawan"]
    for _ in range(3):
        seed = rng.randrange(10**9)
        recipe = pg.random_recipe(seed)
        recipe["grid_size"], recipe["tile_size"] = 4, 30
        line = mix_hex(p["accent"], p["card-bg"], 0.6)
        svg, _ = pg.generate_pattern_svg(seed, line_color=line, bg_color=p["card-bg"], **recipe)
        lines.append(f'ladawan "{pg.as_data_uri(svg)}"')
    lines.append("murdong")
    return lines


def sec_kontak(ctx, rng):
    return [
        "garrapon kontak", 'texto "Get in touch"',
        'butangan "Tell us about your project."',
        'pagsuratan "Naganmo" "Isurat ditoy ti nagan mo"',
        'pagsuratan "Email" "you@example.com"',
        'ayab "Email Us" "mailto:hello@example.com"',
        'ayab "Call Us" "tel:+639000000000"',
        "murdong",
    ]


def sec_footer(ctx):
    return ["udi", 'butangan "Naaramid babaen ti Pintas"',
            f'butangan "{ctx["name"]} - UI {ctx["seed"]}"', "murdong"]


def build_layout(rng, archetype, ctx, p):
    """Return the page body as Pintas lines for one archetype."""
    plan = {  # (required sections, optional sections), in page order
        "kaharian": (["features", "pricing"], ["kwento", "faq", "ladawan", "kontak"]),
        "kwento": (["kwento", "ladawan"], ["features", "faq", "kontak"]),
        "paglusad": (["features", "faq"], ["kwento", "kontak"]),
        "tindahan": (["pricing", "ladawan"], ["features", "faq", "kontak"]),
    }[archetype]
    required, optional = plan
    chosen = list(required) + rng.sample(optional, rng.randint(1, len(optional)))
    order = ["features", "kwento", "pricing", "ladawan", "faq", "kontak"]
    sections = [s for s in order if s in chosen]

    builders = {
        "features": lambda: sec_features(ctx, rng),
        "kwento": lambda: sec_kwento(ctx, rng),
        "pricing": lambda: sec_pricing(ctx, rng),
        "ladawan": lambda: sec_ladawan(ctx, rng, p),
        "faq": lambda: sec_faq(ctx, rng),
        "kontak": lambda: sec_kontak(ctx, rng),
    }
    lines = []
    if archetype != "paglusad" or rng.random() < 0.5:
        lines += sec_nav(sections) + [""]
    lines += sec_hero(ctx, sections[0], countdown=(archetype == "paglusad")) + [""]
    for s in sections:
        lines += builders[s]() + [""]
    lines += sec_footer(ctx)
    return lines, sections


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def donor_theme(palette):
    """A shipped theme with the same Google Fonts, so `tema` loads them."""
    return next((n for n, t in THEMES.items() if t["font-url"] == palette["font-url"]), "puraw")


def generate_ui(seed=None, name=None, today=None):
    """Generate one complete UI. Returns a dict with the .pintas source,
    the compiled HTML and the choices that produced them. Reproducible:
    the same seed (and name) always gives the same UI."""
    if seed is None:
        seed = random.SystemRandom().randrange(10**9)
    rng = random.Random(seed)
    a, b = parse_name(name) if name else pick_creatures(rng)
    if name:  # keep the random stream aligned whether or not a name was forced
        pick_creatures(rng)

    display = hybrid_name(a, b) if b else a["display"]
    origins = [a["origin"]] + ([b["origin"]] if b else [])
    origin_label = " + ".join(dict.fromkeys(origins)) + (" legend" if not b else " hybrid")
    blurb = (
        f"{a['display']} meets {b['display']}: {a['epithet']}, crossed with {b['epithet']}."
        if b else f"{a['display']}: {a['epithet']}."
    )
    launch = ((today or date.today()) + timedelta(days=45)).strftime("%Y-%m-%dT23:59:59")
    ctx = dict(name=display, seed=seed, origin_label=origin_label, blurb=blurb,
               tagline=rng.choice(TAGLINES), launch=launch)

    palette = make_palette(rng, a, b)
    pattern_target, pattern_style, pattern_css = make_pattern_css(rng, palette, a, b)
    look, look_css = make_look(rng, palette, pattern_target)
    sigil = sigil_svg(rng.randrange(10**9), palette["accent"], palette["button-text"])
    sigil_css = [
        ".pintas-immuna::before { content: \"\"; display: block; width: 88px; "
        "height: 88px; margin: 0 auto 1rem; background: url(\""
        + pg.as_data_uri(sigil) + "\") center / contain no-repeat; }"
    ]
    archetype = rng.choice(LAYOUTS)
    body_lines, sections = build_layout(rng, archetype, ctx, palette)

    # Drawn last from the random stream, so adding it changed no earlier choice.
    favicon = fg.generate_favicon(display, palette["accent"], seed=rng.randrange(10**9),
                                  style="monogram", sizes=(32,))
    css = [root_rule_from_theme(theme_palette(palette))] + look_css + pattern_css + sigil_css
    source = "\n".join(
        [
            f"# {display} - generated by ui_generator.py (Pintas, by James Kenneth Ines)",
            f"# seed {seed} | {origin_label} | layout {archetype} | pattern {pattern_style} on {pattern_target}",
            f'panid "{display}"',
            f'ulo "{display}"',
            f'tema "{donor_theme(palette)}"',
            favicon["snippet_inline"],
            "estilo",
            *css,
            "murdong",
            "",
            *body_lines,
            "",
        ]
    )
    html, _ = compile_pintas(source)  # the REAL compiler; raises SyntaxError if wrong
    return dict(
        name=display, slug=slugify(display), seed=seed,
        creatures=[a["display"]] + ([b["display"]] if b else []),
        origin=origin_label, blurb=blurb, layout=archetype, sections=sections,
        pattern=dict(target=pattern_target, style=pattern_style), look=look,
        palette=theme_palette(palette), dark=palette["_dark"],
        checks=verify_ui_palette(palette), source=source, html=html,
    )


def write_ui(ui, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = ui["slug"]
    if (out_dir / f"{stem}.pintas").exists():
        stem = f"{stem}-{ui['seed']}"
    src_path, html_path = out_dir / f"{stem}.pintas", out_dir / f"{stem}.html"
    src_path.write_text(ui["source"], encoding="utf-8")
    html_path.write_text(ui["html"], encoding="utf-8")
    return src_path, html_path


# ---------------------------------------------------------------------------
# The click-to-generate window: a tiny local web page, no dependencies.
# ---------------------------------------------------------------------------

def gui_payload(payload):
    """POST /generate body -> JSON-able reply. Kept separate from the
    HTTP handler so it can be tested directly."""
    seed = payload.get("seed")
    name = (payload.get("name") or "").strip() or None
    try:
        ui = generate_ui(seed=int(seed) if seed not in (None, "") else None, name=name)
    except (ValueError, SyntaxError) as e:
        return {"ok": False, "error": str(e)}
    p = ui["palette"]
    return {
        "ok": True, "name": ui["name"], "slug": ui["slug"], "seed": ui["seed"],
        "origin": ui["origin"], "blurb": ui["blurb"], "layout": ui["layout"],
        "swatches": [p["bg"], p["card-bg"], p["accent"], p["text"]],
        "source": ui["source"], "html": ui["html"],
    }


GUI_PAGE = r"""<!DOCTYPE html>
<html lang="ilo"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pintas UI Generator</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
         background: #14161c; color: #eceef4; display: flex; flex-direction: column; height: 100vh; }
  header { padding: 14px 18px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
           border-bottom: 1px solid #2a2e3a; }
  h1 { font-size: 1.05rem; margin: 0 auto 0 0; }
  input { font: inherit; padding: 9px 12px; border-radius: 8px; border: 1px solid #3a3f4e;
          background: #1d2029; color: inherit; width: 220px; max-width: 100%; }
  button { font: inherit; font-weight: 600; padding: 9px 16px; border-radius: 8px; border: 0;
           background: #e8b84a; color: #1a1408; cursor: pointer; }
  button.ghost { background: #232733; color: #eceef4; border: 1px solid #3a3f4e; }
  button:disabled { opacity: .5; cursor: default; }
  .bar { padding: 10px 18px; display: flex; flex-wrap: wrap; gap: 10px; align-items: center;
         border-bottom: 1px solid #2a2e3a; min-height: 54px; }
  .name { font-weight: 700; font-size: 1.1rem; }
  .meta { color: #9aa1b5; font-size: .85rem; }
  .sw { display: inline-block; width: 18px; height: 18px; border-radius: 50%;
        border: 1px solid #ffffff44; margin-right: 3px; vertical-align: middle; }
  .hist { display: flex; gap: 6px; flex-wrap: wrap; padding: 8px 18px; border-bottom: 1px solid #2a2e3a; }
  .hist:empty { display: none; }
  .chip { padding: 4px 10px; font-size: .8rem; background: #232733; color: #eceef4;
          border: 1px solid #3a3f4e; border-radius: 999px; cursor: pointer; }
  .chip.on { border-color: #e8b84a; }
  main { flex: 1; min-height: 0; position: relative; }
  iframe, textarea { position: absolute; inset: 0; width: 100%; height: 100%; border: 0; }
  iframe { background: #fff; }
  textarea { background: #10121a; color: #d6dae6; padding: 14px; font: .85rem/1.5 ui-monospace, Consolas, monospace;
             resize: none; display: none; }
  .err { color: #ff8e8e; padding: 8px 18px; display: none; }
</style></head><body>
<header>
  <h1>Pintas UI Generator</h1>
  <input id="nm" placeholder="Nagan (optional): Bakunawa-adarna" list="names" autocomplete="off">
  <datalist id="names">__NAMES__</datalist>
  <button id="go">Baro a UI</button>
</header>
<div class="err" id="err"></div>
<div class="bar" id="bar"><span class="meta">Pindutem ti "Baro a UI" tapno mangaramid iti baro.</span></div>
<div class="hist" id="hist"></div>
<main>
  <iframe id="pv" sandbox="allow-scripts"></iframe>
  <textarea id="src" readonly></textarea>
</main>
<script>
var results = [], cur = -1, showSrc = false;
var $ = function (id) { return document.getElementById(id); };
function bar(r) {
  $("bar").innerHTML = "";
  var n = document.createElement("span"); n.className = "name"; n.textContent = r.name; $("bar").appendChild(n);
  var m = document.createElement("span"); m.className = "meta";
  m.textContent = r.origin + " | " + r.layout + " | seed " + r.seed; $("bar").appendChild(m);
  var s = document.createElement("span");
  r.swatches.forEach(function (c) { var i = document.createElement("i"); i.className = "sw"; i.style.background = c; s.appendChild(i); });
  $("bar").appendChild(s);
  [["Preview / .pintas", function () { showSrc = !showSrc; view(); }],
   ["Copy .pintas", function () { navigator.clipboard.writeText(r.source); }],
   ["Download .pintas", function () { dl(r.slug + ".pintas", r.source); }],
   ["Download .html", function () { dl(r.slug + ".html", r.html); }]].forEach(function (b) {
    var el = document.createElement("button"); el.className = "ghost"; el.textContent = b[0];
    el.onclick = b[1]; $("bar").appendChild(el);
  });
}
function dl(name, text) {
  var a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  a.download = name; document.body.appendChild(a); a.click(); a.remove();
}
function view() {
  var r = results[cur]; if (!r) return;
  $("pv").srcdoc = r.html; $("src").value = r.source;
  $("pv").style.display = showSrc ? "none" : "block";
  $("src").style.display = showSrc ? "block" : "none";
}
function hist() {
  $("hist").innerHTML = "";
  results.forEach(function (r, i) {
    var c = document.createElement("button"); c.className = "chip" + (i === cur ? " on" : "");
    c.textContent = r.name; c.onclick = function () { cur = i; show(); }; $("hist").appendChild(c);
  });
}
function show() { bar(results[cur]); view(); hist(); }
$("go").onclick = function () {
  $("go").disabled = true; $("err").style.display = "none";
  fetch("/generate", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: $("nm").value }) })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      $("go").disabled = false;
      if (!d.ok) { $("err").textContent = d.error; $("err").style.display = "block"; return; }
      results.push(d); cur = results.length - 1; show();
    })
    .catch(function () { $("go").disabled = false; $("err").textContent = "Saan a maka-konekta iti server."; $("err").style.display = "block"; });
};
</script></body></html>
"""


class GuiHandler(http.server.BaseHTTPRequestHandler):
    def _send(self, status, ctype, body):
        data = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            names = "".join(f'<option value="{n}">' for n in list_names())
            self._send(200, "text/html; charset=utf-8", GUI_PAGE.replace("__NAMES__", names))
        else:
            self._send(404, "text/plain", "Awan ti mabirukan")

    def do_POST(self):
        if self.path != "/generate":
            self._send(404, "application/json", json.dumps({"ok": False, "error": "Awan ti mabirukan"}))
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, json.JSONDecodeError):
            payload = {}
        self._send(200, "application/json", json.dumps(gui_payload(payload)))

    def log_message(self, format, *args):
        pass


def run_gui(port=8765, open_browser=True):
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), GuiHandler)
    url = f"http://127.0.0.1:{port}/"
    print("=" * 56)
    print(" Pintas UI Generator")
    print(f" {url}")
    print(" Pindutem ti Ctrl+C tapno agsardeng.")
    print("=" * 56)
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="Generate a named, complete Pintas UI.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (reproducible if set)")
    parser.add_argument("--count", type=int, default=1, help="How many UIs to generate")
    parser.add_argument("--name", default=None,
                        help='Choose the name, e.g. "Bakunawa", "Ibong Adarna", "Bakunawa-adarna"')
    parser.add_argument("--out-dir", default="generated_ui", help="Where .pintas and .html files go")
    parser.add_argument("--gui", action="store_true", help="Open the click-to-generate window")
    parser.add_argument("--port", type=int, default=8765, help="Port for --gui")
    parser.add_argument("--list-names", action="store_true", help="Show the available creature names")
    args = parser.parse_args()

    if args.list_names:
        for c in CREATURES:
            print(f"{c['display']:<15} {c['origin']:<8} {c['epithet']}")
        return
    if args.gui:
        run_gui(args.port)
        return

    for i in range(args.count):
        seed = None if args.seed is None else args.seed + i
        try:
            ui = generate_ui(seed=seed, name=args.name)
        except ValueError as e:
            parser.error(str(e))
        src_path, html_path = write_ui(ui, args.out_dir)
        print(f"\n=== {ui['name']} ({ui['origin']}) ===")
        print(f"  {ui['blurb']}")
        print(f"  seed {ui['seed']} | layout {ui['layout']} ({', '.join(ui['sections'])}) "
              f"| pattern {ui['pattern']['style']} on {ui['pattern']['target']}")
        print(f"  accent {ui['palette']['accent']} on {ui['palette']['bg']} "
              f"({'dark' if ui['dark'] else 'light'}) | all contrast checks passed")
        print(f"  wrote {src_path} and {html_path}")


if __name__ == "__main__":
    main()
