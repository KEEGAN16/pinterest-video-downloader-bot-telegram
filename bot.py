
import asyncio
import logging
import os
import re
import tempfile
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)


load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 49 * 1024 * 1024


def get_pinterest_url(text: str) -> str | None:
    # Find URLs in the user's message
    urls = re.findall(r"https?://[^\s<>]+", text)

    for url in urls:
        url = url.rstrip(".,;!?)")
        host = (urlparse(url).hostname or "").lower()

        # Accept Pinterest and its short links
        if (
            host in ("pin.it", "www.pin.it")
            or host == "pinterest.com"
            or host.endswith(".pinterest.com")
        ):
            return url

    return None



def download_video(url: str, folder: Path) -> Path:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required.")
    
    options = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "max_filesize": MAX_FILE_SIZE,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    videos = [
        file
        for file in folder.iterdir()
        if file.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")
    ]

    if not videos:
        raise RuntimeError("No video file was downloaded.")

    return max(videos, key=lambda file: file.stat().st_size)



async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "Hi! Send me a Pinterest video link!"
    )


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    url = get_pinterest_url(update.message.text or "")

    if not url:
        await update.message.reply_text(
            "Please send a valid Pinterest link."
        )
        return

    await update.message.reply_text(
        "Downloading your video..."
    )

    try:
        # Each request gets its own temporary folder
        with tempfile.TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir)

            # Run the blocking download in another thread
            video_path = await asyncio.to_thread(
                download_video, url, folder
            )

            if video_path.stat().st_size > MAX_FILE_SIZE:
                await update.message.reply_text(
                    "The video is too large to send."
                )
                return

            with video_path.open("rb") as video:
                if video_path.suffix.lower() == ".mp4":
                    await update.message.reply_video(
                        video=video,
                        write_timeout=120,
                    )
                else:
                    await update.message.reply_document(
                        document=video,
                        write_timeout=120,
                    )

            # Temporary files are deleted automatically

    except Exception:
        logger.exception("Video download or upload failed")

        await update.message.reply_text(
            "Sorry, I couldn't download this video. "
            "Please try another public Pinterest link."
        )


def main():
    if not TOKEN:
        raise RuntimeError("BOT_TOKEN is missing from .env")

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
