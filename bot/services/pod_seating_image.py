"""Round-table seating PNG — the ASCII octagon rendered as a monospace image.

Discord embed code blocks wrap too narrowly to hold the octagon, so we draw the exact same text art
into a PNG instead and set it as the embed image. Pillow-only, deterministic, no network; the mono font
is bundled so prod never depends on system fonts. Monospace matters — a proportional font would
misalign the art.
"""
from __future__ import annotations

import io
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).resolve().parents[1] / "assets" / "fonts"
FONT_MONO = FONTS_DIR / "DejaVuSansMono.ttf"

SCALE = 1            # keep pixels 1:1 (crisp); enlarge via FONT_SIZE, not fractional scaling
FONT_SIZE = 12
ARROW_FONT_SIZE = 14  # arrows drawn larger than the labels for emphasis; they sit alone in their cells
PAD = 12            # vertical padding around the text block
PAD_X = 20     # horizontal (left/right) padding — a bit roomier than top/bottom
TEXT = (219, 222, 225)
BORDER = (94, 99, 108)  # square box outline, drawn (not ASCII) so it can't misalign
ARROWS = frozenset("→←↑↓↗↘↙↖")


def drop_unrenderable(text: str) -> str:
    """Strip characters the bundled mono font can't draw on the one-column grid — emoji and
    zero-width joiners in Discord names would otherwise render as tofu or skew the alignment."""
    font = _font(FONT_SIZE)
    mono_width = font.getlength("M")
    notdef = _glyph_mask(font, "\ufffe")
    return "".join(
        ch for ch in text
        if font.getlength(ch) == mono_width and _glyph_mask(font, ch) != notdef
    ).strip()


def render_octagon_png(text: str) -> bytes:
    """Render the monospace octagon `text` (already laid out, box included) to transparent PNG bytes.
    Labels render at FONT_SIZE; arrows are overlaid larger, centred on their cells, so emphasis doesn't
    disturb the grid (each arrow is surrounded by blanks in the layout)."""
    font = _font(FONT_SIZE)
    arrow_font = _font(ARROW_FONT_SIZE)
    lines = text.split("\n")
    char_w = font.getlength("M")
    ascent, descent = font.getmetrics()
    line_h = ascent + descent
    pad_x = round(PAD_X * SCALE)
    pad_y = round(PAD * SCALE)
    cols = max((len(line) for line in lines), default=0)
    width = round(char_w * cols) + pad_x * 2
    height = line_h * len(lines) + pad_y * 2
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    inset = round(2 * SCALE)
    draw.rectangle(
        [inset, inset, width - 1 - inset, height - 1 - inset],
        outline=BORDER, width=max(1, round(SCALE)),
    )
    for i, line in enumerate(lines):
        labels_only = "".join(" " if ch in ARROWS else ch for ch in line)
        draw.text((pad_x, pad_y + i * line_h), labels_only, font=font, fill=TEXT)
    for i, line in enumerate(lines):
        for j, ch in enumerate(line):
            if ch in ARROWS:
                cx = pad_x + (j + 0.5) * char_w
                cy = pad_y + (i + 0.5) * line_h
                draw.text((cx, cy), ch, font=arrow_font, fill=TEXT, anchor="mm")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


@lru_cache(maxsize=4)
def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_MONO), round(size * SCALE))


def _glyph_mask(font: ImageFont.FreeTypeFont, ch: str) -> tuple:
    mask = font.getmask(ch)
    return (mask.size, bytes(mask))
