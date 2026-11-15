#!/usr/bin/env python3
"""Render public/klaskhaIcon.png as ASCII art in a PNG, the same way the footer draws it.

    uv run --no-project --with pillow python scripts/ascii_logo_png.py
    uv run --no-project --with pillow python scripts/ascii_logo_png.py --inks dark-bg --out public/klaskha-ascii-for-dark.png
    uv run --no-project --with pillow python scripts/ascii_logo_png.py --inks original --out public/klaskha-ascii-for-light.png
    uv run --no-project --with pillow python scripts/ascii_logo_png.py --icon public/klaskhaIcon-transparent.png

Each cell takes one symbol from a short ramp: more ink in the logo, a denser symbol. The three inks
of the logo (dark mark, navy ring, gold arc) are recoloured for dark backgrounds, as on the web
(--inks dark-bg), kept as in the original logo for light backgrounds (--inks original), or set to
mid tones that read on any background (--inks any, the default).
--icon only removes the white paper from the original logo PNG and writes it with transparency.
"""

import argparse
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image, ImageColor, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SHADE = " .:-=+*#%@"
INKS = {"mark": (217, 213, 208), "navy": (98, 124, 220), "gold": (244, 186, 78)}  # light: for dark backgrounds
# Mid tones that stay readable on white and on black alike.
INKS_ANY = {"mark": (128, 134, 150), "navy": (86, 118, 232), "gold": (236, 160, 28)}
WEIGHT = {"mark": 1.0, "navy": 0.8, "gold": 0.62}
FONT_URL = "https://fonts.gstatic.com/s/ibmplexmono/v23/-F6qfjptAgt5VM-kVkqdyU8n3twJ8lc.ttf"  # IBM Plex Mono 500


def load_font(path: str | None, size: int) -> ImageFont.FreeTypeFont:
    if path:
        return ImageFont.truetype(path, size)
    cached = Path(tempfile.gettempdir()) / "IBMPlexMono-Medium.ttf"
    if not cached.exists():
        urllib.request.urlretrieve(FONT_URL, cached)
    return ImageFont.truetype(str(cached), size)


def unpaper(r: float, g: float, b: float) -> tuple[int, int, int, float]:
    """Split a colour drawn on white paper into its ink colour and how much ink there is (0 to 1)."""
    ink = 1 - min(r, g, b) / 255
    if ink < 0.004:
        return 0, 0, 0, 0.0
    return tuple(max(0, min(255, round((c - 255 * (1 - ink)) / ink))) for c in (r, g, b)) + (ink,)


def write_transparent_icon(source: str, out: str) -> None:
    logo = Image.open(source).convert("RGB")
    result = Image.new("RGBA", logo.size)
    pixels, target = logo.load(), result.load()
    for y in range(logo.height):
        for x in range(logo.width):
            r, g, b, ink = unpaper(*pixels[x, y])
            target[x, y] = (r, g, b, round(ink * 255))
    result.save(out)
    print(f"{out}: {result.width}x{result.height}px, white background removed")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default=str(ROOT / "public" / "klaskhaIcon.png"))
    parser.add_argument("--out", default=str(ROOT / "public" / "klaskha-ascii.png"))
    parser.add_argument("--cols", type=int, default=140, help="Symbols per row; the web footer uses about 67")
    parser.add_argument("--font-size", type=int, default=22, help="Pixels per symbol; sets the output size")
    parser.add_argument("--background", default="transparent", help="'transparent' or a colour such as '#070b17'")
    parser.add_argument("--inks", choices=("any", "dark-bg", "original"), default="any",
                        help="any: mid tones for any background; dark-bg: light inks (as on the web); "
                        "original: the logo's own colours, for light backgrounds")
    parser.add_argument("--icon", metavar="OUT", help="Write the original logo with its white background made transparent, then stop")
    parser.add_argument("--font", help="Path to a monospaced TTF (IBM Plex Mono is downloaded by default)")
    parser.add_argument("--margin", type=int, default=2, help="Empty cells kept around the logo")
    args = parser.parse_args()

    if args.icon:
        write_transparent_icon(args.source, args.icon)
        return

    font = load_font(args.font, args.font_size)
    cw = font.getlength("#")
    ch = round(args.font_size * 1.1)  # same line height as the web (font size x 1.1)
    # Cells are taller than wide, so the grid has fewer rows than columns to keep the logo square.
    rows = round(args.cols * cw / ch)

    logo = Image.open(args.source).convert("RGB")
    # Averaging each block (BOX) keeps thin strokes; it gives the ink amount per cell.
    small = logo.resize((args.cols, rows), Image.BOX)
    pixels = small.load()

    margin = args.margin
    width = round((args.cols + 2 * margin) * cw)
    height = (rows + 2 * margin) * ch
    transparent = args.background == "transparent"
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0) if transparent else ImageColor.getrgb(args.background) + (255,))
    draw = ImageDraw.Draw(canvas)

    for j in range(rows):
        for i in range(args.cols):
            r, g, b = pixels[i, j]
            ink = 1 - min(r, g, b) / 255
            if ink < 0.12:
                continue
            # Take the white paper out of the colour to know which of the three inks this cell is.
            pr, pb = (r - 255 * (1 - ink)) / ink, (b - 255 * (1 - ink)) / ink
            kind = "navy" if pb > pr + 25 else "gold" if pr > pb + 60 else "mark"
            symbol = SHADE[min(len(SHADE) - 1, round(ink * WEIGHT[kind] * (len(SHADE) - 1)))]
            if symbol != " ":
                fill = {"any": INKS_ANY, "dark-bg": INKS}.get(args.inks, {}).get(kind) or tuple(unpaper(r, g, b)[:3])
                draw.text(((i + margin) * cw, (j + margin) * ch), symbol, font=font, fill=fill + (255,))

    canvas.save(args.out)
    print(f"{args.out}: {width}x{height}px, {args.cols}x{rows} symbols, background {args.background}")


if __name__ == "__main__":
    main()
