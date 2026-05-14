import os
import shutil
import tempfile
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic.functional_validators import field_validator
from typing import Optional
import json


class Settings(BaseSettings):
    bot_token: str = ""
    admin_ids: list[int] = []
    force_subscribe_channel: Optional[str] = None
    database_url: str = "sqlite+aiosqlite:///data/bot.db"
    redis_url: Optional[str] = None
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8443
    download_path: str = ""
    max_file_size: int = 52428800
    cookies_file: Optional[str] = None
    log_level: str = "INFO"

    log_channel_id: Optional[int] = None
    default_video_quality: str = "best"
    default_audio_quality: str = "192"
    max_concurrent_downloads: int = 2
    auto_delete_after_hours: int = 1
    ffmpeg_location: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def model_post_init(self, __context):
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

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []


settings = Settings()
