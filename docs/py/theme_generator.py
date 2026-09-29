#!/usr/bin/env python3
"""
Theme Generator for Pintas - separate software, not part of pintas.py.
Part of the Pintas project by James Kenneth Ines.

Autonomously proposes new `tema` color palettes and font/shape
pairings for Pintas, then renders a real live preview through the
actual pintas.py compiler (not a mockup) so you can see the result.

What "autonomous" means here, precisely:
- Colors are derived from real color theory (a random base hue plus
  a scheme: monochromatic/analogous/complementary/triadic), not just
  randomly guessed.
- Every generated palette is VERIFIED, not assumed: text-on-background
  and muted-on-background are nudged until they clear real WCAG
  contrast ratios, and button text automatically picks whichever of
  white or near-black actually has better contrast against the
  generated accent - the exact rule the `balitok` gold-button bug
  taught us, now applied generally instead of by hand each time.
- Font pairing and shape (radius/shadow/heading treatment) are picked
  from small curated pools, so "autonomous" doesn't mean "unconstrained
  random" - a pool of known-good pairings keeps results from being an
  eyesore, the same reasoning as picking Truchet-tile rules for the
  pattern generator instead of drawing free-hand.

What this script deliberately does NOT do: invent a name. Every theme
Pintas ships (puraw, nangisit, asul, berde, duyaw, labaga, rabii,
balitok, danum) is a real, checked Ilokano word - verifying a new one
needs an actual dictionary/source lookup, not an algorithm guessing
plausible-sounding syllables. A generated palette is emitted as
`"CANDIDATE"` with that instruction attached; giving it a real name
before it's added to pintas.py's THEMES is a manual, human step.

Usage:
    python theme_generator.py --seed 42 --count 3
    python theme_generator.py --seed 7 --preview
"""

import argparse
import colorsys
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pintas import compile_pintas  # reuse the REAL compiler for previews, not a mockup


# ---------- color math (same contrast formula validated on balitok) ----------

def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_hex(rgb):
    return "#" + "".join(f"{max(0, min(255, round(c))):02x}" for c in rgb)


def hsl_to_hex(h, s, l):
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360, l, s)
    return rgb_to_hex((r * 255, g * 255, b * 255))


def relative_luminance(rgb):
    def lin(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex_to_rgb(hex1))
    l2 = relative_luminance(hex_to_rgb(hex2))
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def best_button_text(accent_hex):
    """Pick whichever of white/near-black has better contrast against
    the accent - the general form of the fix balitok needed by hand."""
    white, dark = "#ffffff", "#1a1710"
    if contrast_ratio(accent_hex, white) >= contrast_ratio(accent_hex, dark):
        return white
    return dark


def nudge_for_contrast(hue, sat, bg_hex, target_ratio, start_l, step):
    """Walk lightness in `step` increments until contrast against
    bg_hex clears target_ratio, capped so it always terminates."""
    l = start_l
    candidate = hsl_to_hex(hue, sat, l)
    for _ in range(48):
        if contrast_ratio(candidate, bg_hex) >= target_ratio:
            return candidate
        l = max(0.01, min(0.99, l + step))
        candidate = hsl_to_hex(hue, sat, l)
    return candidate  # best effort if the cap is hit


# ---------- curated pools (this is what keeps "autonomous" from meaning "ugly") ----------

FONT_PAIRINGS = [
    ('"Fraunces", Georgia, serif', '"Inter", sans-serif',
     "family=Fraunces:wght@600;700&family=Inter:wght@400;600"),
    ('"Space Grotesk", sans-serif', '"Inter", sans-serif',
     "family=Space+Grotesk:wght@600;700&family=Inter:wght@400;600"),
    ('"Poppins", sans-serif', '"Source Sans 3", sans-serif',
     "family=Poppins:wght@600;700&family=Source+Sans+3:wght@400;600"),
    ('"Lora", Georgia, serif', '"Nunito Sans", sans-serif',
     "family=Lora:wght@600;700&family=Nunito+Sans:wght@400;600"),
    ('"DM Serif Display", Georgia, serif', '"DM Sans", sans-serif',
     "family=DM+Serif+Display&family=DM+Sans:wght@400;600"),
    ('"Oswald", sans-serif', '"Work Sans", sans-serif',
     "family=Oswald:wght@600;700&family=Work+Sans:wght@400;600"),
    ('"Playfair Display", Georgia, serif', '"Montserrat", sans-serif',
     "family=Playfair+Display:wght@600;700&family=Montserrat:wght@400;600"),
    ('"Quicksand", sans-serif', '"Karla", sans-serif',
     "family=Quicksand:wght@600;700&family=Karla:wght@400;600"),
]

STRUCTURE_PRESETS = [
    {"radius": "8px", "card-radius": "12px", "heading-transform": "none",
     "heading-tracking": "normal", "glow": False},
    {"radius": "999px", "card-radius": "16px", "heading-transform": "uppercase",
     "heading-tracking": "0.08em", "glow": True},
    {"radius": "4px", "card-radius": "4px", "heading-transform": "none",
     "heading-tracking": "0.05em", "glow": False},
    {"radius": "24px", "card-radius": "24px", "heading-transform": "none",
     "heading-tracking": "normal", "glow": True},
]


