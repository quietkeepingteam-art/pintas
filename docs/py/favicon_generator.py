#!/usr/bin/env python3
"""
Favicon Generator for Pintas - separate software, not part of pintas.py.
Part of the Pintas project by James Kenneth Ines.

Makes a favicon for a Pintas page: a round or rounded-square badge in the
page's accent colour, either

    monogram  the first letter of the page title, built from a 5x7 grid
              of squares like cross-stitch on abel cloth, over a faint
              kusikus weave; or
    sigil     the weave alone, bold, as a small emblem.

The weave is the same Truchet-tile family pattern_generator.py uses
(each tile draws the same edge-midpoint arcs), so a page's favicon,
background and emblem all belong together.

Pure standard library, like the compiler: the PNGs are rasterised by a
small built-in renderer (supersampled, so edges are smooth) and the .ico
is assembled by hand. No Pillow, no network, no external files.

What one run produces (in --out-dir):
    favicon.svg            vector version (modern browsers)
    favicon-16/32/48.png   raster versions
    favicon.ico            16 + 32 + 48 in one file (older browsers)

And prints the Pintas lines that use them - the `ladawan-ulo` command:
    ladawan-ulo "favicon-32.png"
    ladawan-ulo "favicon.svg"
or, with --data-uri, the same icons embedded in the .pintas file itself
so there is nothing extra to copy anywhere.

Legibility is checked, not assumed: the letter is white or near-black
(the same rule theme_generator.py uses for button text) and, when the
accent is a mid-tone where neither reaches 4.5:1, the badge is nudged a
little lighter or darker until the letter does. The printed contrast
ratio is the real one, measured on the final colours.

Usage:
    python favicon_generator.py --title "Bakunawa" --accent "#2563eb"
    python favicon_generator.py --title "Pintas" --style sigil --seed 7
    python favicon_generator.py --title "Pintas" --data-uri
"""

import argparse
import base64
import colorsys
import math
import random
import re
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pattern_generator as pg  # noqa: E402
import theme_generator as tg  # noqa: E402

HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
SHAPES = ("circle", "squircle")
STYLES = ("monogram", "sigil")
PNG_SIZES = (16, 32, 48)
SQUIRCLE_RADIUS = 0.22  # corner radius as a fraction of the icon width

# Weave geometry, in tile units (one tile = 1.0). Arcs have radius 0.5.
STROKE = {"monogram": 0.30, "sigil": 0.36}


# ---------------------------------------------------------------------------
# The cross-stitch alphabet: 5 columns x 7 rows, '#' = a stitch. Upper-case
# letters and digits only; anything else falls back (see pick_letter).
# ---------------------------------------------------------------------------

_FONT_SRC = """
A .###.|#...#|#...#|#####|#...#|#...#|#...#
B ####.|#...#|#...#|####.|#...#|#...#|####.
C .###.|#...#|#....|#....|#....|#...#|.###.
D ####.|#...#|#...#|#...#|#...#|#...#|####.
E #####|#....|#....|####.|#....|#....|#####
F #####|#....|#....|####.|#....|#....|#....
G .###.|#...#|#....|#.###|#...#|#...#|.###.
H #...#|#...#|#...#|#####|#...#|#...#|#...#
I .###.|..#..|..#..|..#..|..#..|..#..|.###.
J ..###|...#.|...#.|...#.|...#.|#..#.|.##..
K #...#|#..#.|#.#..|##...|#.#..|#..#.|#...#
L #....|#....|#....|#....|#....|#....|#####
M #...#|##.##|#.#.#|#.#.#|#...#|#...#|#...#
N #...#|##..#|#.#.#|#..##|#...#|#...#|#...#
O .###.|#...#|#...#|#...#|#...#|#...#|.###.
P ####.|#...#|#...#|####.|#....|#....|#....
Q .###.|#...#|#...#|#...#|#.#.#|#..#.|.##.#
R ####.|#...#|#...#|####.|#.#..|#..#.|#...#
S .####|#....|#....|.###.|....#|....#|####.
T #####|..#..|..#..|..#..|..#..|..#..|..#..
U #...#|#...#|#...#|#...#|#...#|#...#|.###.
V #...#|#...#|#...#|#...#|#...#|.#.#.|..#..
W #...#|#...#|#...#|#.#.#|#.#.#|##.##|#...#
X #...#|#...#|.#.#.|..#..|.#.#.|#...#|#...#
Y #...#|#...#|.#.#.|..#..|..#..|..#..|..#..
Z #####|....#|...#.|..#..|.#...|#....|#####
0 .###.|#...#|#..##|#.#.#|##..#|#...#|.###.
1 ..#..|.##..|..#..|..#..|..#..|..#..|.###.
2 .###.|#...#|....#|...#.|..#..|.#...|#####
3 #####|...#.|..#..|...#.|....#|#...#|.###.
4 ...#.|..##.|.#.#.|#..#.|#####|...#.|...#.
5 #####|#....|####.|....#|....#|#...#|.###.
6 ..##.|.#...|#....|####.|#...#|#...#|.###.
7 #####|....#|...#.|..#..|.#...|.#...|.#...
8 .###.|#...#|#...#|.###.|#...#|#...#|.###.
9 .###.|#...#|#...#|.####|....#|...#.|.##..
"""

