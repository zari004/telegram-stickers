#!/usr/bin/env python3
"""Create (or extend) a Telegram sticker pack from a folder of images.

No bot conversation needed - point this at a folder of pictures and it
uploads them all as one sticker pack in a single run.

Example:
    python scripts/upload_pack.py \\
        --user-id 123456789 \\
        --name mypack \\
        --title "Mening to'plamim" \\
        --images-dir ./images \\
        --emojis emojis.json

``emojis.json`` (optional) maps file name -> emoji, e.g.:
    {"cat.png": "\U0001F431", "dog.png": "\U0001F436"}
Any image without an entry falls back to --default-emoji.

The target Telegram user (--user-id) must have started a chat with the bot
at least once, and BOT_TOKEN must be set (see .env.example).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telegram import Bot
from telegram.error import TelegramError

from stickerpack.config import require_bot_token
from stickerpack.image_utils import prepare_sticker_png_bytes
from stickerpack.sticker_api import DEFAULT_EMOJI, add_or_create, build_set_name, pack_link

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user-id", type=int, required=True, help="Sticker to'plami egasi bo'lgan Telegram user_id")
    parser.add_argument("--name", required=True, help="To'plam uchun qisqa slug (masalan: mypack)")
    parser.add_argument("--title", required=True, help="To'plamning ko'rinadigan nomi")
    parser.add_argument("--images-dir", type=Path, required=True, help="Rasmlar joylashgan papka")
    parser.add_argument("--emojis", type=Path, default=None, help="fayl_nomi -> emoji xaritasi (JSON)")
    parser.add_argument("--default-emoji", default=DEFAULT_EMOJI, help="Xaritada yo'q rasmlar uchun emoji")
    return parser.parse_args()


def load_emoji_map(path: Path | None) -> dict[str, str]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def collect_images(images_dir: Path) -> list[Path]:
    if not images_dir.is_dir():
        raise SystemExit(f"Papka topilmadi: {images_dir}")
    files = sorted(
        p for p in images_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES
    )
    if not files:
        raise SystemExit(f"'{images_dir}' papkasida rasm topilmadi ({', '.join(sorted(IMAGE_SUFFIXES))})")
    return files


async def run(args: argparse.Namespace) -> None:
    emoji_map = load_emoji_map(args.emojis)
    images = collect_images(args.images_dir)

    bot = Bot(token=require_bot_token())
    async with bot:
        bot_username = (await bot.get_me()).username
        set_name = build_set_name(args.user_id, args.name, bot_username)

        print(f"To'plam: {set_name}  ({len(images)} ta rasm)")
        for index, image_path in enumerate(images, start=1):
            emoji = emoji_map.get(image_path.name, args.default_emoji)
            try:
                png_bytes = prepare_sticker_png_bytes(image_path)
                created = await add_or_create(
                    bot,
                    user_id=args.user_id,
                    set_name=set_name,
                    title=args.title,
                    png_bytes=png_bytes,
                    emoji=emoji,
                )
            except TelegramError as exc:
                print(f"  [{index}/{len(images)}] {image_path.name}: XATOLIK - {exc.message}")
                continue

            action = "yaratildi" if created else "qo'shildi"
            print(f"  [{index}/{len(images)}] {image_path.name} ({emoji}) - {action}")

        print(f"\nTayyor: {pack_link(set_name)}")


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
