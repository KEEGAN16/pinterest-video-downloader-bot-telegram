"""Offline unit tests for Pinterest downloading (no Telegram calls)."""

from pathlib import Path

import pytest

from pinterest_bot import downloader as bot


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("https://pin.it/4nx3w4rnb", "https://pin.it/4nx3w4rnb"),
        ("Watch https://www.pin.it/abc123!", "https://www.pin.it/abc123"),
        (
            "Pinterest: https://www.pinterest.com/pin/123456/",
            "https://www.pinterest.com/pin/123456/",
        ),
        (
            "https://pinterest.com/pin/123456/?foo=bar",
            "https://pinterest.com/pin/123456/?foo=bar",
        ),
    ],
)
def test_valid_pinterest_urls(message, expected):
    assert bot.get_pinterest_url(message) == expected


@pytest.mark.parametrize(
    "message",
    [
        "hello!",
        "https://example.com/video/123",
        "https://pinterest.com.evil.example/pin/123",
        "https://fakepinterest.com/pin/123",
        "https://evil.example/?next=https://pin.it/123",
    ],
)
def test_invalid_urls_are_rejected(message):
    assert bot.get_pinterest_url(message) is None


def test_missing_ffmpeg_is_reported(monkeypatch, tmp_path):
    monkeypatch.setattr(bot.shutil, "which", lambda name: None)

    with pytest.raises(RuntimeError, match="FFmpeg"):
        bot.download_video("https://pin.it/example", tmp_path)


def fake_ydl_that_creates_file(file_size):
    class FakeYoutubeDL:
        def __init__(self, options):
            self.options = options

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def extract_info(self, url, download=True):
            assert url == "https://pin.it/example"
            assert download is True
            file_name = self.options["outtmpl"].replace("%(id)s", "123").replace(
                "%(ext)s", "mp4"
            )
            Path(file_name).write_bytes(b"v" * file_size)

    return FakeYoutubeDL


def test_download_video_returns_generated_file(monkeypatch, tmp_path):
    monkeypatch.setattr(bot.shutil, "which", lambda name: "C:/ffmpeg/bin/" + name)
    monkeypatch.setattr(bot.yt_dlp, "YoutubeDL", fake_ydl_that_creates_file(16))

    file_path = bot.download_video("https://pin.it/example", tmp_path)

    assert file_path.name == "123.mp4"
    assert file_path.read_bytes() == b"v" * 16


def test_download_rejects_oversized_video(monkeypatch, tmp_path):
    monkeypatch.setattr(bot.shutil, "which", lambda name: "C:/ffmpeg/bin/" + name)
    monkeypatch.setattr(bot.yt_dlp, "YoutubeDL", fake_ydl_that_creates_file(11))
    monkeypatch.setattr(bot, "MAX_FILE_SIZE", 10)

    with pytest.raises(bot.VideoTooLargeError):
        bot.download_video("https://pin.it/example", tmp_path)
