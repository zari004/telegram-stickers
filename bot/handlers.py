"""Command, button and message handlers for the sticker-building bot.

Everything is reachable two ways: as a typed command (/newpack, /style, ...)
for people who like that, and as inline-keyboard buttons reachable from
/start's main menu for people who don't want to remember commands.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import replace
from functools import partial
from io import BytesIO
from pathlib import Path

from PIL import Image
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import ContextTypes

from stickerpack import logo_store, pack_registry
from stickerpack.compose import add_outline, add_watermark
from stickerpack.config import FONTS_DIR
from stickerpack.image_utils import image_to_png_bytes, prepare_sticker_image
from stickerpack.resizer import MAX_DIMENSION, MIN_DIMENSION, image_to_png_bytes_with_dpi, resize_to_canvas
from stickerpack.sticker_api import DEFAULT_EMOJI, add_or_create, build_set_name, pack_link
from stickerpack.text_sticker import TextStickerStyle, render_text_sticker
from stickerpack.video_sticker import convert_to_video_sticker

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
    "/newpack <nomi>, /addtext <matn>, /style, /company, /mypacks, /resize, /done, /cancel"
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
GRADIENT_TEXT_KEY = "GRADIENT_GREEN"
GREEN_GRADIENT: tuple[tuple[int, int, int, int], tuple[int, int, int, int]] = (
    (17, 153, 142, 255),
    (56, 239, 125, 255),
)
TEXT_COLOR_CHOICES = [
    ("\U0001F49A Yashil gradient", GRADIENT_TEXT_KEY),
    ("Qora", "1E1E1E"),
    ("Oq", "FFFFFF"),
    ("Sariq", "FFD600"),
    ("Qizil", "EB5757"),
    ("Ko'k", "2D9CDB"),
]
OUTLINE_COLOR_CHOICES = [
    ("O'CHIQ", None),
    ("Oq", "FFFFFF"),
    ("Qora", "1E1E1E"),
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
LOGO_OUTLINE_STATES: list[tuple[str, tuple[int, int, int, int] | None]] = [
    ("O'CHIQ", None),
    ("Oq", (255, 255, 255, 255)),
    ("Qora", (30, 30, 30, 255)),
]
LOGO_OUTLINE_WIDTH = 14

# (label, width, height, dpi_or_None) - dpi=None leaves the user's current DPI untouched
RESIZE_PRESETS: list[tuple[str, int, int, int | None]] = [
    ("Infografika (1080x1440, 300 dpi)", 1080, 1440, 300),
    ("Instagram post (1080x1080)", 1080, 1080, None),
    ("Instagram Story (1080x1920)", 1080, 1920, None),
    ("A4 chop etish (2480x3508, 300 dpi)", 2480, 3508, 300),
]


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


def _colors_clash(a: tuple[int, int, int, int] | None, b: tuple[int, int, int, int] | None) -> bool:
    """True if two colors are close enough that text drawn in `a` with an
    outline in `b` would be hard to tell apart (same color picked for both,
    or near-identical shades)."""
    if a is None or b is None:
        return False
    return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5 < 40


HEX_INPUT_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_hex_input(text: str) -> tuple[int, int, int, int] | None:
    match = HEX_INPUT_RE.match(text.strip())
    return _hex_to_rgba(match.group(1)) if match else None


async def _safe_edit_message_text(query, text: str, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Like ``query.edit_message_text``, but swallows Telegram's "message is
    not modified" error.

    That error fires whenever a button is tapped but the resulting text +
    keyboard are byte-identical to what's already shown (e.g. re-selecting
    an option that's already active). Without this, the tap silently does
    nothing from the user's perspective - the loading spinner clears (since
    ``query.answer()`` already ran) but the crash prevents any visible
    change or feedback.
    """
    try:
        await query.edit_message_text(text, reply_markup=reply_markup)
    except BadRequest as exc:
        if "Message is not modified" not in str(exc):
            raise


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
            [InlineKeyboardButton("\U0001F5BC Rasm o'lchamini o'zgartirish", callback_data="menu:resize")],
            [InlineKeyboardButton("❓ Yordam", callback_data="menu:help")],
        ]
    )


def _back_to_menu_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")]])


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prefs.get(update.effective_user.id).resize_mode = False
    await update.message.reply_text(WELCOME_TEXT, reply_markup=_main_menu_keyboard())


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prefs.get(update.effective_user.id).resize_mode = False
    await update.message.reply_text(WELCOME_TEXT, reply_markup=_main_menu_keyboard())


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    action = query.data.split(":", 1)[1]
    await query.answer()

    if action == "newpack":
        user_prefs = prefs.get(user.id)
        user_prefs.resize_mode = False
        user_prefs.awaiting_new_pack_title = True
        await _safe_edit_message_text(query,
            "\U0001F195 Yangi to'plam uchun nom yozing (masalan: Mening kulgichlarim)."
        )
    elif action == "mypacks":
        await _render_mypacks(user.id, partial(_safe_edit_message_text, query))
    elif action == "style":
        style = prefs.get(user.id).style
        await _safe_edit_message_text(query, _style_summary(style), reply_markup=_style_keyboard(style))
    elif action == "company":
        await _render_company(user.id, partial(_safe_edit_message_text, query))
    elif action == "resize":
        user_prefs = prefs.get(user.id)
        user_prefs.resize_mode = True
        await _safe_edit_message_text(query, _resize_text(user_prefs), reply_markup=_resize_keyboard())
    elif action == "help":
        prefs.get(user.id).resize_mode = False
        await _safe_edit_message_text(query, WELCOME_TEXT, reply_markup=_main_menu_keyboard())


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

    prefs.get(user.id).resize_mode = False
    bot_username = (await context.bot.get_me()).username
    await _start_new_pack(user.id, title, bot_username)
    await update.message.reply_text(
        f"✅ '{title}' to'plami boshlandi.\n"
        "Endi menga rasm yuboring, matn yozing yoki GIF/animatsiya yuboring - har biri "
        "to'plamga stiker sifatida qo'shiladi (rasm/matn va GIF stikerlarini bitta "
        "to'plamda aralashtirib bo'lmaydi - birinchi qo'shgan turingiz shu to'plamning "
        "formatini belgilaydi). Tugatgach /done ni bosing.\n\n"
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
        if hex_value == GRADIENT_TEXT_KEY:
            continue
        if _hex_to_rgba(hex_value) == color:
            return name
    return "-"


def _text_color_name(style: TextStickerStyle) -> str:
    if style.text_gradient:
        return TEXT_COLOR_CHOICES[0][0]
    return _color_name(TEXT_COLOR_CHOICES, style.text_color)


def _style_summary(style: TextStickerStyle) -> str:
    return (
        "\U0001F3A8 Matnli stiker stili:\n"
        f"Fon: {_color_name(BG_CHOICES, style.background_color)}\n"
        f"Matn rangi: {_text_color_name(style)}\n"
        f"Chiziq rangi: {_color_name(OUTLINE_COLOR_CHOICES, style.outline_color)}\n"
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
    text_buttons = []
    for name, hex_v in TEXT_COLOR_CHOICES:
        if hex_v == GRADIENT_TEXT_KEY:
            selected = style.text_gradient is not None
        else:
            selected = style.text_gradient is None and _hex_to_rgba(hex_v) == style.text_color
        text_buttons.append(InlineKeyboardButton(mark(name, selected), callback_data=f"style:text:{hex_v}"))
    current_font = style.font_path or _font_path(FONT_CHOICES[0][1])
    font_buttons = [
        InlineKeyboardButton(
            mark(name, _font_path(filename) == current_font),
            callback_data=f"style:font:{filename}",
        )
        for name, filename in FONT_CHOICES
    ]
    outline_buttons = [
        InlineKeyboardButton(
            mark(name, _hex_to_rgba(hex_v) == style.outline_color),
            callback_data=f"style:outline:{hex_v or 'none'}",
        )
        for name, hex_v in OUTLINE_COLOR_CHOICES
    ]

    rows = [
        *_chunk(bg_buttons, 4),
        [InlineKeyboardButton("\U0001F3A8 Boshqa fon rangi (HEX)", callback_data="style:custompick:bg")],
        *_chunk(text_buttons, 3),
        [InlineKeyboardButton("\U0001F3A8 Boshqa matn rangi (HEX)", callback_data="style:custompick:text")],
        *_chunk(font_buttons, 2),
        *_chunk(outline_buttons, 3),
        [InlineKeyboardButton("\U0001F3A8 Boshqa chiziq rangi (HEX)", callback_data="style:custompick:outline")],
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
    parts = query.data.split(":", 2)
    kind = parts[1]
    value = parts[2] if len(parts) > 2 else None

    if kind == "close":
        await query.answer("Saqlandi ✅")
        await _safe_edit_message_text(query,
            "Stil saqlandi. Endi yangi matnli stikerlar shu uslubda chiqadi.",
            reply_markup=_back_to_menu_button(),
        )
        return

    if kind == "custompick":
        user_prefs.awaiting_custom_color = value  # "bg", "text" or "outline"
        target = {"bg": "fon", "text": "matn", "outline": "chiziq"}[value]
        await query.answer()
        await _safe_edit_message_text(query,
            f"\U0001F3A8 {target.capitalize()} rangi uchun HEX kod yuboring, masalan: #FF5733"
        )
        return

    if kind == "bg":
        user_prefs.style.background_color = None if value == "none" else _hex_to_rgba(value)
    elif kind == "text":
        if value == GRADIENT_TEXT_KEY:
            user_prefs.style.text_gradient = GREEN_GRADIENT
        else:
            user_prefs.style.text_gradient = None
            user_prefs.style.text_color = _hex_to_rgba(value)
    elif kind == "outline":
        user_prefs.style.outline_color = None if value == "none" else _hex_to_rgba(value)
    elif kind == "font":
        user_prefs.style.font_path = _font_path(value)

    warning = None
    if kind in ("text", "outline") and not user_prefs.style.text_gradient:
        if _colors_clash(user_prefs.style.text_color, user_prefs.style.outline_color):
            warning = "⚠️ Matn va chiziq rangi bir-biriga juda yaqin — matn ko'rinmasligi mumkin!"

    await query.answer(warning, show_alert=bool(warning))
    await _safe_edit_message_text(query, _style_summary(user_prefs.style), reply_markup=_style_keyboard(user_prefs.style))


# --------------------------------------------------------------------------
# Company logo
# --------------------------------------------------------------------------


def _outline_label(color: tuple[int, int, int, int] | None) -> str:
    for name, value in LOGO_OUTLINE_STATES:
        if value == color:
            return name
    return LOGO_OUTLINE_STATES[0][0]


def _next_outline_color(color: tuple[int, int, int, int] | None) -> tuple[int, int, int, int] | None:
    values = [value for _, value in LOGO_OUTLINE_STATES]
    next_index = (values.index(color) + 1) % len(values) if color in values else 1
    return values[next_index]


def _company_text(user_id: int, company_mode: bool, outline_color: tuple[int, int, int, int] | None) -> str:
    has_logo = logo_store.has_logo(user_id)
    logo_line = "Logotip: ✅ yuklangan\n" if has_logo else "Logotip: ❌ hali yuklanmagan\n"
    mode_line = "Rejim: \U0001F7E2 YONIQ\n" if company_mode else "Rejim: ⚪ O'CHIQ\n"
    outline_line = f"Logotip konturi: {_outline_label(outline_color)}"
    return (
        "\U0001F3E2 Kompaniya rejimi\n\n"
        + logo_line
        + mode_line
        + outline_line
        + "\n\nYoqilgan bo'lsa, logotipingiz yangi matnli va rasmli stikerlarning "
        "pastki o'ng qismiga kichik belgi (watermark) sifatida qo'yiladi. Logotipni "
        "PNG fayl (hujjat) sifatida yuborsangiz, shaffof fon saqlanib qoladi va "
        "kontur uning shakliga mos chiqadi."
    )


def _company_keyboard(
    has_logo: bool, company_mode: bool, outline_color: tuple[int, int, int, int] | None
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton("\U0001F4E4 Logotip yuklash/almashtirish", callback_data="company:setlogo")]]
    if has_logo:
        toggle_label = "⚪ Rejimni o'chirish" if company_mode else "\U0001F7E2 Rejimni yoqish"
        rows.append([InlineKeyboardButton(toggle_label, callback_data="company:toggle")])
        rows.append(
            [
                InlineKeyboardButton(
                    f"\U0001F58A Logotip konturi: {_outline_label(outline_color)}",
                    callback_data="company:outline",
                )
            ]
        )
        rows.append([InlineKeyboardButton("\U0001F5D1 Logotipni o'chirish", callback_data="company:delete")])
    rows.append([InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")])
    return InlineKeyboardMarkup(rows)


async def _render_company(user_id: int, send) -> None:
    user_prefs = prefs.get(user_id)
    has_logo = logo_store.has_logo(user_id)
    await send(
        _company_text(user_id, user_prefs.company_mode, user_prefs.logo_outline_color),
        reply_markup=_company_keyboard(has_logo, user_prefs.company_mode, user_prefs.logo_outline_color),
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
        await _safe_edit_message_text(query,
            "\U0001F4E4 Endi menga kompaniya logotipini yuboring.\n\n"
            "Eng yaxshi natija uchun uni \U0001F4CE **fayl (hujjat)** sifatida, PNG "
            "formatida yuboring - shunda shaffof fon saqlanib qoladi. Oddiy rasm "
            "qilib yuborsangiz ham bo'ladi, lekin Telegram uni siqib, fonini "
            "oq/qattiq qilib qo'yishi mumkin."
        )
        return
    if action == "toggle":
        if not logo_store.has_logo(user.id):
            await query.answer("Avval logotip yuklang.", show_alert=True)
            return
        user_prefs.company_mode = not user_prefs.company_mode
    elif action == "outline":
        if not logo_store.has_logo(user.id):
            await query.answer("Avval logotip yuklang.", show_alert=True)
            return
        user_prefs.logo_outline_color = _next_outline_color(user_prefs.logo_outline_color)
    elif action == "delete":
        logo_store.delete_logo(user.id)
        user_prefs.company_mode = False
        user_prefs.logo_outline_color = None

    await query.answer()
    has_logo = logo_store.has_logo(user.id)
    await _safe_edit_message_text(query,
        _company_text(user.id, user_prefs.company_mode, user_prefs.logo_outline_color),
        reply_markup=_company_keyboard(has_logo, user_prefs.company_mode, user_prefs.logo_outline_color),
    )


def _apply_company_overlay(user_id: int, image: Image.Image) -> Image.Image:
    user_prefs = prefs.get(user_id)
    if not user_prefs.company_mode:
        return image
    logo = logo_store.load_logo(user_id)
    if logo is None:
        return image
    if user_prefs.logo_outline_color:
        logo = add_outline(logo, color=user_prefs.logo_outline_color, width=LOGO_OUTLINE_WIDTH)
    return add_watermark(image, logo)


# --------------------------------------------------------------------------
# Resize any image to a preconfigured px size + DPI
# --------------------------------------------------------------------------

RESIZE_FIELD_NAMES = {"width": "kenglik (px)", "height": "balandlik (px)", "dpi": "DPI"}


def _resize_text(user_prefs) -> str:
    return (
        "\U0001F5BC Rasm o'lchamini o'zgartirish\n\n"
        f"Joriy sozlama: {user_prefs.resize_width}x{user_prefs.resize_height} px, "
        f"{user_prefs.resize_dpi} dpi\n\n"
        "Menga istalgan rasm(lar)ni yuboring - alohida rasm, fayl (hujjat) yoki bir "
        "nechtasini ketma-ket ham - men har birini shu o'lchamda, o'zgarmagan "
        "nisbatlarda (cho'zmasdan) qaytarib beraman.\n\n"
        "O'lchamni pastdagi tugmalar bilan o'zgartiring:"
    )


def _resize_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"resize:preset:{i}")]
        for i, (label, _w, _h, _dpi) in enumerate(RESIZE_PRESETS)
    ]
    rows.append(
        [
            InlineKeyboardButton("✏️ Kenglik (px)", callback_data="resize:field:width"),
            InlineKeyboardButton("✏️ Balandlik (px)", callback_data="resize:field:height"),
        ]
    )
    rows.append([InlineKeyboardButton("✏️ DPI", callback_data="resize:field:dpi")])
    rows.append([InlineKeyboardButton("\U0001F3E0 Bosh menyu", callback_data="menu:help")])
    return InlineKeyboardMarkup(rows)


async def resize_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_prefs = prefs.get(update.effective_user.id)
    user_prefs.resize_mode = True
    await update.message.reply_text(_resize_text(user_prefs), reply_markup=_resize_keyboard())


async def resize_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    user_prefs = prefs.get(user.id)
    parts = query.data.split(":")
    action = parts[1]

    if action == "preset":
        _label, width, height, dpi = RESIZE_PRESETS[int(parts[2])]
        user_prefs.resize_width = width
        user_prefs.resize_height = height
        if dpi is not None:
            user_prefs.resize_dpi = dpi
    elif action == "field":
        field = parts[2]
        user_prefs.awaiting_resize_field = field
        await query.answer()
        await _safe_edit_message_text(query,
            f"✏️ Yangi {RESIZE_FIELD_NAMES[field]} qiymatini raqam qilib yuboring "
            f"({MIN_DIMENSION}-{MAX_DIMENSION})."
        )
        return

    await query.answer()
    await _safe_edit_message_text(query, _resize_text(user_prefs), reply_markup=_resize_keyboard())


async def _resize_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, image_bytes: bytes) -> None:
    user_prefs = prefs.get(update.effective_user.id)
    width, height, dpi = user_prefs.resize_width, user_prefs.resize_height, user_prefs.resize_dpi

    try:
        image = resize_to_canvas(image_bytes, width, height)
        png_bytes = image_to_png_bytes_with_dpi(image, dpi)
    except Exception:
        logger.exception("Unexpected error while resizing image")
        await update.message.reply_text("Rasmni qayta ishlashda xatolik yuz berdi, qayta urinib ko'ring.")
        return

    document = update.message.document
    stem = Path(document.file_name).stem if document and document.file_name else "rasm"

    await update.message.reply_document(
        document=BytesIO(png_bytes),
        filename=f"{stem}.png",
    )


# --------------------------------------------------------------------------
# My packs (list / continue / rename / delete)
# --------------------------------------------------------------------------


def _format_icon(sticker_format: str) -> str:
    return "\U0001F3AC" if sticker_format == "video" else "\U0001F5BC"


def _packs_keyboard(packs: list[pack_registry.PackRecord]) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                f"{_format_icon(record.sticker_format)} {record.title} ({record.count})",
                callback_data=f"pack:open:{i}",
            )
        ]
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
        await _render_mypacks(user.id, partial(_safe_edit_message_text, query))
        return

    idx = int(parts[2])
    packs = pack_registry.list_packs(user.id)
    if idx >= len(packs):
        await query.answer("Bu to'plam topilmadi (ro'yxat yangilangan bo'lishi mumkin).", show_alert=True)
        return
    record = packs[idx]

    if action == "open":
        await query.answer()
        format_label = "video/GIF" if record.sticker_format == "video" else "rasm/matn"
        await _safe_edit_message_text(query,
            f"{_format_icon(record.sticker_format)} {record.title}\n"
            f"{record.count} ta stiker ({format_label})\n{pack_link(record.name)}",
            reply_markup=_pack_menu_keyboard(idx),
        )
    elif action == "continue":
        session = sessions.start(user.id, set_name=record.name, title=record.title)
        session.count = record.count
        session.sticker_format = record.sticker_format
        prefs.get(user.id).resize_mode = False
        await query.answer()
        next_hint = "GIF/animatsiya" if record.sticker_format == "video" else "rasm yoki matn"
        await _safe_edit_message_text(query,
            f"✅ '{record.title}' to'plamiga davom etyapsiz. Menga {next_hint} yuboring, "
            "tugatgach /done bosing."
        )
    elif action == "rename":
        prefs.get(user.id).awaiting_rename_for = record.name
        await query.answer()
        await _safe_edit_message_text(query, f"✏️ '{record.title}' uchun yangi nomni matn qilib yuboring.")
    elif action == "delete":
        await query.answer()
        await _safe_edit_message_text(query,
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
            await _safe_edit_message_text(query, f"Xatolik: {exc.message}")
            return
        pack_registry.remove_pack(user.id, record.name)
        active = sessions.get(user.id)
        if active and active.set_name == record.name:
            sessions.clear(user.id)
        await query.answer("O'chirildi")
        await _safe_edit_message_text(query,
            f"\U0001F5D1 '{record.title}' o'chirildi.", reply_markup=_back_to_menu_button()
        )


# --------------------------------------------------------------------------
# Photo / file -> sticker
# --------------------------------------------------------------------------


async def _download_image_bytes(update: Update) -> bytes:
    message = update.message
    telegram_file = message.photo[-1] if message.photo else message.document
    tg_file = await telegram_file.get_file()
    return bytes(await tg_file.download_as_bytearray())


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_incoming_image(update, context)


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _handle_incoming_image(update, context)


async def _handle_incoming_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_prefs = prefs.get(user.id)
    image_bytes = await _download_image_bytes(update)

    if user_prefs.awaiting_logo:
        logo_store.save_logo(user.id, Image.open(BytesIO(image_bytes)))
        user_prefs.awaiting_logo = False
        user_prefs.company_mode = True
        await update.message.reply_text(
            "✅ Logotip saqlandi va kompaniya rejimi yoqildi. Endi yuboradigan barcha "
            "stikerlar shu logotip foniga qo'yiladi. /company orqali o'chirish, "
            "almashtirish yoki kontur qo'shish mumkin."
        )
        return

    if user_prefs.resize_mode:
        await _resize_and_send(update, context, image_bytes)
        return

    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text(
            "Avval yangi to'plam boshlang: /newpack nomi yoki /start dagi \U0001F195 tugmasi orqali."
        )
        return
    if session.sticker_format == "video":
        await update.message.reply_text(
            "Bu to'plam video/GIF stikerlar uchun boshlangan — Telegram bitta to'plamda "
            "statik va video stikerlarni aralashtirishga ruxsat bermaydi. Rasm/matn "
            "stikerlari uchun /newpack bilan alohida yangi to'plam boshlang."
        )
        return
    if session.count >= MAX_STICKERS_PER_PACK:
        await update.message.reply_text(
            f"Bu to'plamda allaqachon {MAX_STICKERS_PER_PACK} ta stiker bor (Telegram "
            "chegarasi). /done bilan yakunlang va yangi to'plam boshlang."
        )
        return

    emoji = extract_emoji(update.message.caption) or DEFAULT_EMOJI

    try:
        image = prepare_sticker_image(image_bytes)
        image = _apply_company_overlay(user.id, image)
        png_bytes = image_to_png_bytes(image)
        await add_or_create(
            context.bot,
            user_id=user.id,
            set_name=session.set_name,
            title=session.title,
            media_bytes=png_bytes,
            emoji=emoji,
            sticker_format="static",
        )
    except (BadRequest, TelegramError) as exc:
        logger.warning("Sticker add failed: %s", exc)
        await update.message.reply_text(f"Xatolik yuz berdi: {exc.message}")
        return
    except Exception:
        logger.exception("Unexpected error while adding sticker")
        await update.message.reply_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    session.sticker_format = "static"
    sessions.bump(user.id)
    pack_registry.upsert_pack(user.id, session.set_name, session.title, session.count, sticker_format="static")
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )


