"""Offline unit tests for Telegram handlers; no bot token or network required."""

import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from yt_dlp.utils import DownloadError

from pinterest_bot import handlers
from pinterest_bot.rate_limit import DownloadLimiter


def make_message(text=""):
    return SimpleNamespace(
        text=text,
        reply_text=AsyncMock(),
        reply_video=AsyncMock(),
        reply_document=AsyncMock(),
    )


def test_commands_reply_with_expected_information():
    async def exercise():
        message = make_message()
        update = SimpleNamespace(effective_message=message)
        await handlers.start(update, None)
        await handlers.help_command(update, None)
        await handlers.about_command(update, None)
        replies = [call.args[0] for call in message.reply_text.await_args_list]
        assert "Pinterest" in replies[0]
        assert "pin.it" in replies[1]
        assert "github.com/KEEGAN16" in replies[2]

    asyncio.run(exercise())


def test_set_commands_registers_all_commands():
    bot = SimpleNamespace(set_my_commands=AsyncMock())
    asyncio.run(handlers.set_commands(SimpleNamespace(bot=bot)))
    registered = bot.set_my_commands.await_args.args[0]
    assert [command.command for command in registered] == ["start", "help", "about"]


def test_invalid_message_shows_help():
    message = make_message("hello world")
    update = SimpleNamespace(effective_message=message)
    asyncio.run(handlers.handle_message(update, None))
    message.reply_text.assert_awaited_once()
    assert "valid Pinterest" in message.reply_text.await_args.args[0]


def test_busy_user_is_rejected():
    message = make_message("https://pin.it/abc")
    limiter = DownloadLimiter(max_concurrent=1, cooldown_seconds=0)
    assert limiter.try_start(42).allowed
    update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=42))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"download_limiter": limiter}))
    asyncio.run(handlers.handle_message(update, context))
    assert "already have" in message.reply_text.await_args.args[0]
    limiter.finish(42)


def test_handle_message_releases_slot_when_processing_fails(monkeypatch):
    message = make_message("https://pin.it/abc")
    message.reply_text.return_value = SimpleNamespace(edit_text=AsyncMock())
    limiter = DownloadLimiter(max_concurrent=1, cooldown_seconds=0)
    update = SimpleNamespace(effective_message=message, effective_user=SimpleNamespace(id=42))
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"download_limiter": limiter}))
    monkeypatch.setattr(handlers, "process_video", AsyncMock(side_effect=RuntimeError("test failure")))
    with pytest.raises(RuntimeError, match="test failure"):
        asyncio.run(handlers.handle_message(update, context))
    assert limiter.try_start(42).allowed


def test_process_video_sends_mp4_and_updates_status(monkeypatch):
    async def fake_to_thread(fn, url, folder: Path):
        assert url == "https://pin.it/abc"
        path = folder / "video.mp4"
        path.write_bytes(b"test video bytes")
        return path

    monkeypatch.setattr(handlers.asyncio, "to_thread", fake_to_thread)
    message = make_message()
    status = SimpleNamespace(edit_text=AsyncMock())
    asyncio.run(handlers.process_video(message, status, "https://pin.it/abc"))
    message.reply_video.assert_awaited_once()
    message.reply_document.assert_not_awaited()
    statuses = [call.args[0] for call in status.edit_text.await_args_list]
    assert "Uploading" in statuses[0]
    assert "Done" in statuses[1]


def test_download_error_is_reported(monkeypatch):
    async def fake_to_thread(*args):
        raise DownloadError("test downloader error")

    monkeypatch.setattr(handlers.asyncio, "to_thread", fake_to_thread)
    message = make_message()
    status = SimpleNamespace(edit_text=AsyncMock())
    asyncio.run(handlers.process_video(message, status, "https://pin.it/abc"))
    message.reply_video.assert_not_awaited()
    assert "Couldn't download" in status.edit_text.await_args.args[0]


def test_edit_status_handles_telegram_error():
    from telegram.error import TelegramError

    status = SimpleNamespace(edit_text=AsyncMock(side_effect=TelegramError("test error")))
    asyncio.run(handlers.edit_status(status, "New status"))
    status.edit_text.assert_awaited_once_with("New status")