FONT = {}
for _row in _FONT_SRC.strip().splitlines():
    _ch, _bits = _row.split(" ", 1)
    FONT[_ch] = [[c == "#" for c in r] for r in _bits.split("|")]

GLYPH_HEIGHT = 0.62  # fraction of the icon height the letter occupies
GLYPH_COLS, GLYPH_ROWS = 5, 7


def pick_letter(title):
    """First letter or digit of the title, upper-cased. Accented letters
    are reduced to their base letter; if nothing usable is found, 'P'
    (for Pintas)."""
    import unicodedata

    for ch in unicodedata.normalize("NFD", title or ""):
        up = ch.upper()
        if up in FONT:
            return up
    return "P"


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------

def _check_hex(color):
    if not HEX_COLOR.match(color or ""):
        raise ValueError("Sayop a kolor. Usaren ti kas iti #2563eb.")
    return color.lower()


def mix_hex(a, b, weight_a):
    ca, cb = tg.hex_to_rgb(a), tg.hex_to_rgb(b)
    return tg.rgb_to_hex([x * weight_a + y * (1 - weight_a) for x, y in zip(ca, cb)])


def readable_badge(accent):
    """Pick white or near-black letter colour, whichever reads better on
    `accent`. For mid-tones neither reaches 4.5:1 (the best possible is
    about 4.2:1), so the badge is nudged lighter or darker, a hair at a
    time, until the letter does. Returns (badge_hex, ink_hex)."""
    ink = tg.best_button_text(accent)
    if tg.contrast_ratio(accent, ink) >= 4.5:
        return accent, ink
    r, g, b = (c / 255 for c in tg.hex_to_rgb(accent))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    step = -0.01 if ink == "#ffffff" else 0.01  # away from the ink colour
    for _ in range(60):
        l = max(0.0, min(1.0, l + step))
        nr, ng, nb = colorsys.hls_to_rgb(h, l, s)
        candidate = tg.rgb_to_hex((nr * 255, ng * 255, nb * 255))
        if tg.contrast_ratio(candidate, ink) >= 4.5:
            return candidate, ink
    return accent, ink


def make_spec(title="", accent="#2563eb", seed=None, style=None, shape=None):
    """Everything needed to draw one favicon. Deterministic per seed."""
    accent = _check_hex(accent)
    if seed is None:
        seed = random.SystemRandom().randrange(10**9)
    rng = random.Random(f"favicon:{seed}")
    if style is None:
        style = "monogram"
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    if shape is None:
        shape = rng.choice(SHAPES)
    if shape not in SHAPES:
        raise ValueError(f"shape must be one of {SHAPES}")

    accent, ink = readable_badge(accent)
    grid_n = 4
    cells = pg._flip_grid(rng, grid_n, True)  # symmetric = weaving-like rosette
    if style == "monogram":
        line = mix_hex(ink, accent, 0.16)  # faint: the letter must win
    else:
        line = ink
    return dict(
        seed=seed, style=style, shape=shape, letter=pick_letter(title),
        bg=accent, ink=ink, line=line, grid=grid_n, cells=cells,
        stroke=STROKE[style],
        contrast=tg.contrast_ratio(accent, ink),
    )


# ---------------------------------------------------------------------------
# Geometry shared by the SVG writer and the rasteriser (unit square).
# ---------------------------------------------------------------------------

def _glyph_box():
    ch = GLYPH_HEIGHT
    cell = ch / GLYPH_ROWS
    w = cell * GLYPH_COLS
    return (1 - w) / 2, (1 - ch) / 2, cell


def _inside_shape(shape, u, v):
    dx, dy = u - 0.5, v - 0.5
    if shape == "circle":
        return dx * dx + dy * dy <= 0.25
    r = SQUIRCLE_RADIUS
    ex, ey = max(abs(dx) - (0.5 - r), 0.0), max(abs(dy) - (0.5 - r), 0.0)
    return ex * ex + ey * ey <= r * r


# Arc centres per Truchet variant (tile-local corners): same two mirror
# variants as pattern_generator.truchet_tile_path.
_ARC_CENTRES = {0: ((0.0, 0.0), (1.0, 1.0)), 1: ((1.0, 0.0), (0.0, 1.0))}


# ---------------------------------------------------------------------------
# SVG
# ---------------------------------------------------------------------------

def _n(x):
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return s if s else "0"


def make_svg(spec, px=64):
    n, cells = spec["grid"], spec["cells"]
    tile = px / n
    d = "".join(
        pg._tile_d("curves", cells[r][c], c * tile, r * tile, tile)
        for r in range(n) for c in range(n)
    )
    # pg._tile_d returns floats formatted by Python; round them for size
    d = re.sub(r"(\d+\.\d{3,})", lambda m: _n(float(m.group(1))), d)

    if spec["shape"] == "circle":
        badge = f'<circle cx="{px/2:g}" cy="{px/2:g}" r="{px/2:g}" fill="{spec["bg"]}"/>'
        clip = f'<circle cx="{px/2:g}" cy="{px/2:g}" r="{px/2:g}"/>'
    else:
        rr = px * SQUIRCLE_RADIUS
        badge = f'<rect width="{px}" height="{px}" rx="{_n(rr)}" fill="{spec["bg"]}"/>'
        clip = f'<rect width="{px}" height="{px}" rx="{_n(rr)}"/>'

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" viewBox="0 0 {px} {px}">',
        f'<defs><clipPath id="c">{clip}</clipPath></defs>',
        badge,
        f'<g clip-path="url(#c)"><path d="{d}" fill="none" stroke="{spec["line"]}" '
        f'stroke-width="{_n(tile * spec["stroke"])}" stroke-linecap="round"/></g>',
    ]
    if spec["style"] == "monogram":
        gx, gy, cell = _glyph_box()
        gx, gy, cell = gx * px, gy * px, cell * px
        squares = []
        for r, row in enumerate(FONT[spec["letter"]]):
            for c, on in enumerate(row):
                if on:
                    squares.append(f"M{_n(gx + c * cell)} {_n(gy + r * cell)}h{_n(cell)}v{_n(cell)}h-{_n(cell)}z")
        parts.append(f'<path d="{"".join(squares)}" fill="{spec["ink"]}"/>')
    parts.append("</svg>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# PNG / ICO: a small supersampling rasteriser (standard library only).
# ---------------------------------------------------------------------------

def render_rgba(spec, size, ss=None):
    """Rasterise to raw RGBA bytes (non-premultiplied). Each output pixel
    averages ss x ss samples, so curved edges are anti-aliased."""
    if ss is None:
        ss = 4 if size <= 64 else 3
    n, cells = spec["grid"], spec["cells"]
    hw = spec["stroke"] / 2
    bg, line, ink = (tuple(tg.hex_to_rgb(spec[k])) for k in ("bg", "line", "ink"))
    mono = spec["style"] == "monogram"
    glyph = FONT[spec["letter"]] if mono else None
    gx0, gy0, gcell = _glyph_box()
    shape = spec["shape"]

    out = bytearray()
    total = ss * ss
    for py in range(size):
        for px in range(size):
            a = r = g = b = 0
            for sy in range(ss):
                v = (py + (sy + 0.5) / ss) / size
                for sx in range(ss):
                    u = (px + (sx + 0.5) / ss) / size
                    if not _inside_shape(shape, u, v):
                        continue
                    col = bg
                    # weave
                    x, y = u * n, v * n
                    tc, tr = min(int(x), n - 1), min(int(y), n - 1)
                    fx, fy = x - tc, y - tr
                    for cx, cy in _ARC_CENTRES[cells[tr][tc]]:
                        if abs(math.hypot(fx - cx, fy - cy) - 0.5) <= hw:
                            col = line
                            break
                    # letter
                    if mono:
                        gx, gy = (u - gx0) / gcell, (v - gy0) / gcell
                        if 0 <= gx < GLYPH_COLS and 0 <= gy < GLYPH_ROWS:
                            ci, ri = int(gx), int(gy)
                            if glyph[ri][ci]:
                                col = ink
                    a += 1
                    r += col[0]
                    g += col[1]
                    b += col[2]
            if a == 0:
                out += b"\x00\x00\x00\x00"
            else:
                out += bytes((round(r / a), round(g / a), round(b / a), round(255 * a / total)))
    return bytes(out)


def _png_chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def encode_png(rgba, size):
    rows = b"".join(b"\x00" + rgba[y * size * 4:(y + 1) * size * 4] for y in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(rows, 9))
        + _png_chunk(b"IEND", b"")
    )


