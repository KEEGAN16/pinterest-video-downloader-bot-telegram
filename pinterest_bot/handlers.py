"""Telegram commands and safe, privacy-conscious request logging."""

import asyncio
import logging
import tempfile
import time
from pathlib import Path

from telegram import BotCommand, Message, Update
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes
from yt_dlp.utils import DownloadError

from .config import APP_VERSION, GITHUB_URL
from .downloader import (
    MissingFFmpegError,
    NoVideoError,
    VideoTooLargeError,
    download_video,
    get_pinterest_url,
)
from .rate_limit import DownloadLimiter

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "👋 Welcome to Pinterest Video Downloader!\n\n"
        "Send me a public Pinterest video link and I'll try to download it with sound.\n"
        "Use /help for instructions."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "📌 How to use the bot:\n\n"
        "1. Open a public Pinterest video.\n"
        "2. Copy its pinterest.com or pin.it link.\n"
        "3. Send the link here.\n"
        "4. Wait for the video to appear.\n\n"
        "Supported: public Pinterest video pins.\n"
        "Limit: approximately 49 MB per video.\n"
        "Some pins may be unavailable or unsupported.\n"
        "Please wait 30 seconds after each download before sending another."
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        f"🤖 Pinterest Video Downloader v{APP_VERSION}\n"
        "Built with Python, python-telegram-bot, yt-dlp and FFmpeg.\n\n"
        f"Source code: {GITHUB_URL}\n\n"
        "Only download videos you have permission to save."
    )


async def set_commands(app: Application) -> None:
    """Show available commands in Telegram's command menu."""
    await app.bot.set_my_commands(
        [
            BotCommand("start", "Start the bot"),
            BotCommand("help", "How to download a video"),
            BotCommand("about", "Information about this bot"),
        ]
    )


async def on_application_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log only the exception class; messages can contain private URLs/tokens."""
    error = context.error
    logger.error("unhandled_update_error error_type=%s", type(error).__name__)


async def edit_status(status_message: Message, text: str) -> None:
    """Don't lose the original result if a status edit fails."""
    try:
        await status_message.edit_text(text)
    except TelegramError:
        logger.warning("status_edit_failed")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    url = get_pinterest_url(message.text or "")
    if not url:
        await message.reply_text("❌ Please send a valid Pinterest video link. Try /help.")
        return

    user = update.effective_user
    if user is None:
        return

    # No await between checking and reserving: one process, one event-loop limiter.
    limiter: DownloadLimiter = context.application.bot_data["download_limiter"]
    decision = limiter.try_start(user.id)
    if not decision.allowed:
        await message.reply_text(decision.message)
        return

    try:
        status = await message.reply_text("⏳ Downloading your video...")
        await process_video(message, status, url)
    finally:
        # Always release the slot even if Telegram raises or the handler is cancelled.
        limiter.finish(user.id)


async def process_video(message: Message, status: Message, url: str) -> None:
    started = time.monotonic()
    logger.info("video_request_started")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = await asyncio.to_thread(download_video, url, Path(temp_dir))
            size_bytes = video_path.stat().st_size
            await edit_status(status, "📤 Video downloaded! Uploading to Telegram...")

            with video_path.open("rb") as video_file:
                if video_path.suffix.lower() == ".mp4":
                    await message.reply_video(video=video_file, write_timeout=120)
                else:
                    await message.reply_document(document=video_file, write_timeout=120)

        logger.info(
            "video_request_succeeded elapsed_seconds=%.2f size_bytes=%d",
            time.monotonic() - started,
            size_bytes,
        )
        await edit_status(status, "✅ Done! Your video is ready.")

    except VideoTooLargeError:
        logger.warning("video_request_failed reason=too_large elapsed_seconds=%.2f", time.monotonic() - started)
        await edit_status(status, "❌ This video is too large (limit: 49 MB).")
    except MissingFFmpegError:
        logger.error("video_request_failed reason=ffmpeg_unavailable elapsed_seconds=%.2f", time.monotonic() - started)
        await edit_status(status, "❌ The bot is temporarily unable to process videos.")
    except (DownloadError, NoVideoError) as error:
        logger.warning("video_request_failed reason=download error_type=%s elapsed_seconds=%.2f", type(error).__name__, time.monotonic() - started)
        await edit_status(
            status,
            "❌ Couldn't download this pin. Check that it contains a public video, "
            "or try another link.",
        )
    except TelegramError as error:
        logger.warning("video_request_failed reason=telegram error_type=%s elapsed_seconds=%.2f", type(error).__name__, time.monotonic() - started)
        await edit_status(status, "❌ The video was downloaded, but Telegram could not receive it.")
    except Exception as error:
        logger.error("video_request_failed reason=unexpected error_type=%s elapsed_seconds=%.2f", type(error).__name__, time.monotonic() - started)
        await edit_status(status, "❌ Something went wrong. Please try again later.")
