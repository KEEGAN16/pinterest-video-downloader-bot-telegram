import asyncio
import logging
import os
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.error import TelegramError
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from yt_dlp.utils import DownloadError


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 49 * 1024 * 1024  # Below the 50 MB Telegram upload limit
GITHUB_URL = "https://github.com/KEEGAN16/pinterest-video-downloader-bot-telegram"


class VideoTooLargeError(Exception):
    """The completed video exceeds the configured Telegram upload limit."""


def get_pinterest_url(text: str) -> str | None:
    """Return the first Pinterest URL in a message, if any."""
    urls = re.findall(r"https?://[^\s<>]+", text)

    for url in urls:
        url = url.rstrip(".,;!?)")
        host = (urlparse(url).hostname or "").lower()
        if (
            host in ("pin.it", "www.pin.it")
            or host == "pinterest.com"
            or host.endswith(".pinterest.com")
        ):
            return url

    return None


def download_video(url: str, folder: Path) -> Path:
    """Download a Pinterest video and merge audio/video via FFmpeg."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe must be installed and available on PATH")

    options = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 20,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    videos = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")
    ]
    if not videos:
        raise RuntimeError("No video file was downloaded")

    video = max(videos, key=lambda path: path.stat().st_size)
    if video.stat().st_size > MAX_FILE_SIZE:
        raise VideoTooLargeError()
    return video


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
        "Some pins may be unavailable or unsupported."
    )


async def about_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(
        "🤖 Pinterest Video Downloader v0.2.0\n"
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


async def edit_status(status_message, text: str) -> None:
    """Do not lose the original result if a status edit fails."""
    try:
        await status_message.edit_text(text)
    except TelegramError:
        logger.warning("Could not edit status message", exc_info=True)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.effective_message
    if message is None:
        return

    url = get_pinterest_url(message.text or "")
    if not url:
        await message.reply_text("❌ Please send a valid Pinterest video link. Try /help.")
        return

    status = await message.reply_text("⏳ Downloading your video...")

    try:
        # A separate folder for every request avoids filename collisions.
        with tempfile.TemporaryDirectory() as temp_dir:
            video_path = await asyncio.to_thread(download_video, url, Path(temp_dir))

            await edit_status(status, "📤 Video downloaded! Uploading to Telegram...")

            with video_path.open("rb") as video_file:
                if video_path.suffix.lower() == ".mp4":
                    await message.reply_video(video=video_file, write_timeout=120)
                else:
                    await message.reply_document(document=video_file, write_timeout=120)

        await edit_status(status, "✅ Done! Your video is ready.")

    except VideoTooLargeError:
        await edit_status(status, "❌ This video is too large (limit: 49 MB).")
    except DownloadError:
        logger.exception("Pinterest video download failed")
        await edit_status(
            status,
            "❌ Couldn't download this pin. Check that it contains a public video, "
            "or try another link.",
        )
    except TelegramError:
        logger.exception("Telegram upload failed")
        await edit_status(status, "❌ The video was downloaded, but Telegram could not receive it.")
    except Exception:
        logger.exception("Unexpected error while processing a video")
        await edit_status(status, "❌ Something went wrong. Please try again later.")


def main() -> None:
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing from .env")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(set_commands)
        .concurrent_updates(2)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("about", about_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
