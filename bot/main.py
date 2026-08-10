"""Entry point for the interactive sticker-pack Telegram bot."""
from __future__ import annotations

import logging

from telegram.ext import Application, CommandHandler, MessageHandler, filters

from stickerpack.config import require_bot_token

from . import handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)


def build_application() -> Application:
    token = require_bot_token()
    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("newpack", handlers.newpack_command))
    application.add_handler(CommandHandler("addtext", handlers.addtext_command))
    application.add_handler(CommandHandler("done", handlers.done_command))
    application.add_handler(CommandHandler("cancel", handlers.cancel_command))
    application.add_handler(MessageHandler(filters.PHOTO, handlers.photo_handler))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.text_handler)
    )

    return application


def main() -> None:
    application = build_application()
    application.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
