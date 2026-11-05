# v1.0.0 — First stable release

First documented release of Pinterest Video Downloader Telegram Bot.

### Highlights

- Download publicly accessible Pinterest video pins from `pin.it` and `pinterest.com` links.
- Merge separate video and audio streams using yt-dlp and FFmpeg.
- Telegram `/start`, `/help` and `/about` commands with download status updates.
- Basic protection for shared use: up to two active downloads, one per user, and a 30-second cooldown.
- Temporary file cleanup, privacy-conscious logging and user-facing error messages.
- Local Python and Docker Compose start-up options.
- 38 unit tests passed locally before the release preparation; Ruff lint and format checks passed locally as well. CI results must be verified on the release commit.

### Installation

See the [README](https://github.com/KEEGAN16/pinterest-video-downloader-bot-telegram#readme) for Windows/Python and Docker Compose instructions. Create a Telegram bot using BotFather and configure your own `BOT_TOKEN` in `.env`.

### Known limitations

- Runs only while the local computer/process is active, unless you host it separately.
- Public video pins only; Pinterest changes and yt-dlp compatibility may affect downloading.
- Roughly 49 MiB file limit and in-memory request limits.

Use only with content you are authorized to download. This project is not affiliated with Pinterest or Telegram.
