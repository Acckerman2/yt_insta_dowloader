from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


VIDEO_QUALITIES = {
    "144": "144p",
    "240": "240p",
    "360": "360p",
    "480": "480p",
    "720": "720p HD",
    "1080": "1080p Full HD",
    "1440": "1440p 2K",
    "2160": "2160p 4K",
    "best": "Best Available",
}

AUDIO_BITRATES = {
    "64": "64 kbps",
    "96": "96 kbps",
    "128": "128 kbps",
    "192": "192 kbps",
    "256": "256 kbps",
    "320": "320 kbps",
    "best": "Best Available",
}


@dataclass
class UserStats:
    user_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    joined_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    download_count: int = 0
    total_downloads: int = 0


@dataclass
class DownloadTask:
    user_id: int
    url: str
    platform: str
    quality: str = "best"
    format: str = "video"
    resolution: str = "best"
    audio_bitrate: str = "192"
    chat_id: int = 0
    message_id: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3


@dataclass
class CachedFile:
    url_hash: str
    platform: str
    file_id: str
    file_size: int
    file_name: str
    mime_type: str


class DownloadFormat:
    VIDEO = "video"
    AUDIO = "audio"
    VIDEO_HD = "video_hd"
