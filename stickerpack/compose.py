"""Layer a sticker's content on top of a background image (e.g. a company logo)."""
from __future__ import annotations

from PIL import Image

from .image_utils import STICKER_SIZE


def fit_to_canvas(image: Image.Image, size: int = STICKER_SIZE) -> Image.Image:
    """Center ``image`` (preserving aspect ratio) on a transparent size x size canvas."""
    image = image.convert("RGBA")
    scale = size / max(image.size)
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.resize(new_size, Image.LANCZOS)

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    offset = ((size - resized.width) // 2, (size - resized.height) // 2)
    canvas.paste(resized, offset, resized)
    return canvas


def layer_over_background(
    foreground: Image.Image,
    background: Image.Image,
    *,
    foreground_scale: float = 1.0,
) -> Image.Image:
    """Composite ``foreground`` centered on top of ``background``.

    Both images are fit to the sticker canvas first. ``foreground_scale``
    (0-1] shrinks the foreground so some of the background peeks out around
    the edges, which matters for opaque foregrounds like photos - a plain
    text sticker (transparent background) shows the logo through its own
    gaps and rarely needs shrinking.
    """
    canvas = fit_to_canvas(background)
    fg = fit_to_canvas(foreground)

    if foreground_scale < 1.0:
        new_size = tuple(max(1, round(dim * foreground_scale)) for dim in fg.size)
        fg = fg.resize(new_size, Image.LANCZOS)

    offset = ((canvas.width - fg.width) // 2, (canvas.height - fg.height) // 2)
    canvas.paste(fg, offset, fg)
    return canvas
