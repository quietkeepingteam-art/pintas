#!/usr/bin/env python3
"""
Pattern Generator for Pintas - separate software, not part of pintas.py.
Part of the Pintas project by James Kenneth Ines.

Autonomously generates tileable background patterns inspired by
"kusikus," a real geometric motif from Ilokano abel/inabel weaving -
undulating square grids historically woven to mimic whirlpools
(the technique is called "binakol"). This does not attempt to
reproduce actual loom/thread mechanics; it borrows the same
grid-and-flow visual logic using Truchet tiles, a real (17th-century)
mathematical technique for exactly this kind of flowing grid pattern,
which is why it's a legitimate way to generate the look algorithmically
rather than needing each pattern hand-drawn.

What "autonomous" means here: given a seed, a grid size, and up to two
colors, it produces a new, different, seamlessly-tileable SVG pattern
every time - no per-pattern manual drawing.

Output is a true CSS <pattern> (tiles seamlessly via background-repeat,
not a single static image), plus a ready-to-paste Pintas `estilo`
snippet using a base64 data URI - no external image file needed,
consistent with the rest of this project's zero-external-asset
approach.

Usage:
    python pattern_generator.py --seed 7 --size 6 --line "#2563eb" --bg "#f0f6ff"
    python pattern_generator.py --seed 7 --size 6 --for-garrapon
"""

import argparse
import base64
import random
from pathlib import Path


def truchet_tile_path(variant, s):
    """Two quarter-circle arcs per tile, radius s/2, each connecting
    the midpoints of two adjacent sides. Two mirror variants; every
    tile touches all four edge midpoints, so adjacent tiles' arcs
    always connect regardless of which variant either one is - that's
    what makes the whole grid flow into continuous curves rather than
    a grid of disconnected quarter-circles.
    """
    h = s / 2
    if variant == 0:  # arcs bulge toward top-left / bottom-right corners
        return (
            f"M {h},0 A {h},{h} 0 0,0 0,{h} "
            f"M {h},{s} A {h},{h} 0 0,0 {s},{h}"
        )
    else:  # mirror: arcs bulge toward top-right / bottom-left corners
        return (
            f"M {h},0 A {h},{h} 0 0,1 {s},{h} "
            f"M {h},{s} A {h},{h} 0 0,1 0,{h}"
        )


# Four looks, all built from the same edge-midpoint tile so every one tiles
# seamlessly. The seed alone used to only reshuffle ONE look (thin curves),
# which is why every generated pattern felt the same.
STYLES = ("curves", "diamonds", "ribbon", "blobs")

# How strongly each look is tinted toward the accent colour. Thin lines need
# more contrast than big filled shapes to be seen at all, but stay soft
# enough that text on top remains readable.
STYLE_STRENGTH = {"curves": 0.40, "diamonds": 0.40, "ribbon": 0.34, "blobs": 0.20}


def random_recipe(seed):
    """Pick a look for `seed`: style, grid size, tile size, line weight and
    whether the grid is mirrored into a symmetric, weaving-like rosette.
    Deterministic per seed, and independent of the tile-flip randomness."""
    r = random.Random(f"recipe:{seed}")
    return dict(
        style=r.choice(STYLES),
        symmetric=r.random() < 0.6,
        grid_size=r.choice((4, 6, 8)),
        tile_size=r.choice((30, 40, 52)),
        stroke_width=r.choice((2, 3, 4)),
    )


def _flip_grid(rng, n, symmetric):
    """n x n grid of 0/1 tile variants. Symmetric mode draws one quadrant and
    mirrors it: reflecting a Truchet tile swaps its variant, so left/right and
    top/bottom copies use 1-v, the diagonal copy keeps v. (Even n only.)"""
    if not (symmetric and n % 2 == 0):
        return [[rng.choice([0, 1]) for _ in range(n)] for _ in range(n)]
    half = n // 2
    g = [[0] * n for _ in range(n)]
    for r in range(half):
        for c in range(half):
            v = rng.choice([0, 1])
            g[r][c] = v
            g[r][n - 1 - c] = 1 - v
            g[n - 1 - r][c] = 1 - v
            g[n - 1 - r][n - 1 - c] = v
    return g


