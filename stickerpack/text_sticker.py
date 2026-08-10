"""Render short text as a Telegram sticker image (512x512 PNG)."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from .config import DEFAULT_FONT_BOLD
from .image_utils import STICKER_SIZE

Color = Tuple[int, int, int, int]

PADDING = 48
MAX_FONT_SIZE = 160
MIN_FONT_SIZE = 28
FONT_STEP = 4


@dataclass
class TextStickerStyle:
    text_color: Color = (30, 30, 30, 255)
    outline_color: Optional[Color] = (255, 255, 255, 255)
    outline_width: int = 8
    background_color: Optional[Color] = None  # None => transparent background
    font_path: Optional[str] = None


def render_text_sticker(text: str, style: Optional[TextStickerStyle] = None) -> Image.Image:
    """Render ``text`` centered on a 512x512 sticker canvas.

    The font size is auto-shrunk until every line fits inside the padded
    canvas, so short exclamations render huge and longer phrases still fit.
    """
    style = style or TextStickerStyle()
    text = (text or "").strip()
    if not text:
        raise ValueError("Matn bo'sh bo'lishi mumkin emas")

    size = STICKER_SIZE
    image = Image.new("RGBA", (size, size), style.background_color or (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    max_width = size - PADDING * 2
    max_height = size - PADDING * 2
    font_path = style.font_path or str(DEFAULT_FONT_BOLD)

    font, lines, line_height = _fit_text(draw, text, font_path, max_width, max_height)

    total_text_height = line_height * len(lines)
    y = (size - total_text_height) / 2

    stroke_width = style.outline_width if style.outline_color else 0
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (size - line_width) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=style.text_color,
            stroke_width=stroke_width,
            stroke_fill=style.outline_color,
        )
        y += line_height

    return image


def _fit_text(draw: ImageDraw.ImageDraw, text: str, font_path: str, max_width: float, max_height: float):
    last_font = last_lines = None
    last_line_height = 0

    for font_size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -FONT_STEP):
        font = ImageFont.truetype(font_path, font_size)
        lines = _wrap_lines(draw, text, font, max_width)
        ascent, descent = font.getmetrics()
        line_height = ascent + descent + max(4, font_size // 10)
        total_height = line_height * len(lines)
        widest_line = max((draw.textlength(line, font=font) for line in lines), default=0)

        last_font, last_lines, last_line_height = font, lines, line_height
        if total_height <= max_height and widest_line <= max_width:
            return font, lines, line_height

    # Nothing fit perfectly (extremely long text) - use the smallest size we tried.
    return last_font, last_lines, last_line_height


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if draw.textlength(candidate, font=font) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]
