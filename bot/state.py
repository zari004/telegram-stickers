"""In-memory per-user bot state: the pack currently being built, and prefs."""
from __future__ import annotations

from dataclasses import dataclass, field

from stickerpack.text_sticker import TextStickerStyle

MAX_STICKERS_PER_PACK = 120


@dataclass
class PackSession:
    set_name: str
    title: str
    count: int = 0


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, PackSession] = {}

    def get(self, user_id: int) -> PackSession | None:
        return self._sessions.get(user_id)

    def start(self, user_id: int, set_name: str, title: str) -> PackSession:
        session = PackSession(set_name=set_name, title=title)
        self._sessions[user_id] = session
        return session

    def clear(self, user_id: int) -> None:
        self._sessions.pop(user_id, None)

    def bump(self, user_id: int) -> None:
        session = self._sessions.get(user_id)
        if session:
            session.count += 1


@dataclass
class UserPrefs:
    """Sticky per-user settings and short-lived "waiting for a reply" flags."""

    style: TextStickerStyle = field(default_factory=TextStickerStyle)
    company_mode: bool = False
    logo_outline_color: tuple[int, int, int, int] | None = None
    resize_width: int = 1080
    resize_height: int = 1080
    resize_dpi: int = 72
    resize_mode: bool = False
    awaiting_logo: bool = False
    awaiting_new_pack_title: bool = False
    awaiting_rename_for: str | None = None
    awaiting_custom_color: str | None = None  # "bg" or "text"
    awaiting_resize_field: str | None = None  # "width", "height" or "dpi"


class PrefsStore:
    def __init__(self) -> None:
        self._prefs: dict[int, UserPrefs] = {}

    def get(self, user_id: int) -> UserPrefs:
        return self._prefs.setdefault(user_id, UserPrefs())


sessions = SessionStore()
prefs = PrefsStore()
