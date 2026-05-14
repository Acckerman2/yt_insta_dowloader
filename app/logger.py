import logging
import sys
from pathlib import Path

from app.config import settings


def setup_logging() -> logging.Logger:
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(
        log_dir / "bot.log", encoding="utf-8", mode="a"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    root_logger = logging.getLogger("bot")
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    yt_dlp_logger = logging.getLogger("yt_dlp")
    yt_dlp_logger.setLevel(logging.WARNING)

    return root_logger


logger = setup_logging()
