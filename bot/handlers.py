"""Command and message handlers for the sticker-building bot."""
from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from stickerpack.image_utils import image_to_png_bytes, prepare_sticker_png_bytes
from stickerpack.sticker_api import DEFAULT_EMOJI, add_or_create, build_set_name, pack_link
from stickerpack.text_sticker import TextStickerStyle, render_text_sticker

from .state import MAX_STICKERS_PER_PACK, sessions

logger = logging.getLogger(__name__)

# Matches a single emoji-ish grapheme (covers the common emoji blocks).
EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "✀-➿"
    "☀-⛿"
    "]+",
    flags=re.UNICODE,
)

WELCOME_TEXT = (
    "Salom! Men senga Telegram uchun stiker to'plami yasashda yordam beraman. \U0001F60A\n\n"
    "Buyruqlar:\n"
    "/newpack <nomi> - yangi stiker to'plamini boshlash\n"
    "/addtext <matn> - matndan stiker yasab, to'plamga qo'shish\n"
    "  (ixtiyoriy emoji: /addtext Salom! | \U0001F600)\n"
    "Rasm yuborsang - avtomatik stikerga aylantirib to'plamga qo'shaman\n"
    "  (rasmga izoh sifatida bitta emoji yuborsang, o'shani ishlataman)\n"
    "/done - to'plamni yakunlab, havolasini olish\n"
    "/cancel - joriy to'plamni bekor qilish\n\n"
    "Boshlash uchun: /newpack Mening to'plamim"
)


def extract_emoji(text: str | None) -> str | None:
    if not text:
        return None
    match = EMOJI_RE.search(text)
    return match.group(0)[:1] if match else None


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT)


async def newpack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    title = " ".join(context.args).strip() if context.args else ""
    if not title:
        await update.message.reply_text(
            "To'plam nomini ham yozing: /newpack Mening to'plamim"
        )
        return

    bot_username = (await context.bot.get_me()).username
    set_name = build_set_name(user.id, title.lower().split()[0], bot_username)
    sessions.start(user.id, set_name=set_name, title=title[:64])

    await update.message.reply_text(
        f"✅ '{title}' to'plami boshlandi.\n"
        "Endi menga rasm yuboring yoki matn yozing - har biri to'plamga stiker "
        "sifatida qo'shiladi. Tugatgach /done ni bosing."
    )


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if sessions.get(user.id) is None:
        await update.message.reply_text("Faol to'plam yo'q.")
        return
    sessions.clear(user.id)
    await update.message.reply_text("Bekor qilindi.")


async def done_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text(
            "Faol to'plam yo'q. Yangisini boshlash uchun /newpack nomi"
        )
        return
    if session.count == 0:
        await update.message.reply_text(
            "To'plamga hali birorta stiker qo'shmadingiz. Rasm yoki matn yuboring."
        )
        return

    link = pack_link(session.set_name)
    sessions.clear(user.id)
    await update.message.reply_text(
        f"\U0001F389 Tayyor! {session.count} ta stikerdan iborat to'plam:\n{link}"
    )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text(
            "Avval /newpack nomi buyrug'i bilan to'plam boshlang."
        )
        return
    if session.count >= MAX_STICKERS_PER_PACK:
        await update.message.reply_text(
            f"Bu to'plamda allaqachon {MAX_STICKERS_PER_PACK} ta stiker bor (Telegram "
            "chegarasi). /done bilan yakunlang va yangi to'plam boshlang."
        )
        return

    photo = update.message.photo[-1]
    tg_file = await photo.get_file()
    image_bytes = bytes(await tg_file.download_as_bytearray())

    emoji = extract_emoji(update.message.caption) or DEFAULT_EMOJI

    try:
        png_bytes = prepare_sticker_png_bytes(image_bytes)
        await add_or_create(
            context.bot,
            user_id=user.id,
            set_name=session.set_name,
            title=session.title,
            png_bytes=png_bytes,
            emoji=emoji,
        )
    except (BadRequest, TelegramError) as exc:
        logger.warning("Sticker add failed: %s", exc)
        await update.message.reply_text(f"Xatolik yuz berdi: {exc.message}")
        return
    except Exception:
        logger.exception("Unexpected error while adding sticker")
        await update.message.reply_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    sessions.bump(user.id)
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )


async def addtext_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = update.message.text.partition(" ")[2].strip()
    if not raw:
        await update.message.reply_text("Foydalanish: /addtext Matningiz | \U0001F600 (emoji ixtiyoriy)")
        return
    text, _, emoji_part = raw.partition("|")
    emoji = extract_emoji(emoji_part) or DEFAULT_EMOJI
    await _add_text_sticker(update, context, text.strip(), emoji)


async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if sessions.get(user.id) is None:
        await update.message.reply_text(
            "Avval /newpack nomi bilan to'plam boshlang, keyin menga matn yoki rasm yuboring."
        )
        return
    await _add_text_sticker(update, context, update.message.text.strip(), DEFAULT_EMOJI)


async def _add_text_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str, emoji: str) -> None:
    user = update.effective_user
    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text("Avval /newpack nomi bilan to'plam boshlang.")
        return
    if session.count >= MAX_STICKERS_PER_PACK:
        await update.message.reply_text(
            f"Bu to'plamda allaqachon {MAX_STICKERS_PER_PACK} ta stiker bor. /done bilan yakunlang."
        )
        return
    if not text:
        await update.message.reply_text("Matn bo'sh bo'lmasligi kerak.")
        return

    try:
        image = render_text_sticker(text, TextStickerStyle())
        png_bytes = image_to_png_bytes(image)
        await add_or_create(
            context.bot,
            user_id=user.id,
            set_name=session.set_name,
            title=session.title,
            png_bytes=png_bytes,
            emoji=emoji,
        )
    except (BadRequest, TelegramError) as exc:
        logger.warning("Sticker add failed: %s", exc)
        await update.message.reply_text(f"Xatolik yuz berdi: {exc.message}")
        return
    except Exception:
        logger.exception("Unexpected error while adding text sticker")
        await update.message.reply_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    sessions.bump(user.id)
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )
