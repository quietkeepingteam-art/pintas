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


def generate_pattern_svg(seed, grid_size, line_color, bg_color, tile_size=40, stroke_width=3):
    rng = random.Random(seed)
    unit = grid_size * tile_size

    tiles = []
    for row in range(grid_size):
        for col in range(grid_size):
            variant = rng.choice([0, 1])
            x, y = col * tile_size, row * tile_size
            d = truchet_tile_path(variant, tile_size)
            tiles.append(
                f'<path transform="translate({x},{y})" d="{d}" '
                f'fill="none" stroke="{line_color}" stroke-width="{stroke_width}" '
                f'stroke-linecap="round"/>'
            )

    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{unit}" height="{unit}" '
        f'viewBox="0 0 {unit} {unit}">'
        f'<rect width="{unit}" height="{unit}" fill="{bg_color}"/>'
        + "".join(tiles)
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
    parser.add_argument("--for-garrapon", action="store_true", help="Target .garrapon instead of body")
    parser.add_argument("--out", default="pattern.svg", help="Where to save the standalone .svg file")
    args = parser.parse_args()

    svg, unit = generate_pattern_svg(
        args.seed, args.size, args.line, args.bg, args.tile_size, args.stroke_width
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
