"""Privacy-safe logging and download reliability tests (offline)."""

import asyncio
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from yt_dlp.utils import DownloadError

import bot
from pinterest_bot import downloader, handlers


def make_message():
    return SimpleNamespace(reply_video=AsyncMock(), reply_document=AsyncMock())


def test_log_formatter_redacts_bot_token():
    formatter = bot.TokenRedactingFormatter("secret-token-123")
    record = logging.LogRecord(
        "httpx", logging.ERROR, "test.py", 1,
        "HTTP request to /botsecret-token-123/getUpdates", (), None,
    )
    output = formatter.format(record)
    assert "secret-token-123" not in output
    assert "[REDACTED]" in output


def test_download_options_are_bounded_and_quiet(monkeypatch, tmp_path):
    seen = {}

    class FakeYoutubeDL:
        def __init__(self, options):
            seen.update(options)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url, download=True):
            (tmp_path / "123.mp4").write_bytes(b"video")

    monkeypatch.setattr(downloader.shutil, "which", lambda name: name)
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    downloader.download_video("https://pin.it/test", tmp_path)

    assert seen["socket_timeout"] == 20
    assert seen["retries"] == 2
    assert seen["fragment_retries"] == 2
    assert seen["no_warnings"] is True
    assert isinstance(seen["logger"], downloader.QuietYtDlpLogger)


def test_no_video_yields_specific_exception(monkeypatch, tmp_path):
    class FakeYoutubeDL:
        def __init__(self, options):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def extract_info(self, url, download=True):
            return None

    monkeypatch.setattr(downloader.shutil, "which", lambda name: name)
    monkeypatch.setattr(downloader.yt_dlp, "YoutubeDL", FakeYoutubeDL)
    with pytest.raises(downloader.NoVideoError):
        downloader.download_video("https://pin.it/test", tmp_path)


def test_downloader_error_does_not_leak_url_in_logs(monkeypatch, caplog):
    secret_url = "https://pin.it/test?private_invite=SECRET"

    async def fake_to_thread(*args):
        raise DownloadError(f"Download failed for {secret_url}")

    monkeypatch.setattr(handlers.asyncio, "to_thread", fake_to_thread)
    status = SimpleNamespace(edit_text=AsyncMock())
    with caplog.at_level(logging.INFO, logger="pinterest_bot.handlers"):
        asyncio.run(handlers.process_video(make_message(), status, secret_url))

    assert "video_request_failed reason=download" in caplog.text
    assert "SECRET" not in caplog.text
    assert "pin.it" not in caplog.text
    assert "Couldn't download" in status.edit_text.await_args.args[0]


def test_ffmpeg_error_gets_separate_user_message(monkeypatch, caplog):
    async def fake_to_thread(*args):
        raise downloader.MissingFFmpegError("test")

    monkeypatch.setattr(handlers.asyncio, "to_thread", fake_to_thread)
    status = SimpleNamespace(edit_text=AsyncMock())
    with caplog.at_level(logging.INFO, logger="pinterest_bot.handlers"):
        asyncio.run(handlers.process_video(make_message(), status, "https://pin.it/test"))

    assert "ffmpeg_unavailable" in caplog.text
    assert "temporarily" in status.edit_text.await_args.args[0]


def test_success_logs_duration_and_size_not_url(monkeypatch, caplog):
    async def fake_to_thread(fn, url, folder: Path):
        path = folder / "abc.mp4"
        path.write_bytes(b"12345")
        return path

    monkeypatch.setattr(handlers.asyncio, "to_thread", fake_to_thread)
    status = SimpleNamespace(edit_text=AsyncMock())
    with caplog.at_level(logging.INFO, logger="pinterest_bot.handlers"):
        asyncio.run(handlers.process_video(make_message(), status, "https://pin.it/SECRET"))

    assert "video_request_succeeded" in caplog.text
    assert "size_bytes=5" in caplog.text
    assert "elapsed_seconds=" in caplog.text
    assert "SECRET" not in caplog.text


def test_unhandled_error_logs_only_type(caplog):
    context = SimpleNamespace(error=RuntimeError("private-url-SECRET"))
    with caplog.at_level(logging.INFO, logger="pinterest_bot.handlers"):
        asyncio.run(handlers.on_application_error(None, context))

    assert "error_type=RuntimeError" in caplog.text
    assert "SECRET" not in caplog.text
