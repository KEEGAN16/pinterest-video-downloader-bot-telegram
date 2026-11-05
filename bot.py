"""Run the Pinterest Telegram bot locally or in Docker."""

import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from pinterest_bot.handlers import (
    about_command,
    handle_message,
    help_command,
    set_commands,
    start,
)
from pinterest_bot.rate_limit import DownloadLimiter

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
    # httpx logs can include the bot token in Telegram API request URLs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def create_application(token: str) -> Application:
    """Wire handlers and the in-memory download limiter together."""
    app = (
        Application.builder()
        .token(token)
        .post_init(set_commands)
        .concurrent_updates(8)
        .build()
    )

    app.bot_data["download_limiter"] = DownloadLimiter(
        max_concurrent=2,
        cooldown_seconds=30,
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    return app


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing from .env")

    configure_logging()
    app = create_application(token)
    logger.info("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
