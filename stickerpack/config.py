import os
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"

DEFAULT_FONT_BOLD = FONTS_DIR / "DejaVuSans-Bold.ttf"
DEFAULT_FONT_REGULAR = FONTS_DIR / "DejaVuSans.ttf"

load_dotenv(ROOT_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


def require_bot_token() -> str:
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN topilmadi. .env faylida yoki muhit o'zgaruvchisida "
            "BOT_TOKEN ni belgilang (uni @BotFather dan oling)."
        )
    return BOT_TOKEN