# --------------------------------------------------------------------------
# GIF / animation -> video sticker
# --------------------------------------------------------------------------


async def gif_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    user_prefs = prefs.get(user.id)

    if user_prefs.awaiting_logo:
        await update.message.reply_text(
            "Kompaniya logotipi statik rasm (PNG/JPG) bo'lishi kerak, GIF/animatsiya emas. "
            "Iltimos, logotipni oddiy rasm yoki fayl qilib qayta yuboring."
        )
        return

    session = sessions.get(user.id)
    if session is None:
        await update.message.reply_text(
            "Avval yangi to'plam boshlang: /newpack nomi yoki /start dagi \U0001F195 tugmasi orqali."
        )
        return
    if session.sticker_format == "static":
        await update.message.reply_text(
            "Bu to'plam rasm/matn stikerlar uchun boshlangan — Telegram bitta to'plamda "
            "statik va video stikerlarni aralashtirishga ruxsat bermaydi. GIF stikerlar "
            "uchun /newpack bilan alohida yangi to'plam boshlang."
        )
        return
    if session.count >= MAX_STICKERS_PER_PACK:
        await update.message.reply_text(
            f"Bu to'plamda allaqachon {MAX_STICKERS_PER_PACK} ta stiker bor (Telegram "
            "chegarasi). /done bilan yakunlang va yangi to'plam boshlang."
        )
        return

    media = update.message.animation or update.message.document
    tg_file = await media.get_file()
    source_bytes = bytes(await tg_file.download_as_bytearray())

    emoji = extract_emoji(update.message.caption) or DEFAULT_EMOJI
    status_message = await update.message.reply_text(
        "\U0001F504 GIF video-stikerga o'girilmoqda, biroz kuting..."
    )

    try:
        webm_bytes = await asyncio.to_thread(convert_to_video_sticker, source_bytes)
    except Exception:
        logger.exception("Unexpected error while converting GIF to a video sticker")
        await status_message.edit_text(
            "GIFni video-stikerga o'girishda xatolik yuz berdi (juda uzun yoki formatida "
            "muammo bo'lishi mumkin). Boshqa GIF bilan urinib ko'ring."
        )
        return

    try:
        await add_or_create(
            context.bot,
            user_id=user.id,
            set_name=session.set_name,
            title=session.title,
            media_bytes=webm_bytes,
            emoji=emoji,
            sticker_format="video",
        )
    except (BadRequest, TelegramError) as exc:
        logger.warning("Video sticker add failed: %s", exc)
        await status_message.edit_text(f"Xatolik yuz berdi: {exc.message}")
        return
    except Exception:
        logger.exception("Unexpected error while adding video sticker")
        await status_message.edit_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    session.sticker_format = "video"
    sessions.bump(user.id)
    pack_registry.upsert_pack(user.id, session.set_name, session.title, session.count, sticker_format="video")
    await status_message.edit_text(
        f"➕ Video-stiker qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
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
            "Endi menga rasm, matn yoki GIF/animatsiya yuboring - har biri to'plamga "
            "stiker sifatida qo'shiladi (rasm/matn va GIF stikerlarini bitta to'plamda "
            "aralashtirib bo'lmaydi). Tugatgach /done ni bosing."
        )
        return

    if user_prefs.awaiting_resize_field:
        field = user_prefs.awaiting_resize_field
        user_prefs.awaiting_resize_field = None
        try:
            value = int(text)
        except ValueError:
            await update.message.reply_text("Bu butun son emas. Masalan: 1080 kabi yuboring.")
            return
        if not (MIN_DIMENSION <= value <= MAX_DIMENSION):
            await update.message.reply_text(f"{MIN_DIMENSION} dan {MAX_DIMENSION} gacha qiymat kiriting.")
            return
        setattr(user_prefs, f"resize_{field}", value)
        await update.message.reply_text(_resize_text(user_prefs), reply_markup=_resize_keyboard())
        return

    if user_prefs.awaiting_custom_color:
        target = user_prefs.awaiting_custom_color  # "bg", "text" or "outline"
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
        elif target == "outline":
            user_prefs.style.outline_color = color
        else:
            user_prefs.style.text_gradient = None
            user_prefs.style.text_color = color

        summary = _style_summary(user_prefs.style)
        if (
            target in ("text", "outline")
            and not user_prefs.style.text_gradient
            and _colors_clash(user_prefs.style.text_color, user_prefs.style.outline_color)
        ):
            summary = "⚠️ Matn va chiziq rangi bir-biriga juda yaqin — matn ko'rinmasligi mumkin!\n\n" + summary
        await update.message.reply_text(summary, reply_markup=_style_keyboard(user_prefs.style))
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

    if user_prefs.resize_mode:
        await update.message.reply_text(
            "\U0001F5BC Rasm o'lchamini o'zgartirish rejimidasiz - menga rasm yoki fayl yuboring."
        )
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
    if session.sticker_format == "video":
        await update.message.reply_text(
            "Bu to'plam video/GIF stikerlar uchun boshlangan — Telegram bitta to'plamda "
            "statik va video stikerlarni aralashtirishga ruxsat bermaydi. Matnli stikerlar "
            "uchun /newpack bilan alohida yangi to'plam boshlang."
        )
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
        image = _apply_company_overlay(user.id, image)
        png_bytes = image_to_png_bytes(image)
        await add_or_create(
            context.bot,
            user_id=user.id,
            set_name=session.set_name,
            title=session.title,
            media_bytes=png_bytes,
            emoji=emoji,
            sticker_format="static",
        )
    except (BadRequest, TelegramError) as exc:
        logger.warning("Sticker add failed: %s", exc)
        await update.message.reply_text(f"Xatolik yuz berdi: {exc.message}")
        return
    except Exception:
        logger.exception("Unexpected error while adding text sticker")
        await update.message.reply_text("Kutilmagan xatolik yuz berdi, qayta urinib ko'ring.")
        return

    session.sticker_format = "static"
    sessions.bump(user.id)
    pack_registry.upsert_pack(user.id, session.set_name, session.title, session.count, sticker_format="static")
    await update.message.reply_text(
        f"➕ Qo'shildi ({session.count}/{MAX_STICKERS_PER_PACK}). Davom eting yoki /done bosing."
    )
