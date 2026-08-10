"""Command, button and message handlers for the sticker-building bot.

Everything is reachable two ways: as a typed command (/newpack, /style, ...)
for people who like that, and as inline-keyboard buttons reachable from
/start's main menu for people who don't want to remember commands.
"""
from __future__ import annotations

import logging
import re
from dataclasses import replace
from io import BytesIO

from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from stickerpack import logo_store, pack_registry
from stickerpack.compose import layer_over_background
from stickerpack.config import FONTS_DIR
from stickerpack.image_utils import image_to_png_bytes, prepare_sticker_image
from stickerpack.sticker_api import DEFAULT_EMOJI, add_or_create, build_set_name, pack_link
from stickerpack.text_sticker import TextStickerStyle, render_text_sticker

from .state import MAX_STICKERS_PER_PACK, prefs, sessions

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
    "Quyidagi tugmalardan birini tanla, yoki buyruqlardan foydalan:\n"
    "/newpack <nomi>, /addtext <matn>, /style, /company, /mypacks, /done, /cancel"
)

BG_CHOICES = [
    ("Shaffof", None),
    ("Oq", "FFFFFF"),
    ("Sariq", "FFD600"),
    ("Ko'k", "2D9CDB"),
    ("Yashil", "27AE60"),
    ("Pushti", "EB5757"),
    ("Qora", "1E1E1E"),
]
TEXT_COLOR_CHOICES = [
    ("Qora", "1E1E1E"),
    ("Oq", "FFFFFF"),
    ("Sariq", "FFD600"),
    ("Qizil", "EB5757"),
    ("Ko'k", "2D9CDB"),
]
FONT_CHOICES = [
    ("Qalin", "DejaVuSans-Bold.ttf"),
    ("Oddiy", "DejaVuSans.ttf"),
    ("Klassik", "DejaVuSerif-Bold.ttf"),
    ("Mashinka", "DejaVuSansMono-Bold.ttf"),
]

COMPANY_PHOTO_SCALE = 0.82  # shrink uploaded photos so the logo frames them


def extract_emoji(text: str | None) -> str | None:
    if not text:
        return None
    match = EMOJI_RE.search(text)
    return match.group(0)[:1] if match else None


def _font_path(filename: str) -> str:
    return str(FONTS_DIR / filename)


def _font_name(font_path: str | None) -> str:
    resolved = font_path or _font_path(FONT_CHOICES[0][1])
    for name, filename in FONT_CHOICES:
        if _font_path(filename) == resolved:
            return name
    return FONT_CHOICES[0][0]


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _hex_to_rgba(hex_value: str | None) -> tuple[int, int, int, int] | None:
    if hex_value is None:
        return None
    r, g, b = (int(hex_value[i : i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, 255)


HEX_INPUT_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_hex_input(text: str) -> tuple[int, int, int, int] | None:
    match = HEX_INPUT_RE.match(text.strip())
    return _hex_to_rgba(match.group(1)) if match else None


# --------------------------------------------------------------------------
# Main menu
# --------------------------------------------------------------------------


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("\U0001F195 Yangi to'plam", callback_data="menu:newpack")],
            [InlineKeyboardButton("\U0001F4E6 Mening to'plamlarim", callback_data="menu:mypacks")],
            [InlineKeyboardButton("\U0001F3A8 Stil sozlash", callback_data="menu:style")],
            [InlineKeyboardButton("\U0001F3E2 Kompaniya logotipi", callback_data="menu:company")],
            [InlineKeyboardButton("❓ Yordam", callback_data="menu:help")],
        ]
    )


def _back_to_menu_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")]])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, reply_markup=_main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME_TEXT, reply_markup=_main_menu_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    action = query.data.split(":", 1)[1]
    await query.answer()

    if action == "newpack":
        prefs.get(user.id).awaiting_new_pack_title = True
        await query.edit_message_text(
            "\U0001F195 Yangi to'plam uchun nom yozing (masalan: Mening kulgichlarim)."
        )
    elif action == "mypacks":
        await _render_mypacks(user.id, query.edit_message_text)
    elif action == "style":
        style = prefs.get(user.id).style
        await query.edit_message_text(_style_summary(style), reply_markup=_style_keyboard(style))
    elif action == "company":
        await _render_company(user.id, query.edit_message_text)
    elif action == "help":
        await query.edit_message_text(WELCOME_TEXT, reply_markup=_main_menu_keyboard())


