"""Thin helpers around python-telegram-bot's sticker-set endpoints."""
from __future__ import annotations

import re
from io import BytesIO

from telegram import Bot, InputSticker
from telegram.error import BadRequest

DEFAULT_EMOJI = "🙂"
MAX_NAME_LEN = 64


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
        await bot.get_sticker_set(set_name)
        return True
    except BadRequest:
        return False


async def create_sticker_pack(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    title: str,
    png_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
) -> None:
    sticker = InputSticker(
        sticker=BytesIO(png_bytes),
        emoji_list=[emoji],
        format="static",
    )
    await bot.create_new_sticker_set(
        user_id=user_id,
        name=set_name,
        title=title,
        stickers=[sticker],
    )


async def add_sticker_to_pack(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    png_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
) -> None:
    sticker = InputSticker(
        sticker=BytesIO(png_bytes),
        emoji_list=[emoji],
        format="static",
    )
    await bot.add_sticker_to_set(user_id=user_id, name=set_name, sticker=sticker)


async def add_or_create(
    bot: Bot,
    *,
    user_id: int,
    set_name: str,
    title: str,
    png_bytes: bytes,
    emoji: str = DEFAULT_EMOJI,
) -> bool:
    """Add a sticker to ``set_name``, creating the pack first if needed.

    Returns True if a new pack was created, False if a sticker was appended
    to an existing one.
    """
    if await sticker_set_exists(bot, set_name):
        await add_sticker_to_pack(
            bot, user_id=user_id, set_name=set_name, png_bytes=png_bytes, emoji=emoji
        )
        return False

    await create_sticker_pack(
        bot,
        user_id=user_id,
        set_name=set_name,
        title=title,
        png_bytes=png_bytes,
        emoji=emoji,
    )
    return True
