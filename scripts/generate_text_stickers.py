#!/usr/bin/env python3
"""Generate sticker-ready PNG images (512x512) from lines of text.

Pure image generator - no Telegram bot or token needed. Feed the output
folder into scripts/upload_pack.py (or the bot's /newpack flow) afterwards.

Examples:
    python scripts/generate_text_stickers.py --text "Salom!" --text "Xayr!"
    python scripts/generate_text_stickers.py --texts-file phrases.txt \\
        --bg "#FFD600" --color "#1E1E1E" --output-dir out
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stickerpack.image_utils import image_to_png_bytes
from stickerpack.text_sticker import TextStickerStyle, render_text_sticker

HEX_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def parse_color(value: str | None) -> tuple[int, int, int, int] | None:
    if not value:
        return None
    match = HEX_RE.match(value)
    if not match:
        raise argparse.ArgumentTypeError(f"Noto'g'ri rang: {value} (masalan #FFD600 bo'lishi kerak)")
    hex_value = match.group(1)
    r, g, b = (int(hex_value[i : i + 2], 16) for i in (0, 2, 4))
    return (r, g, b, 255)


def slugify(text: str, fallback: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip()).strip("_").lower()
    return slug[:40] or fallback


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--text", action="append", default=[], help="Bitta stiker matni (bir necha marta ishlatish mumkin)")
    parser.add_argument("--texts-file", type=Path, help="Har bir qatori alohida stiker bo'ladigan matn fayli")
    parser.add_argument("--output-dir", type=Path, default=Path("stickers_out"), help="Chiqish papkasi")
    parser.add_argument("--bg", type=parse_color, default=None, help="Fon rangi hex (masalan #FFD600); berilmasa shaffof")
    parser.add_argument("--color", type=parse_color, default="#1E1E1E", help="Matn rangi hex")
    parser.add_argument("--outline", type=parse_color, default="#FFFFFF", help="Matn atrofidagi chiziq rangi hex")
    parser.add_argument("--no-outline", action="store_true", help="Matn atrofida chiziq chizmaslik")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    texts = list(args.text)
    if args.texts_file:
        texts.extend(
            line.strip() for line in args.texts_file.read_text(encoding="utf-8").splitlines() if line.strip()
        )
    if not texts:
        raise SystemExit("Kamida bitta matn bering: --text \"...\" yoki --texts-file fayl.txt")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    style_kwargs = dict(
        background_color=args.bg,
        text_color=parse_color(args.color) if isinstance(args.color, str) else args.color,
        outline_color=None if args.no_outline else (
            parse_color(args.outline) if isinstance(args.outline, str) else args.outline
        ),
    )

    used_names: set[str] = set()
    for index, text in enumerate(texts, start=1):
        style = TextStickerStyle(**style_kwargs)
        image = render_text_sticker(text, style)
        png_bytes = image_to_png_bytes(image)

        base_name = slugify(text, f"sticker_{index}")
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}_{suffix}"
            suffix += 1
        used_names.add(name)

        out_path = args.output_dir / f"{index:03d}_{name}.png"
        out_path.write_bytes(png_bytes)
        print(f"[{index}/{len(texts)}] {text!r} -> {out_path}")

    print(f"\nTayyor: {len(texts)} ta rasm {args.output_dir}/ papkasida.")


if __name__ == "__main__":
    main()