# --------------------------------------------------------------------------
# New pack / continue / cancel / done
# --------------------------------------------------------------------------


async def _start_new_pack(user_id: int, title: str, bot_username: str) -> None:
    set_name = build_set_name(user_id, title.lower().split()[0], bot_username)
    sessions.start(user_id, set_name=set_name, title=title[:64])


async def newpack_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    title = " ".join(context.args).strip() if context.args else ""
    if not title:
        await update.message.reply_text("To'plam nomini ham yozing: /newpack Mening to'plamim")
        return

    bot_username = (await context.bot.get_me()).username
    await _start_new_pack(user.id, title, bot_username)
    await update.message.reply_text(
        f"✅ '{title}' to'plami boshlandi.\n"
        "Endi menga rasm yuboring yoki matn yozing - har biri to'plamga stiker "
        "sifatida qo'shiladi. Tugatgach /done ni bosing.\n\n"
        "Xohlasangiz avval /style bilan ko'rinishni yoki /company bilan "
        "kompaniya logotipini sozlashingiz mumkin."
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
        await update.message.reply_text("Faol to'plam yo'q. Yangisini boshlash uchun /newpack nomi")
        return
    if session.count == 0:
        await update.message.reply_text("To'plamga hali birorta stiker qo'shmadingiz. Rasm yoki matn yuboring.")
        return

    link = pack_link(session.set_name)
    sessions.clear(user.id)
    await update.message.reply_text(f"\U0001F389 Tayyor! {session.count} ta stikerdan iborat to'plam:\n{link}")


# --------------------------------------------------------------------------
# Style picker
# --------------------------------------------------------------------------


def _color_name(choices: list[tuple[str, str | None]], color: tuple | None) -> str:
    for name, hex_value in choices:
        if _hex_to_rgba(hex_value) == color:
            return name
    return "-"


def _style_summary(style: TextStickerStyle) -> str:
    outline_label = "yoniq" if style.outline_color else "o'chiq"
    return (
        "\U0001F3A8 Matnli stiker stili:\n"
        f"Fon: {_color_name(BG_CHOICES, style.background_color)}\n"
        f"Matn rangi: {_color_name(TEXT_COLOR_CHOICES, style.text_color)}\n"
        f"Chiziq: {outline_label}\n"
        f"Shrift: {_font_name(style.font_path)}\n\n"
        "Tugmalar orqali o'zgartiring:"
    )


def _style_keyboard(style: TextStickerStyle) -> InlineKeyboardMarkup:
    def mark(label: str, selected: bool) -> str:
        return f"✅ {label}" if selected else label

    bg_buttons = [
        InlineKeyboardButton(
            mark(name, _hex_to_rgba(hex_v) == style.background_color),
            callback_data=f"style:bg:{hex_v or 'none'}",
        )
        for name, hex_v in BG_CHOICES
    ]
    text_buttons = [
        InlineKeyboardButton(
            mark(name, _hex_to_rgba(hex_v) == style.text_color),
            callback_data=f"style:text:{hex_v}",
        )
        for name, hex_v in TEXT_COLOR_CHOICES
    ]
    current_font = style.font_path or _font_path(FONT_CHOICES[0][1])
    font_buttons = [
        InlineKeyboardButton(
            mark(name, _font_path(filename) == current_font),
            callback_data=f"style:font:{filename}",
        )
        for name, filename in FONT_CHOICES
    ]
    outline_label = "\U0001F532 Chiziq: YONIQ" if style.outline_color else "⬜ Chiziq: O'CHIQ"

    rows = [
        *_chunk(bg_buttons, 4),
        [InlineKeyboardButton("\U0001F3A8 Boshqa fon rangi (HEX)", callback_data="style:custompick:bg")],
        *_chunk(text_buttons, 3),
        [InlineKeyboardButton("\U0001F3A8 Boshqa matn rangi (HEX)", callback_data="style:custompick:text")],
        *_chunk(font_buttons, 2),
        [InlineKeyboardButton(outline_label, callback_data="style:outline:toggle")],
        [InlineKeyboardButton("✅ Saqlash", callback_data="style:close")],
    ]
    return InlineKeyboardMarkup(rows)


async def style_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    style = prefs.get(update.effective_user.id).style
    await update.message.reply_text(_style_summary(style), reply_markup=_style_keyboard(style))


async def style_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_prefs = prefs.get(user.id)
    _, kind, value = query.data.split(":", 2)

    if kind == "close":
        await query.answer("Saqlandi ✅")
        await query.edit_message_text(
            "Stil saqlandi. Endi yangi matnli stikerlar shu uslubda chiqadi.",
            reply_markup=_back_to_menu_button(),
        )
        return

    if kind == "custompick":
        user_prefs.awaiting_custom_color = value  # "bg" or "text"
        target = "fon" if value == "bg" else "matn"
        await query.answer()
        await query.edit_message_text(
            f"\U0001F3A8 {target.capitalize()} rangi uchun HEX kod yuboring, masalan: #FF5733"
        )
        return

    if kind == "bg":
        user_prefs.style.background_color = None if value == "none" else _hex_to_rgba(value)
    elif kind == "text":
        user_prefs.style.text_color = _hex_to_rgba(value)
    elif kind == "outline":
        user_prefs.style.outline_color = None if user_prefs.style.outline_color else (255, 255, 255, 255)
    elif kind == "font":
        user_prefs.style.font_path = _font_path(value)

    await query.answer()
    await query.edit_message_text(_style_summary(user_prefs.style), reply_markup=_style_keyboard(user_prefs.style))


# --------------------------------------------------------------------------
# Company logo
# --------------------------------------------------------------------------


def _company_text(user_id: int, company_mode: bool) -> str:
    has_logo = logo_store.has_logo(user_id)
    logo_line = "Logotip: ✅ yuklangan\n" if has_logo else "Logotip: ❌ hali yuklanmagan\n"
    mode_line = "Rejim: \U0001F7E2 YONIQ" if company_mode else "Rejim: ⚪ O'CHIQ"
    return (
        "\U0001F3E2 Kompaniya rejimi\n\n"
        + logo_line
        + mode_line
        + "\n\nYoqilgan bo'lsa, logotipingiz yangi matnli va rasmli stikerlarning "
        "orqa foniga avtomatik qo'yiladi."
    )


def _company_keyboard(has_logo: bool, company_mode: bool) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("\U0001F4E4 Logotip yuklash/almashtirish", callback_data="company:setlogo")]]
    if has_logo:
        toggle_label = "⚪ Rejimni o'chirish" if company_mode else "\U0001F7E2 Rejimni yoqish"
        rows.append([InlineKeyboardButton(toggle_label, callback_data="company:toggle")])
        rows.append([InlineKeyboardButton("\U0001F5D1 Logotipni o'chirish", callback_data="company:delete")])
    rows.append([InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")])
    return InlineKeyboardMarkup(rows)


async def _render_company(user_id: int, send) -> None:
    user_prefs = prefs.get(user_id)
    has_logo = logo_store.has_logo(user_id)
    await send(
        _company_text(user_id, user_prefs.company_mode),
        reply_markup=_company_keyboard(has_logo, user_prefs.company_mode),
    )


async def company_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_company(update.effective_user.id, update.message.reply_text)


async def company_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_prefs = prefs.get(user.id)
    action = query.data.split(":", 1)[1]

    if action == "setlogo":
        user_prefs.awaiting_logo = True
        await query.answer()
        await query.edit_message_text("\U0001F4E4 Endi menga kompaniya logotipini rasm qilib yuboring.")
        return
    if action == "toggle":
        if not logo_store.has_logo(user.id):
            await query.answer("Avval logotip yuklang.", show_alert=True)
            return
        user_prefs.company_mode = not user_prefs.company_mode
    elif action == "delete":
        logo_store.delete_logo(user.id)
        user_prefs.company_mode = False

    await query.answer()
    has_logo = logo_store.has_logo(user.id)
    await query.edit_message_text(
        _company_text(user.id, user_prefs.company_mode),
        reply_markup=_company_keyboard(has_logo, user_prefs.company_mode),
    )


def _apply_company_overlay(user_id: int, image: Image.Image, *, is_photo: bool) -> Image.Image:
    user_prefs = prefs.get(user_id)
    if not user_prefs.company_mode:
        return image
    logo = logo_store.load_logo(user_id)
    if logo is None:
        return image
    scale = COMPANY_PHOTO_SCALE if is_photo else 1.0
    return layer_over_background(image, logo, foreground_scale=scale)


# --------------------------------------------------------------------------
# My packs (list / continue / rename / delete)
# --------------------------------------------------------------------------


def _packs_keyboard(packs: list[pack_registry.PackRecord]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(f"{record.title} ({record.count})", callback_data=f"pack:open:{i}")]
        for i, record in enumerate(packs)
    ]
    rows.append([InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")])
    return InlineKeyboardMarkup(rows)


def _pack_menu_keyboard(idx: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ Davom qo'shish", callback_data=f"pack:continue:{idx}")],
            [InlineKeyboardButton("✏️ Nomini o'zgartirish", callback_data=f"pack:rename:{idx}")],
            [InlineKeyboardButton("\U0001F5D1 O'chirish", callback_data=f"pack:delete:{idx}")],
            [InlineKeyboardButton("\U0001F519 Ro'yxatga qaytish", callback_data="pack:back")],
        ]
    )


async def _render_mypacks(user_id: int, send) -> None:
    packs = pack_registry.list_packs(user_id)
    if not packs:
        await send(
            "Sizda hali stiker to'plamlaringiz yo'q. /newpack orqali birinchisini yarating.",
            reply_markup=_back_to_menu_button(),
        )
        return
    await send("\U0001F4E6 Sizning stiker to'plamlaringiz:", reply_markup=_packs_keyboard(packs))


async def mypacks_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _render_mypacks(update.effective_user.id, update.message.reply_text)


async def pack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    parts = query.data.split(":")
    action = parts[1]

    if action == "back":
        await query.answer()
        await _render_mypacks(user.id, query.edit_message_text)
        return

    idx = int(parts[2])
    packs = pack_registry.list_packs(user.id)
    if idx >= len(packs):
        await query.answer("Bu to'plam topilmadi (ro'yxat yangilangan bo'lishi mumkin).", show_alert=True)
        return
    record = packs[idx]

    if action == "open":
        await query.answer()
        await query.edit_message_text(
            f"\U0001F4E6 {record.title}\n{record.count} ta stiker\n{pack_link(record.name)}",
            reply_markup=_pack_menu_keyboard(idx),
        )
    elif action == "continue":
        session = sessions.start(user.id, set_name=record.name, title=record.title)
        session.count = record.count
        await query.answer()
        await query.edit_message_text(
            f"✅ '{record.title}' to'plamiga davom etyapsiz. Rasm yoki matn yuboring, "
            "tugatgach /done bosing."
        )
    elif action == "rename":
        prefs.get(user.id).awaiting_rename_for = record.name
        await query.answer()
        await query.edit_message_text(f"✏️ '{record.title}' uchun yangi nomni matn qilib yuboring.")
    elif action == "delete":
        await query.answer()
        await query.edit_message_text(
            f"\U0001F5D1 '{record.title}' to'plamini rostdan o'chirmoqchimisiz? Bu qaytarib bo'lmaydi.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("✅ Ha, o'chirish", callback_data=f"pack:confirmdelete:{idx}"),
                        InlineKeyboardButton("❌ Bekor qilish", callback_data=f"pack:open:{idx}"),
                    ]
                ]
            ),
        )
    elif action == "confirmdelete":
        try:
            await context.bot.delete_sticker_set(record.name)
        except (BadRequest, TelegramError) as exc:
            await query.answer()
            await query.edit_message_text(f"Xatolik: {exc.message}")
            return
        pack_registry.remove_pack(user.id, record.name)
        active = sessions.get(user.id)
        if active and active.set_name == record.name:
            sessions.clear(user.id)
        await query.answer("O'chirildi")
        await query.edit_message_text(
            f"\U0001F5D1 '{record.title}' o'chirildi.", reply_markup=_back_to_menu_button()
        )