def make_png(spec, size):
    return encode_png(render_rgba(spec, size), size)


def make_ico(png_by_size):
    """Assemble a .ico holding PNG-compressed images (supported since
    Windows Vista and by every current browser)."""
    sizes = sorted(png_by_size)
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for s in sizes:
        data = png_by_size[s]
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return header + entries + blobs


def data_uri(mime, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def generate_favicon(title="", accent="#2563eb", seed=None, style=None, shape=None,
                     sizes=PNG_SIZES):
    """Make one favicon. Returns a dict with the spec, the SVG text, the
    PNG/ICO bytes and ready-to-paste Pintas snippets (file-based and
    data-URI). Reproducible: the same arguments always give the same icon.
    `sizes` limits which PNG sizes are rendered (32 must be among them for
    the snippets); fewer sizes is faster."""
    if 32 not in sizes:
        raise ValueError("sizes must include 32")
    spec = make_spec(title, accent, seed, style, shape)
    svg = make_svg(spec)
    pngs = {s: make_png(spec, s) for s in sizes}
    ico = make_ico(pngs)
    inline = (
        f'ladawan-ulo "{data_uri("image/png", pngs[32])}"\n'
        f'ladawan-ulo "{data_uri("image/svg+xml", svg)}"'
    )
    files = 'ladawan-ulo "favicon-32.png"\nladawan-ulo "favicon.svg"'
    return dict(spec=spec, svg=svg, pngs=pngs, ico=ico,
                snippet_inline=inline, snippet_files=files)


def write_favicon(fav, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "favicon.svg").write_text(fav["svg"], encoding="utf-8")
    for s, data in fav["pngs"].items():
        (out_dir / f"favicon-{s}.png").write_bytes(data)
    (out_dir / "favicon.ico").write_bytes(fav["ico"])
    return out_dir


def main():
    parser = argparse.ArgumentParser(description="Make a favicon for a Pintas page.")
    parser.add_argument("--title", default="", help="Page title; its first letter becomes the monogram")
    parser.add_argument("--accent", default="#2563eb", help="Badge colour (hex)")
    parser.add_argument("--style", choices=STYLES, default="monogram")
    parser.add_argument("--shape", choices=SHAPES, default=None, help="Default: chosen by the seed")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (reproducible if set)")
    parser.add_argument("--out-dir", default="favicon", help="Where the icon files go")
    parser.add_argument("--data-uri", action="store_true",
                        help="Print the snippet with the icons embedded (no extra files needed)")
    args = parser.parse_args()

    try:
        fav = generate_favicon(args.title, args.accent, args.seed, args.style, args.shape)
    except ValueError as e:
        parser.error(str(e))
    out = write_favicon(fav, args.out_dir)
    spec = fav["spec"]
    print(f"Favicon written to {out}/ (favicon.svg, favicon-16/32/48.png, favicon.ico)")
    print(f"  {spec['style']} '{spec['letter']}' on a {spec['shape']}, seed {spec['seed']}, "
          f"badge/letter contrast {spec['contrast']:.1f}:1")
    print("\nPaste this into a .pintas file (anywhere), and keep the icon files next to the page:\n")
    print(fav["snippet_inline"] if args.data_uri else fav["snippet_files"])


if __name__ == "__main__":
    main()
