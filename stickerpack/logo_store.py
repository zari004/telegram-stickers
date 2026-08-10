"""Persist a per-user company logo, used as a sticker background layer.

Stored as a plain PNG on disk. Note: on free hosting tiers without a
persistent disk (see README), this directory can be wiped on redeploy or
restart - users may need to re-upload their logo occasionally.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from .config import ROOT_DIR

LOGOS_DIR = ROOT_DIR / "data" / "logos"


def _logo_path(user_id: int) -> Path:
    return LOGOS_DIR / f"{user_id}.png"


def save_logo(user_id: int, image: Image.Image) -> None:
    LOGOS_DIR.mkdir(parents=True, exist_ok=True)
    image.convert("RGBA").save(_logo_path(user_id))


def load_logo(user_id: int) -> Image.Image | None:
    path = _logo_path(user_id)
    if not path.exists():
        return None
    return Image.open(path).convert("RGBA")


def has_logo(user_id: int) -> bool:
    return _logo_path(user_id).exists()


def delete_logo(user_id: int) -> None:
    _logo_path(user_id).unlink(missing_ok=True)
