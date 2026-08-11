"""General-purpose image resizing to a fixed pixel size, with DPI metadata.

Unlike ``image_utils`` (which targets Telegram's sticker constraints), this
resizes to an arbitrary, user-configured width x height and embeds a DPI
value into the saved file - useful for print-ready or platform-specific
exports (e.g. "Instagram post", "A4 @300dpi").
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image

from .image_utils import load_image

MIN_DIMENSION = 1
MAX_DIMENSION = 10000


def resize_to_canvas(source: "str | Path | bytes | Image.Image", width: int, height: int) -> Image.Image:
    """Fit ``source`` inside a ``width`` x ``height`` canvas without distortion.

    The image is scaled (preserving aspect ratio) to fit within the target
    box and centered on a transparent canvas of exactly that size - no
    cropping, no stretching.
    """
    image = load_image(source).convert("RGBA")
    if image.width == 0 or image.height == 0:
        raise ValueError("Bo'sh yoki noto'g'ri rasm")

    scale = min(width / image.width, height / image.height)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    offset = ((width - resized.width) // 2, (height - resized.height) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def image_to_png_bytes_with_dpi(image: Image.Image, dpi: int) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG", dpi=(dpi, dpi))
    buffer.seek(0)
    return buffer.getvalue()