def generate_palette(rng):
    dark_mode = rng.random() < 0.4
    base_hue = rng.uniform(0, 360)
    scheme = rng.choice(["monochromatic", "analogous", "complementary", "triadic"])
    accent_hue = {
        "complementary": base_hue + 180,
        "triadic": base_hue + 120,
        "analogous": base_hue + 30,
        "monochromatic": base_hue,
    }[scheme]

    if dark_mode:
        bg = hsl_to_hex(base_hue, 0.35, 0.06)
        card_bg = hsl_to_hex(base_hue, 0.3, 0.1)
        text = nudge_for_contrast(base_hue, 0.08, bg, 7.0, 0.92, +0.02)
        muted = nudge_for_contrast(base_hue, 0.12, bg, 4.5, 0.7, +0.02)
    else:
        bg = hsl_to_hex(base_hue, 0.4, 0.97)
        card_bg = hsl_to_hex(base_hue, 0.3, 0.99)
        text = nudge_for_contrast(base_hue, 0.15, bg, 7.0, 0.12, -0.02)
        muted = nudge_for_contrast(base_hue, 0.15, bg, 4.5, 0.4, -0.02)

    accent = hsl_to_hex(accent_hue, rng.uniform(0.55, 0.85), rng.uniform(0.42, 0.55))
    accent_hover = hsl_to_hex(
        accent_hue, rng.uniform(0.6, 0.9), max(0.22, rng.uniform(0.3, 0.45))
    )
    button_text = best_button_text(accent)

    heading_font, body_font, font_url = rng.choice(FONT_PAIRINGS)
    structure = dict(rng.choice(STRUCTURE_PRESETS))
    glow = structure.pop("glow")
    r, g, b = hex_to_rgb(accent)
    if glow:
        card_shadow = f"0 0 22px rgba({r},{g},{b},0.28)"
        button_shadow = f"0 0 14px rgba({r},{g},{b},0.45)"
    else:
        card_shadow = "0 1px 3px rgba(0,0,0,0.08)" if not dark_mode else "0 2px 10px rgba(0,0,0,0.35)"
        button_shadow = "none"

    return {
        "bg": bg, "text": text, "muted": muted,
        "accent": accent, "accent-hover": accent_hover, "card-bg": card_bg,
        "button-text": button_text,
        "font-heading": heading_font, "font-body": body_font, "font-url": font_url,
        **structure,
        "card-shadow": card_shadow, "button-shadow": button_shadow,
    }


def verify_palette(p):
    """Real checks, not a formality - matches the bar test_pintas.py
    already holds every shipped theme to."""
    checks = {
        "bg/text >= 7:1": contrast_ratio(p["bg"], p["text"]) >= 7.0,
        "bg/muted >= 4.5:1": contrast_ratio(p["bg"], p["muted"]) >= 4.5,
        "accent/button-text >= 4.5:1": contrast_ratio(p["accent"], p["button-text"]) >= 4.5,
    }
    return checks


def format_as_theme_entry(name, p):
    lines = [f'    "{name}": {{  # CANDIDATE - needs a real, verified Ilokano name']
    lines.append(
        f'        "bg": "{p["bg"]}", "text": "{p["text"]}", "muted": "{p["muted"]}",'
    )
    lines.append(
        f'        "accent": "{p["accent"]}", "accent-hover": "{p["accent-hover"]}", '
        f'"card-bg": "{p["card-bg"]}",'
    )
    lines.append(f'        "font-heading": \'{p["font-heading"]}\',')
    lines.append(f'        "font-body": \'{p["font-body"]}\',')
    lines.append(f'        "font-url": "{p["font-url"]}",')
    lines.append(
        f'        "radius": "{p["radius"]}", "card-radius": "{p["card-radius"]}", '
        f'"card-shadow": "{p["card-shadow"]}",'
    )
    lines.append(
        f'        "button-shadow": "{p["button-shadow"]}", '
        f'"heading-transform": "{p["heading-transform"]}", '
        f'"heading-tracking": "{p["heading-tracking"]}",'
    )
    lines.append(f'        "button-text": "{p["button-text"]}",')
    lines.append("    },")
    return "\n".join(lines)


def render_preview(p, name, out_path):
    """Feed the candidate straight through the REAL compiler by
    temporarily registering it, so the preview is exactly what Pintas
    would actually produce - not a hand-simulated approximation."""
    import pintas

    pintas.THEMES[name] = p
    try:
        source = (
            f'ulo "{name} - Pintas theme candidate"\n'
            f'tema "{name}"\n'
            f'texto "Kastoy ti langa ti {name}"\n'
            f'subtexto "Pagsuboan a temaa - kastoy ti langana"\n'
            'butangan "Daytoy ket sample a testo tapno makita ti kontrasti '
            'ken ti pagbasaan."\n'
            'pagpindutan "Sample a buton"\n'
            "garrapon\n"
            'texto "Uneg ti garrapon"\n'
            'butangan "Kastoy ti langa ti maysa a lalaem iti daytoy a tema."\n'
            "murdong\n"
            "tengnga\n"
        )
        html, _ = compile_pintas(source)
    finally:
        del pintas.THEMES[name]
    out_path.write_text(html, encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Generate candidate Pintas themes.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (reproducible if set)")
    parser.add_argument("--count", type=int, default=3, help="How many candidates to generate")
    parser.add_argument("--preview", action="store_true", help="Also write an HTML preview per candidate")
    parser.add_argument("--out-dir", default="generated_themes", help="Where preview HTML files go")
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(args.out_dir)

    for i in range(args.count):
        name = f"candidate{i + 1}"
        palette = generate_palette(rng)
        checks = verify_palette(palette)
        failed = [k for k, ok in checks.items() if not ok]

        print(f"\n=== {name} ===")
        if failed:
            print(f"  FAILED contrast checks: {failed} (skipping)")
            continue
        print("  All contrast checks passed:", ", ".join(checks))
        print(format_as_theme_entry(name, palette))

        if args.preview:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = render_preview(palette, name, out_dir / f"{name}.html")
            print(f"  Preview written: {path}")


if __name__ == "__main__":
    main()
