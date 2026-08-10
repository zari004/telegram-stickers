"""Turn arbitrary images into Telegram-compliant static sticker PNGs.

Telegram's rules for a static sticker image (Bot API "static" sticker format):
  - PNG, with transparency support.
  - Exactly one side must be 512px, the other side must be <= 512px.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

STICKER_SIZE = 512


def prepare_sticker_image(source: "str | Path | bytes | Image.Image") -> Image.Image:
    """Resize/convert an image so it satisfies Telegram's sticker constraints.

    The image is scaled (preserving aspect ratio) so its longest side is
    exactly ``STICKER_SIZE`` pixels, and converted to RGBA so transparency
    (if any) is preserved.
    """
    image = _load_image(source)
    image = image.convert("RGBA")

    width, height = image.size
    if width == 0 or height == 0:
        raise ValueError("Bo'sh yoki noto'g'ri rasm")

    scale = STICKER_SIZE / max(width, height)
    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    image = image.resize(new_size, Image.LANCZOS)

    return image


def image_to_png_bytes(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def prepare_sticker_png_bytes(source: "str | Path | bytes | Image.Image") -> bytes:
    return image_to_png_bytes(prepare_sticker_image(source))


def _load_image(source: "str | Path | bytes | Image.Image") -> Image.Image:
    if isinstance(source, Image.Image):
        return source
    if isinstance(source, (bytes, bytearray)):
        return Image.open(BytesIO(source))
    return Image.open(source)
