"""Tiny in-memory session store: one active pack-being-built per user."""
from __future__ import annotations

from dataclasses import dataclass, field

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


sessions = SessionStore()
