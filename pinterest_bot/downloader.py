"""Pinterest URL validation and yt-dlp / FFmpeg downloads."""

import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yt_dlp

from .config import MAX_FILE_SIZE


class VideoTooLargeError(Exception):
    """The completed video exceeds the configured Telegram upload limit."""


class MissingFFmpegError(RuntimeError):
    """FFmpeg or FFprobe is unavailable on the current machine."""


class NoVideoError(RuntimeError):
    """No usable video file was produced by the downloader."""


class QuietYtDlpLogger:
    """Avoid printing video URLs, request parameters or credentials to logs."""

    def debug(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str) -> None:
        pass


def get_pinterest_url(text: str) -> str | None:
    """Return the first recognized Pinterest URL in a message, if any."""
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
    """Download Pinterest video and merge audio/video via FFmpeg."""
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise MissingFFmpegError("FFmpeg and FFprobe are required")

    options = {
        "outtmpl": str(folder / "%(id)s.%(ext)s"),
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "logger": QuietYtDlpLogger(),
        "max_filesize": MAX_FILE_SIZE,
        "socket_timeout": 20,  # Inactivity timeout per connection, not a total download deadline.
        "retries": 2,
        "fragment_retries": 2,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    videos = [
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in (".mp4", ".webm", ".mkv", ".mov")
    ]
    if not videos:
        raise NoVideoError("No video was downloaded")

    video = max(videos, key=lambda path: path.stat().st_size)
    if video.stat().st_size > MAX_FILE_SIZE:
        raise VideoTooLargeError()
    return video
