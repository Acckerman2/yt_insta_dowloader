import math
import re
from datetime import timedelta
from typing import Optional


def format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {units[i]}"


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "00:00"
    td = timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_speed(speed: Optional[float]) -> str:
    if speed is None or speed <= 0:
        return "N/A"
    return format_size(int(speed)) + "/s"


def format_eta(eta: Optional[int]) -> str:
    if eta is None or eta <= 0:
        return "N/A"
    return format_duration(eta)


def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', "_", name)


def progress_bar(percent: float, length: int = 20) -> str:
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return bar


def is_valid_url(text: str) -> bool:
    url_pattern = re.compile(
        r"https?://"
        r"(?:www\.)?"
        r"[-a-zA-Z0-9@:%._+~#=]{1,256}"
        r"\.[a-zA-Z0-9()]{1,6}"
        r"\b[-a-zA-Z0-9()@:%_+.~#?&/=]*"
    )
    return bool(url_pattern.match(text.strip()))
