"""Persisted registry of sticker packs each user has created via this bot.

Telegram's Bot API has no "list my sticker sets" endpoint, so the bot has
to remember what it created itself in order to offer a /mypacks list, and
to know which pack names belong to which user.

Note: on free hosting tiers without a persistent disk (see README), this
file can be wiped on redeploy or restart.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import ROOT_DIR

REGISTRY_PATH = ROOT_DIR / "data" / "packs.json"
_lock = threading.Lock()


@dataclass
class PackRecord:
    name: str
    title: str
    count: int = 0
    sticker_format: str = "static"  # "static" or "video"
    created_at: str = ""


def _load() -> dict[str, list[dict]]:
    if not REGISTRY_PATH.exists():
        return {}
    raw = REGISTRY_PATH.read_text(encoding="utf-8").strip()
    return json.loads(raw) if raw else {}


def _save(data: dict[str, list[dict]]) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_packs(user_id: int) -> list[PackRecord]:
    with _lock:
        data = _load()
    return [PackRecord(**rec) for rec in data.get(str(user_id), [])]


def get_pack(user_id: int, name: str) -> PackRecord | None:
    for record in list_packs(user_id):
        if record.name == name:
            return record
    return None


def upsert_pack(user_id: int, name: str, title: str, count: int, sticker_format: str = "static") -> None:
    with _lock:
        data = _load()
        records = data.setdefault(str(user_id), [])
        for rec in records:
            if rec["name"] == name:
                rec["title"] = title
                rec["count"] = count
                rec["sticker_format"] = sticker_format
                break
        else:
            records.append(
                {
                    "name": name,
                    "title": title,
                    "count": count,
                    "sticker_format": sticker_format,
                    "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
        _save(data)


def remove_pack(user_id: int, name: str) -> None:
    with _lock:
        data = _load()
        key = str(user_id)
        data[key] = [rec for rec in data.get(key, []) if rec["name"] != name]
        _save(data)


def rename_pack(user_id: int, name: str, new_title: str) -> None:
    with _lock:
        data = _load()
        for rec in data.get(str(user_id), []):
            if rec["name"] == name:
                rec["title"] = new_title
                break
        _save(data)
