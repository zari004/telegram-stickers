"""Layer a sticker's content on top of a background image (e.g. a company logo)."""
from __future__ import annotations

from PIL import Image, ImageFilter

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


def add_watermark(
    base: Image.Image,
    logo: Image.Image,
    *,
    scale: float = 0.22,
    margin: int = 22,
) -> Image.Image:
    """Paste ``logo`` small in the bottom-right corner of ``base``, as a watermark.

    ``scale`` caps the logo's longest side at that fraction of the canvas
    (e.g. 0.22 = at most 22% of the sticker's width/height), so it reads as
    a small badge rather than taking over the sticker.
    """
    base = fit_to_canvas(base)
    logo = logo.convert("RGBA")

    target = max(1, round(base.width * scale))
    logo_scale = target / max(logo.size)
    new_size = (max(1, round(logo.width * logo_scale)), max(1, round(logo.height * logo_scale)))
    logo_resized = logo.resize(new_size, Image.LANCZOS)

    x = base.width - logo_resized.width - margin
    y = base.height - logo_resized.height - margin

    result = base.copy()
    result.alpha_composite(logo_resized, (x, y))
    return result


def add_outline(
    image: Image.Image,
    color: tuple[int, int, int, int] = (255, 255, 255, 255),
    width: int = 10,
) -> Image.Image:
    """Draw a solid-color stroke around the opaque silhouette of ``image``.

    Works by dilating the alpha channel (a max-filter over a ``width``-sized
    window) into a solid ``color`` layer, then drawing the original image on
    top. A fully-opaque rectangular photo just gets a plain border; a PNG
    logo with real transparency gets a stroke that traces its shape.
    """
    image = image.convert("RGBA")
    alpha = image.split()[-1]
    kernel_size = max(1, width) * 2 + 1
    dilated_alpha = alpha.filter(ImageFilter.MaxFilter(kernel_size))

    stroke_layer = Image.new("RGBA", image.size, color[:3] + (0,))
    stroke_layer.putalpha(dilated_alpha)

    result = Image.new("RGBA", image.size, (0, 0, 0, 0))
    result.alpha_composite(stroke_layer)
    result.alpha_composite(image)
    return result
