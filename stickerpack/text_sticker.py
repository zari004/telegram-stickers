"""Render short text as a Telegram sticker image (512x512 PNG)."""
from __future__ import annotations

import textwrap
from dataclasses import dataclass
from functools import lru_cache
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
    text_gradient: Optional[Tuple[Color, Color]] = None  # (left, right); overrides text_color when set
    outline_color: Optional[Color] = (255, 255, 255, 255)
    outline_width: int = 8
    background_color: Optional[Color] = None  # None => transparent background
    font_path: Optional[str] = None


@dataclass
class _FontSet:
    """The font(s) needed to render one piece of text.

    ``fallback`` is only set when ``primary`` (typically a user-uploaded
    custom font) is missing a glyph for at least one character actually
    present in the text - e.g. many decorative fonts don't include the
    Uzbek-specific Cyrillic letters Ў/Ғ/Қ/Ҳ, and FreeType silently
    substitutes the font's own ".notdef" glyph for those (some fonts draw
    that as a literal "NO GLYPH" box). When unset, rendering behaves exactly
    as a single-font pipeline - no per-character overhead.
    """

    primary: ImageFont.FreeTypeFont
    primary_path: str
    fallback: Optional[ImageFont.FreeTypeFont] = None

    def font_for(self, ch: str) -> ImageFont.FreeTypeFont:
        if self.fallback is not None and not _char_has_glyph(self.primary_path, ch):
            return self.fallback
        return self.primary

    def metrics(self) -> Tuple[int, int]:
        ascent, descent = self.primary.getmetrics()
        if self.fallback is not None:
            fb_ascent, fb_descent = self.fallback.getmetrics()
            ascent, descent = max(ascent, fb_ascent), max(descent, fb_descent)
        return ascent, descent


@lru_cache(maxsize=256)
def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(font_path, size)


@lru_cache(maxsize=64)
def _font_codepoints(font_path: str) -> Optional[frozenset]:
    """Characters ``font_path`` has a real glyph for, per its cmap table.

    Returns None (meaning "unknown, assume it supports everything") if the
    font can't be introspected, so a missing/broken fontTools install just
    disables fallback instead of breaking rendering.
    """
    try:
        from fontTools.ttLib import TTFont

        ttfont = TTFont(font_path, lazy=True, fontNumber=0)
        cmap = ttfont.getBestCmap()
        ttfont.close()
        if not cmap:
            return None
        return frozenset(chr(cp) for cp in cmap)
    except Exception:
        return None


def _char_has_glyph(font_path: str, ch: str) -> bool:
    if ch.isspace():
        return True
    codepoints = _font_codepoints(font_path)
    return codepoints is None or ch in codepoints


def _needs_fallback(text: str, font_path: str) -> bool:
    default_path = str(DEFAULT_FONT_BOLD)
    if font_path == default_path:
        return False
    return any(not _char_has_glyph(font_path, ch) for ch in set(text) if not ch.isspace())


def _text_width(draw: ImageDraw.ImageDraw, text: str, fonts: _FontSet) -> float:
    if fonts.fallback is None:
        return draw.textlength(text, font=fonts.primary)
    return sum(draw.textlength(ch, font=fonts.font_for(ch)) for ch in text)


def _draw_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[float, float],
    text: str,
    fonts: _FontSet,
    *,
    fill,
    stroke_width: int = 0,
    stroke_fill=None,
) -> None:
    if fonts.fallback is None:
        draw.text(xy, text, font=fonts.primary, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        return
    x, y = xy
    for ch in text:
        font = fonts.font_for(ch)
        draw.text((x, y), ch, font=font, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)
        x += draw.textlength(ch, font=font)


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
    fallback_path = str(DEFAULT_FONT_BOLD) if _needs_fallback(text, font_path) else None

    fonts, lines, line_height = _fit_text(draw, text, font_path, fallback_path, max_width, max_height)

    total_text_height = line_height * len(lines)
    y = (size - total_text_height) / 2

    stroke_width = style.outline_width if style.outline_color else 0

    if style.text_gradient:
        _draw_gradient_text(image, draw, lines, fonts, y, line_height, stroke_width, style)
    else:
        for line in lines:
            line_width = _text_width(draw, line, fonts)
            x = (size - line_width) / 2
            _draw_text(
                draw, (x, y), line, fonts,
                fill=style.text_color, stroke_width=stroke_width, stroke_fill=style.outline_color,
            )
            y += line_height

    return image


def _draw_gradient_text(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    fonts: _FontSet,
    start_y: float,
    line_height: float,
    stroke_width: int,
    style: TextStickerStyle,
) -> None:
    """Fill the glyph interiors with a left-to-right gradient, keeping any
    outline solid - draw.text() only accepts a single flat fill color, so
    the gradient is painted separately and cut to the glyphs' shape via a
    mask."""
    size = image.size[0]

    if stroke_width and style.outline_color:
        outline_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
        outline_draw = ImageDraw.Draw(outline_layer)
        y = start_y
        for line in lines:
            x = (size - _text_width(draw, line, fonts)) / 2
            _draw_text(
                outline_draw, (x, y), line, fonts,
                fill=style.outline_color, stroke_width=stroke_width, stroke_fill=style.outline_color,
            )
            y += line_height
        image.alpha_composite(outline_layer)

    fill_mask = Image.new("L", image.size, 0)
    mask_draw = ImageDraw.Draw(fill_mask)
    y = start_y
    for line in lines:
        x = (size - _text_width(draw, line, fonts)) / 2
        _draw_text(mask_draw, (x, y), line, fonts, fill=255)
        y += line_height

    gradient = _horizontal_gradient(image.size, *style.text_gradient)
    gradient_layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    gradient_layer.paste(gradient, (0, 0), fill_mask)
    image.alpha_composite(gradient_layer)


def _horizontal_gradient(size: Tuple[int, int], left: Color, right: Color) -> Image.Image:
    width, height = size
    row = Image.new("RGBA", (max(1, width), 1))
    for x in range(width):
        t = x / max(1, width - 1)
        row.putpixel(
            (x, 0),
            tuple(round(left[i] + (right[i] - left[i]) * t) for i in range(4)),
        )
    return row.resize((width, height))


def _fit_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font_path: str,
    fallback_path: Optional[str],
    max_width: float,
    max_height: float,
):
    last_fonts = last_lines = None
    last_line_height = 0

    for font_size in range(MAX_FONT_SIZE, MIN_FONT_SIZE - 1, -FONT_STEP):
        primary = _load_font(font_path, font_size)
        fallback = _load_font(fallback_path, font_size) if fallback_path else None
        fonts = _FontSet(primary, font_path, fallback)

        lines = _wrap_lines(draw, text, fonts, max_width)
        ascent, descent = fonts.metrics()
        line_height = ascent + descent + max(4, font_size // 10)
        total_height = line_height * len(lines)
        widest_line = max((_text_width(draw, line, fonts) for line in lines), default=0)

        last_fonts, last_lines, last_line_height = fonts, lines, line_height
        if total_height <= max_height and widest_line <= max_width:
            return fonts, lines, line_height

    # Nothing fit perfectly (extremely long text) - use the smallest size we tried.
    return last_fonts, last_lines, last_line_height


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, fonts: _FontSet, max_width: float) -> list[str]:
    lines: list[str] = []
    for paragraph in text.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if _text_width(draw, candidate, fonts) <= max_width or not current:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines or [""]
