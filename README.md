# Pinterest Video Downloader Telegram Bot

A lightweight Telegram bot that downloads **public Pinterest video pins** and sends the video back to the chat. It supports both `pin.it` short links and `pinterest.com` links, and uses FFmpeg to merge video and audio when Pinterest provides separate streams.

> **Run it on your own computer for free.** No hosting subscription is required. The bot is available to Telegram users **only while your Python process or Docker container is running** and the computer has internet access.

## Features

- Send a public Pinterest video URL; receive the downloaded video in Telegram when extraction succeeds.
- Short (`pin.it`) and standard (`pinterest.com`) Pinterest links.
- Audio/video merging with **yt-dlp + FFmpeg**.
- `/start`, `/help` and `/about` commands.
- Download/upload status updates and user-friendly error messages.
- Temporary download files are removed after each request.
- Up to **2 active downloads** at once, **1 per user**, with a **30-second cooldown** after completion (in-memory limits).
- Approximate **49 MiB maximum** downloaded file size for Telegram uploads.
- Unit tests with **pytest**, linting and formatting with **Ruff**, and **GitHub Actions** checks.
- Optional **Docker Compose** setup.

## Requirements

For local Python use:

- Python **3.12+** (the automated checks target Python 3.12 and 3.13).
- **FFmpeg and FFprobe** available on your `PATH`.
- An internet connection.
- A Telegram bot token obtained from [@BotFather](https://t.me/BotFather).

Docker users need Docker Engine / Docker Desktop with Docker Compose instead of installing Python and FFmpeg on the host.

## Setup: Python (Windows / PowerShell)

1. Clone the repository and enter the project directory:

   ```powershell
   git clone https://github.com/KEEGAN16/pinterest-video-downloader-bot-telegram.git
   cd pinterest-video-downloader-bot-telegram
   ```

2. Create a virtual environment and install the dependencies:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Install FFmpeg. On Windows 11, one option is:

   ```powershell
   winget install -e --id Gyan.FFmpeg
   ```

   Reopen your terminal and verify that both commands work:

   ```powershell
   ffmpeg -version
   ffprobe -version
   ```

4. Copy the example environment file and set your **own** bot token:

   ```powershell
   Copy-Item .env.example .env
   ```

   Edit `.env`:

   ```dotenv
   BOT_TOKEN=your_actual_bot_token_here
   ```

5. Start the bot:

   ```powershell
   .\.venv\Scripts\python.exe bot.py
   ```

   Keep this terminal open while using the bot. Use `Ctrl+C` to stop it.

On Linux/macOS, use the corresponding virtual-environment activation or `./.venv/bin/python`; install FFmpeg using your system's package manager.

## Setup: Docker Compose (optional)

Docker builds an image containing Python, dependencies and FFmpeg. **Docker runs locally too; it does not provide free 24/7 cloud hosting.**

1. Create a `.env` in the repository root (copy `.env.example`) and set `BOT_TOKEN`.
2. Start the container:

   ```bash
   docker compose up --build
   ```

   Or run it in the background:

   ```bash
   docker compose up -d --build
   ```

3. Show logs or stop the container:

   ```bash
   docker compose logs -f
   docker compose down
   ```

**Do not run `python bot.py` and `docker compose up` simultaneously with the same bot token.** Both would attempt to poll the same Telegram updates.

## Using the bot

1. Open your bot in Telegram and tap **Start** (or send `/start`).
2. Send a **public Pinterest video** link, for example `https://pin.it/...` or `https://www.pinterest.com/pin/...`.
3. Wait for the download and upload status to update. If successful, the bot sends the video into the chat.

| Command | Purpose |
| --- | --- |
| `/start` | Greeting and basic instructions |
| `/help` | Supported links, usage and limits |
| `/about` | Bot version and project information |

## Development and tests

Install the development dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the same checks used during development:

```powershell
python -m pytest -v
python -m ruff check .
python -m ruff format --check .
```

The GitHub Actions workflow also checks the tests and Ruff on pull requests and pushes to `main`.

## Project layout

```text
bot.py                      # Start the Telegram application
pinterest_bot/
  config.py                 # App version and non-secret settings
  downloader.py             # URL validation, yt-dlp, FFmpeg
  handlers.py               # Telegram commands and messages
  rate_limit.py             # Per-user and global download limits
tests/                       # Unit tests
.github/workflows/tests.yml # Automated CI checks
Dockerfile                  # Container image
compose.yaml                # Local Docker Compose setup
.env.example                # Example token configuration
```

## Limitations

- **Not all pins work:** the pin must contain a publicly accessible video, and Pinterest or yt-dlp changes may interrupt downloads.
- **No guaranteed uptime:** without hosting, the bot is offline when the computer is off, asleep, disconnected or the process is stopped.
- **Small-scale usage:** rate limits are stored only in memory and reset on restart. This is not a high-volume hosted service.
- **Size limit:** files above the configured maximum cannot be sent; very large downloads are not supported.
- **No promise of support for private content** or access-restricted pins.

## Security and privacy

- Never commit `.env` or post your bot token in issues, logs or screenshots. If exposed, revoke the token with BotFather and replace it.
- `.env` is ignored by Git and excluded from the Docker build context.
- The app is designed not to log users' messages, Pinterest URLs or Telegram user IDs; successful requests are logged with basic timing and file size information.
- Downloaded media is stored temporarily during processing and removed afterward.
- Telegram and Pinterest are third-party services with their own data processing and terms.

**Only download media that you are authorized to save or reuse.** Respect creators' rights and Pinterest's terms. This project is not affiliated with Pinterest or Telegram.

## Contributing

Issues and pull requests for bugs, tests and documentation are welcome. Please do not include bot tokens, private links, credentials or copyrighted video files in bug reports.

## Source

[GitHub repository](https://github.com/KEEGAN16/pinterest-video-downloader-bot-telegram)
