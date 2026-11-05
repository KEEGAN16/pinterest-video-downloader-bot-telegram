"""Run the Pinterest Telegram bot locally or in Docker."""

import logging
import os

from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from pinterest_bot.handlers import (
    about_command,
    handle_message,
    help_command,
    on_application_error,
    set_commands,
    start,
)
from pinterest_bot.rate_limit import DownloadLimiter

logger = logging.getLogger(__name__)


class TokenRedactingFormatter(logging.Formatter):
    """Hide the bot token if a library accidentally includes it in a log."""

    def __init__(self, token: str) -> None:
        super().__init__("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
        self._token = token

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return formatted.replace(self._token, "[REDACTED]") if self._token else formatted


def configure_logging(token: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(TokenRedactingFormatter(token))
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)

    # Only our own event logs are emitted at INFO level.
    logging.getLogger(__name__).setLevel(logging.INFO)
    logging.getLogger("pinterest_bot").setLevel(logging.INFO)

    # Suppress third-party request logs, which may include the bot token in URLs.
    logging.getLogger("httpx").disabled = True
    logging.getLogger("httpcore").disabled = True


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
    app.add_error_handler(on_application_error)
    return app


def main() -> None:
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is missing from .env")

    configure_logging(token)
    app = create_application(token)
    logger.info("bot_started")
    app.run_polling()


if __name__ == "__main__":
    main()
