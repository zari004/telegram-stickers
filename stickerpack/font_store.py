"""Persist per-user custom fonts (.ttf/.otf) uploaded for text stickers.

Note: on free hosting tiers without a persistent disk (see README), this
directory can be wiped on redeploy or restart.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import ImageFont

from .config import ROOT_DIR

FONTS_ROOT = ROOT_DIR / "data" / "user_fonts"
MAX_FONTS_PER_USER = 10


@dataclass
class CustomFont:
    name: str
    path: Path


def _user_dir(user_id: int) -> Path:
    return FONTS_ROOT / str(user_id)


def _safe_filename(filename: str) -> str:
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()
    clean_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_") or "font"
    return f"{clean_stem}{suffix}"


def validate_font_bytes(data: bytes) -> bool:
    try:
        ImageFont.truetype(BytesIO(data), size=40)
        return True
    except Exception:
        return False


def save_font(user_id: int, filename: str, data: bytes) -> CustomFont:
    if not validate_font_bytes(data):
        raise ValueError("Bu fayl to'g'ri TTF/OTF shrift emas")

    user_dir = _user_dir(user_id)
    user_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _safe_filename(filename)
    path = user_dir / safe_name
    path.write_bytes(data)
    return CustomFont(name=path.stem, path=path)


def list_fonts(user_id: int) -> list[CustomFont]:
    user_dir = _user_dir(user_id)
    if not user_dir.is_dir():
        return []
    return sorted(
        (CustomFont(name=p.stem, path=p) for p in user_dir.iterdir() if p.suffix.lower() in (".ttf", ".otf")),
        key=lambda f: f.name.lower(),
    )


def delete_font(user_id: int, name: str) -> None:
    for font in list_fonts(user_id):
        if font.name == name:
            font.path.unlink(missing_ok=True)
            return
