# Telegram Media Downloader

A high-performance Telegram bot for downloading media from YouTube and Instagram, built with Python 3.12+ and aiogram 3.x.

## Features

- **YouTube**: videos, shorts, music, playlists
- **Instagram**: reels, posts, photos, stories, carousel
- **Auto-detection**: just send any URL, bot identifies the platform
- **Video quality selection**: 144p, 360p, 720p HD, 1080p Full HD, 2K, 4K
- **Audio extraction**: MP3 with selectable bitrate (64-320 kbps)
- **Telegram storage channel**: media uploaded to private log channel, cached via file_id
- **No permanent local storage**: temp files auto-deleted after upload
- **File caching**: reuses Telegram CDN for duplicate requests
- **Queue system**: concurrent download support with user queue
- **Retry system**: automatic retry for failed downloads (3 attempts)
- **Progress messages**: real-time status during download
- **Auto cleanup**: old temp files cleaned periodically
- **Rate limiting & throttling**: anti-spam protection
- **Force subscribe**: optional channel membership requirement
- **Admin panel**: stats, users, broadcast, cache info, cleanup
- **SQLite database**: user statistics and file cache
- **Webhook and polling**: both modes supported
- **Docker**: ready for containerized deployment
- **Logging**: comprehensive logging system

## Project Structure

```
telegram-bot/
├── app/
│   ├── __init__.py
│   ├── main.py            # Entry point
│   ├── config.py          # Configuration (pydantic-settings)
│   ├── bot.py             # Bot & dispatcher setup
│   ├── database.py        # SQLite database layer
│   ├── logger.py          # Logging setup
│   ├── models.py          # Data models & quality presets
│   ├── middlewares.py     # Rate limit, force sub, throttling
│   ├── handlers/
│   │   ├── start.py       # /start command
│   │   ├── help.py        # /help command
│   │   ├── settings.py    # /settings command
│   │   ├── stats.py       # /stats command
│   │   ├── download.py    # URL download handler
│   │   ├── broadcast.py   # /broadcast command
│   │   └── admin.py       # Admin panel
│   ├── services/
│   │   ├── detector.py    # URL platform detection
│   │   ├── youtube.py     # YouTube downloader
│   │   ├── instagram.py   # Instagram downloader
│   │   └── downloader.py  # Download orchestrator
│   ├── utils/
│   │   ├── helpers.py     # Formatting helpers
│   │   ├── file_manager.py# File caching & log channel
│   │   └── queue_manager.py# Async download queue
│   └── api/
│       └── webhook.py     # FastAPI webhook server
├── downloads/             # Temporary download storage
├── data/                  # SQLite database
├── logs/                  # Log files
├── .env.example           # Environment config template
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker build
├── docker-compose.yml     # Docker compose
├── Makefile               # Utility commands
└── README.md              # This file
```

## Requirements

- Python 3.12+
- ffmpeg (for audio extraction and video merging)
- Telegram Bot Token (from @BotFather)
- Private Telegram channel for media storage (optional but recommended)

## Quick Start

### 1. Clone and setup

```bash
git clone <repo-url> telegram-bot
cd telegram-bot
cp .env.example .env
```

### 2. Edit .env

```bash
# Edit .env with your bot token
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=[your_telegram_id]
LOG_CHANNEL_ID=-1001234567890  # Your private channel ID
```

### 3. Install dependencies

```bash
pip install uv
uv pip install --system -r requirements.txt
```

### 4. Install ffmpeg

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install ffmpeg -y
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Download from https://ffmpeg.org/download.html and add to PATH.

### 5. Run the bot

```bash
python app/main.py
```

## Telegram Log Channel Setup

The bot uses a private Telegram channel as a storage backend instead of saving files to disk permanently.

### How to set up:

1. Create a private Telegram channel (e.g., `@my_media_storage` or any private channel)
2. Add your bot as an administrator to the channel (give it "Post Messages" permission)
3. Get the channel ID:
   - Forward a message from the channel to `@getidsbot` (or use `@RawDataBot`)
   - The channel ID will be negative, like `-1001234567890`
4. Set `LOG_CHANNEL_ID=-1001234567890` in your `.env` file

### How it works:

1. User sends a URL → bot detects platform
2. Bot shows quality/resolution selection (if not set in preferences)
3. Bot downloads the media temporarily to `./downloads/`
4. Bot uploads the media to your private log channel
5. Bot stores the Telegram `file_id` in database cache
6. Bot forwards the media to the user using `file_id`
7. Temporary file is deleted immediately
8. Future requests for the same URL use cached `file_id` (instant delivery)

## Video Quality Options

| Setting | Description |
|---------|-------------|
| Best Available | Highest resolution available (up to 4K/8K) |
| 144p | Lowest quality, smallest file |
| 360p | Standard definition |
| 480p | DVD quality |
| 720p HD | High definition |
| 1080p Full HD | Full high definition |
| 1440p 2K | 2K resolution |
| 2160p 4K | Ultra high definition |

## Audio Quality Options

| Setting | Bitrate |
|---------|---------|
| Best Available | Highest available |
| 64 kbps | Low quality, smallest file |
| 96 kbps | Standard quality |
| 128 kbps | Good quality |
| 192 kbps | High quality (default) |
| 256 kbps | Very high quality |
| 320 kbps | Maximum quality |

## Docker Setup

### Build and run with Docker Compose:

```bash
docker compose build
docker compose up -d
```

### View logs:

```bash
docker compose logs -f
```

### Stop:

```bash
docker compose down
```

## VPS Deployment Guide

### 1. Server setup (Ubuntu 22.04/24.04)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Reboot or re-login for group changes
```

### 2. Deploy bot

```bash
git clone <repo-url> telegram-bot
cd telegram-bot
cp .env.example .env
nano .env  # Edit with your config
docker compose up -d
```

### 3. Nginx reverse proxy (for webhook mode)

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /webhook/ {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

```bash
# Install nginx
sudo apt install nginx -y
sudo nano /etc/nginx/sites-available/tg-bot
sudo ln -s /etc/nginx/sites-available/tg-bot /etc/nginx/sites-enabled/
sudo certbot --nginx -d yourdomain.com
sudo nginx -t && sudo systemctl reload nginx
```

### 4. Systemd service (for non-Docker deployment)

```ini
# /etc/systemd/system/tg-bot.service
[Unit]
Description=Telegram Media Downloader Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/telegram-bot
ExecStart=/usr/bin/python3 app/main.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/telegram-bot/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-bot
sudo systemctl start tg-bot
sudo journalctl -u tg-bot -f
```

## Webhook Setup

1. Set `WEBHOOK_URL` in `.env` to your public URL (e.g., `https://yourdomain.com`)
2. The bot automatically sets the webhook on startup when `WEBHOOK_URL` is configured
3. Ensure your server is accessible on port 443 (or the configured `WEBHOOK_PORT`)

### Telegram Webhook Requirements:
- Must use HTTPS (certificate required)
- Domain must be reachable from Telegram servers
- Recommended: use Cloudflare or Let's Encrypt for SSL

## Production Optimization

1. **Use webhook mode** instead of polling for better reliability
2. **Set up Redis** for improved queue management and caching
3. **Configure reverse proxy** (Nginx) with rate limiting
4. **Monitor with** `docker compose logs -f` or `journalctl -u tg-bot`
5. **Set memory limits** in docker-compose.yml
6. **Regular cleanup** of old downloads via admin panel
7. **Use cookies.txt** for accessing restricted or age-restricted content
8. **Configure log rotation** to prevent disk full
9. **Enable log channel** to offload storage to Telegram CDN

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and usage guide |
| `/help` | Detailed help and supported URLs |
| `/settings` | Configure video resolution, audio bitrate, format |
| `/stats` | View your download statistics |
| `/cancel` | Cancel active downloads |
| `/broadcast` | (Admin) Send message to all users |
| `/admin` | (Admin) Open admin panel |
| `/ban <id>` | (Admin) Ban a user |
| `/unban <id>` | (Admin) Unban a user |

## How URLs Are Handled

### YouTube
- `https://youtube.com/watch?v=...` → video
- `https://youtu.be/...` → short video
- `https://youtube.com/shorts/...` → shorts
- `https://music.youtube.com/...` → music/audio
- `https://youtube.com/playlist?list=...` → playlist (first 10)

### Instagram
- `https://instagram.com/p/...` → post (photo/video/carousel)
- `https://instagram.com/reel/...` → reel
- `https://instagram.com/stories/username/...` → story

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `BOT_TOKEN` | Telegram Bot Token | (required) |
| `ADMIN_IDS` | JSON array of admin user IDs | `[]` |
| `FORCE_SUBSCRIBE_CHANNEL` | Channel username for force sub | None |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///data/bot.db` |
| `REDIS_URL` | Redis URL (optional) | None |
| `WEBHOOK_URL` | Public URL for webhook mode | None |
| `WEBHOOK_SECRET` | Webhook secret token | None |
| `DOWNLOAD_PATH` | Temp download directory | `./downloads` |
| `MAX_FILE_SIZE` | Max upload file size (bytes) | `52428800` |
| `COOKIES_FILE` | Path to cookies.txt for auth | None |
| `LOG_LEVEL` | Logging level | `INFO` |
| `LOG_CHANNEL_ID` | Private channel ID for media storage | None |
| `DEFAULT_VIDEO_QUALITY` | Default video resolution | `best` |
| `DEFAULT_AUDIO_QUALITY` | Default audio bitrate | `192` |
| `MAX_CONCURRENT_DOWNLOADS` | Max simultaneous downloads | `5` |
| `AUTO_DELETE_AFTER_HOURS` | Auto-delete temp files after N hours | `1` |

## License

MIT
