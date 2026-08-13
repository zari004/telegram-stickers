"""Thin helpers around python-telegram-bot's sticker-set endpoints."""
from __future__ import annotations

import asyncio
import logging
import re
from io import BytesIO
from typing import Awaitable, Callable, TypeVar

from telegram import Bot, InputSticker
from telegram.error import BadRequest, NetworkError, TimedOut

DEFAULT_EMOJI = "🙂"
MAX_NAME_LEN = 64

RETRY_ATTEMPTS = 3
RETRY_BASE_DELAY = 1.5  # seconds; doubles-ish each retry

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def _with_retry(call: Callable[[], Awaitable[T]]) -> T:
    """Run ``call()`` again on transient network timeouts.

    Sticker-set endpoints upload an image and can be slow on constrained
    hosting (e.g. a free-tier instance), so a handful of retries with
    backoff smooths over occasional ``TimedOut``/``NetworkError`` blips
    instead of failing the whole sticker add.
    """
    last_exc: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            return await call()
        except (TimedOut, NetworkError) as exc:
            last_exc = exc
            if attempt < RETRY_ATTEMPTS - 1:
                logger.warning(
                    "Telegram API call timed out (attempt %d/%d), retrying: %s",
                    attempt + 1,
                    RETRY_ATTEMPTS,
                    exc,
                )
                await asyncio.sleep(RETRY_BASE_DELAY * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def build_set_name(user_id: int, slug: str, bot_username: str) -> str:
    """Build a sticker-set ``name`` that satisfies Telegram's requirements.

    Telegram requires the internal set name to:
      - contain only letters, digits and underscores
      - start with a letter
      - end with ``_by_<bot_username>``
      - be at most 64 characters
    """
    clean_slug = re.sub(r"[^a-zA-Z0-9_]", "_", slug).strip("_") or "pack"
    if not clean_slug[0].isalpha():
        clean_slug = f"p_{clean_slug}"

    suffix = f"_by_{bot_username}"
    user_part = f"_{user_id}"
    # The user id must stay intact (it keeps pack names unique per user);
    # trim the descriptive slug instead if the total would exceed the limit.
    max_slug_len = max(1, MAX_NAME_LEN - len(suffix) - len(user_part))
    clean_slug = clean_slug[:max_slug_len]
    if not clean_slug[0].isalpha():
        clean_slug = ("p" + clean_slug)[:max_slug_len]

    return f"{clean_slug}{user_part}{suffix}"


def pack_link(set_name: str) -> str:
    return f"https://t.me/addstickers/{set_name}"


async def sticker_set_exists(bot: Bot, set_name: str) -> bool:
    try:
        await _with_retry(lambda: bot.get_sticker_set(set_name))
        return True
    except BadRequest:
        return False


async def create_sticker_pack(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    title: str,
    media_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
    sticker_format: str = "static",
) -> None:
    async def call() -> None:
        sticker = InputSticker(sticker=BytesIO(media_bytes), emoji_list=[emoji], format=sticker_format)
        await bot.create_new_sticker_set(
            user_id=user_id,
            name=set_name,
            title=title,
            stickers=[sticker],
        )

    await _with_retry(call)


async def add_sticker_to_pack(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    media_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
    sticker_format: str = "static",
) -> None:
    async def call() -> None:
        sticker = InputSticker(sticker=BytesIO(media_bytes), emoji_list=[emoji], format=sticker_format)
        await bot.add_sticker_to_set(user_id=user_id, name=set_name, sticker=sticker)

    await _with_retry(call)


async def add_or_create(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    title: str,
    media_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
    sticker_format: str = "static",
) -> bool:
    """Add a sticker to ``set_name``, creating the pack first if needed.

    Returns True if a new pack was created, False if a sticker was appended
    to an existing one.
    """
    if await sticker_set_exists(bot, set_name):
        await add_sticker_to_pack(
            bot,
            user_id=user_id,
            set_name=set_name,
            media_bytes=media_bytes,
            emoji=emoji,
            sticker_format=sticker_format,
        )
        return False

    await create_sticker_pack(
        bot,
        user_id=user_id,
        set_name=set_name,
        title=title,
        media_bytes=media_bytes,
        emoji=emoji,
        sticker_format=sticker_format,
    )
    return True