# --------------------------------------------------------------------------
# Photo -> sticker
# --------------------------------------------------------------------------


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_prefs = prefs.get(user.id)

    if user_prefs.awaiting_logo:
        photo = update.message.photo[-1]
        tg_file = await photo.get_file()
        image_bytes = bytes(await tg_file.download_as_bytearray())
        logo_store.save_logo(user.id, Image.open(BytesIO(image_bytes)))
        user_prefs.awaiting_logo = False
        user_prefs.company_mode = True
        await update.message.reply_text(
            "✅ Logotip saqlandi va kompaniya rejimi yoqildi. Endi yuboradigan barcha "
            "stikerlar shu logotip foniga qo'yiladi. /company orqali o'chirish yoki o'zgartirish mumkin."
        )
        return

    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text(
            "Avval yangi to'plam boshlang: /newpack nomi yoki /start dagi \U0001F195 tugmasi orqali."
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
        image = prepare_sticker_image(image_bytes)
        image = _apply_company_overlay(user.id, image, is_photo=True)
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
        logger.exception("Unexpected error while adding sticker")
        await update.message.reply_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    sessions.bump(user.id)
    pack_registry.upsert_pack(user.id, session.set_name, session.title, session.count)
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )


# --------------------------------------------------------------------------
# Text -> sticker / rename / new pack title
# --------------------------------------------------------------------------


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
    user_prefs = prefs.get(user.id)
    text = update.message.text.strip()

    if user_prefs.awaiting_new_pack_title:
        user_prefs.awaiting_new_pack_title = False
        if not text:
            await update.message.reply_text("Nom bo'sh bo'lmasligi kerak. Qayta urinib ko'ring: /newpack nomi")
            return
        bot_username = (await context.bot.get_me()).username
        await _start_new_pack(user.id, text, bot_username)
        await update.message.reply_text(
            f"✅ '{text}' to'plami boshlandi.\n"
            "Endi menga rasm yuboring yoki matn yozing - har biri to'plamga stiker "
            "sifatida qo'shiladi. Tugatgach /done ni bosing."
        )
        return

    if user_prefs.awaiting_custom_color:
        target = user_prefs.awaiting_custom_color  # "bg" or "text"
        color = _parse_hex_input(text)
        if color is None:
            await update.message.reply_text(
                "Bu HEX kod emas. Masalan: #FF5733 yoki FF5733 shaklida yuboring, "
                "yoki qayta urinmaslik uchun /style ni qayta oching."
            )
            return
        user_prefs.awaiting_custom_color = None
        if target == "bg":
            user_prefs.style.background_color = color
        else:
            user_prefs.style.text_color = color
        await update.message.reply_text(
            _style_summary(user_prefs.style), reply_markup=_style_keyboard(user_prefs.style)
        )
        return

    if user_prefs.awaiting_rename_for:
        set_name = user_prefs.awaiting_rename_for
        user_prefs.awaiting_rename_for = None
        new_title = text[:64]
        if not new_title:
            await update.message.reply_text("Nom bo'sh bo'lmasligi kerak.")
            return
        try:
            await context.bot.set_sticker_set_title(name=set_name, title=new_title)
        except (BadRequest, TelegramError) as exc:
            await update.message.reply_text(f"Xatolik: {exc.message}")
            return
        pack_registry.rename_pack(user.id, set_name, new_title)
        active = sessions.get(user.id)
        if active and active.set_name == set_name:
            active.title = new_title
        await update.message.reply_text(f"✅ Nomi '{new_title}' ga o'zgartirildi.")
        return

    if sessions.get(user.id) is None:
        await update.message.reply_text(
            "Avval yangi to'plam boshlang: /newpack nomi yoki /start dagi \U0001F195 tugmasi orqali."
        )
        return
    await _add_text_sticker(update, context, text, DEFAULT_EMOJI)


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

    user_prefs = prefs.get(user.id)
    style = user_prefs.style
    has_logo = user_prefs.company_mode and logo_store.has_logo(user.id)
    if has_logo and style.background_color is not None:
        style = replace(style, background_color=None)  # let the logo show through

    try:
        image = render_text_sticker(text, style)
        image = _apply_company_overlay(user.id, image, is_photo=False)
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
    pack_registry.upsert_pack(user.id, session.set_name, session.title, session.count)
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )
