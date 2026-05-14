import os
import json
import shutil
import tempfile
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


load_dotenv()


def _parse_int_list(v: Optional[str]) -> list[int]:
    if not v:
        return []
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return []


class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: list[int] = _parse_int_list(os.getenv("ADMIN_IDS"))
    force_subscribe_channel: Optional[str] = os.getenv("FORCE_SUBSCRIBE_CHANNEL")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///data/bot.db")
    redis_url: Optional[str] = os.getenv("REDIS_URL")
    webhook_url: Optional[str] = os.getenv("WEBHOOK_URL")
    webhook_secret: Optional[str] = os.getenv("WEBHOOK_SECRET")
    webhook_host: str = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    webhook_port: int = int(os.getenv("WEBHOOK_PORT", "8443"))
    download_path: str = os.getenv("DOWNLOAD_PATH", "")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", str(50 * 1024 * 1024)))
    cookies_file: Optional[str] = os.getenv("COOKIES_FILE")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_channel_id: Optional[int] = (
        int(os.getenv("LOG_CHANNEL_ID")) if os.getenv("LOG_CHANNEL_ID") else None
    )
    default_video_quality: str = os.getenv("DEFAULT_VIDEO_QUALITY", "best")
    default_audio_quality: str = os.getenv("DEFAULT_AUDIO_QUALITY", "192")
    max_concurrent_downloads: int = int(os.getenv("MAX_CONCURRENT_DOWNLOADS", "2"))
    auto_delete_after_hours: int = int(os.getenv("AUTO_DELETE_AFTER_HOURS", "1"))
    ffmpeg_location: Optional[str] = os.getenv("FFMPEG_LOCATION")

    def __init__(self):
        if not self.download_path:
            self.download_path = str(
                Path(tempfile.gettempdir()) / "tg-media-bot"
            )

    @property
    def has_ffmpeg(self) -> bool:
        if self.ffmpeg_location:
            p = Path(self.ffmpeg_location)
            for exe in ("ffmpeg", "ffmpeg.exe"):
                if (p / exe).exists():
                    return True
        return shutil.which("ffmpeg") is not None


settings = Settings()