def _tile_d(style, variant, x, y, s):
    """Path data for one tile at (x, y), in absolute coordinates so all tiles
    can share a single <path> (much smaller output than one element per tile)."""
    h = s / 2
    if style == "diamonds":  # straight midpoint-to-midpoint strokes
        if variant == 0:
            return f"M{x + h},{y}L{x},{y + h}M{x + h},{y + s}L{x + s},{y + h}"
        return f"M{x + h},{y}L{x + s},{y + h}M{x + h},{y + s}L{x},{y + h}"
    if style == "blobs":  # filled quarter discs at two opposite corners
        if variant == 0:
            return (f"M{x},{y}L{x + h},{y}A{h},{h} 0 0,0 {x},{y + h}Z"
                    f"M{x + s},{y + s}L{x + h},{y + s}A{h},{h} 0 0,0 {x + s},{y + h}Z")
        return (f"M{x + s},{y}L{x + h},{y}A{h},{h} 0 0,1 {x + s},{y + h}Z"
                f"M{x},{y + s}L{x + h},{y + s}A{h},{h} 0 0,1 {x},{y + h}Z")
    # curves / ribbon: the two quarter-circle arcs
    if variant == 0:
        return (f"M{x + h},{y}A{h},{h} 0 0,0 {x},{y + h}"
                f"M{x + h},{y + s}A{h},{h} 0 0,0 {x + s},{y + h}")
    return (f"M{x + h},{y}A{h},{h} 0 0,1 {x + s},{y + h}"
            f"M{x + h},{y + s}A{h},{h} 0 0,1 {x},{y + h}")


def generate_pattern_svg(seed, grid_size, line_color, bg_color, tile_size=40,
                         stroke_width=3, style="curves", symmetric=False):
    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}")
    rng = random.Random(seed)
    unit = grid_size * tile_size
    grid = _flip_grid(rng, grid_size, symmetric)

    d = "".join(
        _tile_d(style, grid[row][col], col * tile_size, row * tile_size, tile_size)
        for row in range(grid_size)
        for col in range(grid_size)
    )
    if style == "blobs":
        shapes = f'<path d="{d}" fill="{line_color}"/>'
    elif style == "ribbon":  # thick line with a thin bg-coloured core = a ribbon
        shapes = (
            f'<path d="{d}" fill="none" stroke="{line_color}" '
            f'stroke-width="{stroke_width * 3}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{bg_color}" '
            f'stroke-width="{max(1, stroke_width)}" stroke-linecap="round"/>'
        )
    else:
        shapes = (
            f'<path d="{d}" fill="none" stroke="{line_color}" '
            f'stroke-width="{stroke_width}" stroke-linecap="round"/>'
        )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{unit}" height="{unit}" '
        f'viewBox="0 0 {unit} {unit}">'
        f'<rect width="{unit}" height="{unit}" fill="{bg_color}"/>'
        + shapes
        + "</svg>"
    )
    return svg, unit


def as_data_uri(svg_text):
    encoded = base64.b64encode(svg_text.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def estilo_snippet(svg_text, unit, target):
    uri = as_data_uri(svg_text)
    return (
        "estilo\n"
        f"{target} {{\n"
        f'  background-image: url("{uri}");\n'
        f"  background-size: {unit}px {unit}px;\n"
        "  background-repeat: repeat;\n"
        "}\n"
        "murdong"
    )


def main():
    parser = argparse.ArgumentParser(description="Generate a kusikus-inspired tileable Pintas background.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed (reproducible if set)")
    parser.add_argument("--size", type=int, default=6, help="Grid size (NxN tiles)")
    parser.add_argument("--tile-size", type=int, default=40, help="Pixel size of one tile before scaling")
    parser.add_argument("--line", default="#2563eb", help="Line color")
    parser.add_argument("--bg", default="#f0f6ff", help="Background color between lines")
    parser.add_argument("--stroke-width", type=int, default=3, help="Line thickness")
    parser.add_argument("--style", default="curves", choices=STYLES + ("random",),
                        help="Look of the pattern; 'random' lets the seed choose everything")
    parser.add_argument("--symmetric", action="store_true",
                        help="Mirror the grid into a symmetric, weaving-like rosette (even --size)")
    parser.add_argument("--for-garrapon", action="store_true", help="Target .garrapon instead of body")
    parser.add_argument("--out", default="pattern.svg", help="Where to save the standalone .svg file")
    args = parser.parse_args()

    if args.seed is None:
        args.seed = random.randrange(10**9)
    if args.style == "random":
        r = random_recipe(args.seed)
        svg, unit = generate_pattern_svg(
            args.seed, r["grid_size"], args.line, args.bg, r["tile_size"],
            r["stroke_width"], r["style"], r["symmetric"],
        )
    else:
        svg, unit = generate_pattern_svg(
            args.seed, args.size, args.line, args.bg, args.tile_size,
            args.stroke_width, args.style, args.symmetric,
        )

    out_path = Path(args.out)
    out_path.write_text(svg, encoding="utf-8")
    print(f"Standalone SVG written: {out_path} ({unit}x{unit}, tiles seamlessly)")

    target = ".garrapon" if args.for_garrapon else "body"
    snippet = estilo_snippet(svg, unit, target)
    print("\nPaste this into a .pintas file to use it as a background:\n")
    print(snippet)


if __name__ == "__main__":
    main()
