import asyncio
import hashlib
import os
import shutil
import time
from pathlib import Path
from typing import Optional

from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest
from aiogram.types import FSInputFile

from app.bot import bot
from app.config import settings
from app.database import db
from app.logger import logger


class FileManager:
    def __init__(self):
        self.temp_dir = Path(settings.download_path)
        self.max_file_size = settings.max_file_size
        self.log_channel_id = settings.log_channel_id

    async def initialize(self):
        if self.temp_dir.exists():
            shutil.rmtree(str(self.temp_dir), ignore_errors=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Temp directory ready: {self.temp_dir}")

    def get_file_size(self, file_path: str) -> int:
        try:
            return os.path.getsize(file_path)
        except OSError:
            return 0

    def is_within_limit(self, file_path: str) -> bool:
        return self.get_file_size(file_path) <= self.max_file_size

    def get_url_hash(self, url: str) -> str:
        return hashlib.sha256(url.encode()).hexdigest()[:16]

    async def get_cached_or_upload(self, file_path: str, url: str, platform: str) -> dict:
        url_hash = self.get_url_hash(url)

        cached = await db.get_cached_file(url_hash)
        if cached:
            await db.increment_cache_access(url_hash)
            logger.info(f"Cache hit for {url_hash}")
            return dict(cached)

        file_size = self.get_file_size(file_path)
        file_name = os.path.basename(file_path)

        if self.log_channel_id:
            file_id = await self.upload_to_log_channel(file_path, file_name, url_hash, platform)
            if file_id:
                return {
                    "cached": False,
                    "file_id": file_id,
                    "file_size": file_size,
                    "file_name": file_name,
                }

        return {
            "cached": True,
            "file_path": file_path,
            "file_size": file_size,
            "file_name": file_name,
        }

    async def send_from_cache(
        self, chat_id: int, cached: dict, caption: str
    ) -> bool:
        file_id = cached.get("file_id")
        if not file_id:
            return False

        try:
            ext = os.path.splitext(cached.get("file_name", ""))[1].lower()
            is_audio = ext in (".mp3", ".m4a", ".wav", ".flac")
            is_video = ext in (".mp4", ".mkv", ".webm", ".mov")

            if is_audio:
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=file_id,
                    caption=caption,
                )
            elif is_video:
                await bot.send_video(
                    chat_id=chat_id,
                    video=file_id,
                    caption=caption,
                    supports_streaming=True,
                )
            else:
                await bot.send_document(
                    chat_id=chat_id,
                    document=file_id,
                    caption=caption,
                )
            return True
        except TelegramBadRequest as e:
            logger.error(f"Send from cache failed: {e}")
            return False

    async def upload_to_log_channel(
        self, file_path: str, file_name: str, url_hash: str, platform: str
    ) -> Optional[str]:
        if not self.log_channel_id:
            logger.warning("No log channel configured, skipping upload")
            return None

        try:
            ext = os.path.splitext(file_path)[1].lower()
            is_audio = ext in (".mp3", ".m4a", ".wav", ".flac")
            is_video = ext in (".mp4", ".mkv", ".webm", ".mov")

            display_name = file_name
            if is_video and ext != ".mp4":
                display_name = os.path.splitext(file_name)[0] + ".mp4"

            sent = None
            caption = f"#{platform} | {display_name}"
            input_file = FSInputFile(file_path, filename=display_name)
            if is_audio:
                sent = await bot.send_audio(
                    chat_id=self.log_channel_id,
                    audio=input_file,
                    caption=caption,
                )
            elif is_video:
                sent = await bot.send_video(
                    chat_id=self.log_channel_id,
                    video=input_file,
                    caption=caption,
                    supports_streaming=True,
                )
            else:
                sent = await bot.send_document(
                    chat_id=self.log_channel_id,
                    document=input_file,
                    caption=caption,
                )

            if sent:
                file_id = None
                mime_type = None
                file_size = self.get_file_size(file_path)

                if is_audio and sent.audio:
                    file_id = sent.audio.file_id
                    mime_type = "audio/mpeg"
                elif is_video and sent.video:
                    file_id = sent.video.file_id
                    mime_type = "video/mp4"
                elif sent.document:
                    file_id = sent.document.file_id
                    mime_type = sent.document.mime_type or "application/octet-stream"

                if file_id:
                    await db.set_cached_file(
                        url_hash=url_hash,
                        platform=platform,
                        file_id=file_id,
                        file_size=file_size,
                        file_name=display_name,
                        mime_type=mime_type,
                    )
                    logger.info(f"Cached file_id {file_id[:20]} for {url_hash}")
                    return file_id

            return None
        except TelegramRetryAfter as e:
            logger.warning(f"Flood wait {e.retry_after}s, retrying...")
            await asyncio.sleep(e.retry_after)
            return await self.upload_to_log_channel(file_path, file_name, url_hash, platform)
        except TelegramBadRequest as e:
            logger.error(f"Telegram upload error: {e}")
            return None
        except Exception as e:
            logger.error(f"Log channel upload failed: {e}")
            return None

    async def delete_file(self, file_path: str):
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.debug(f"Deleted temp file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to delete {file_path}: {e}")

    async def cleanup_all(self):
        try:
            if self.temp_dir.exists():
                shutil.rmtree(str(self.temp_dir), ignore_errors=True)
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Temporary files cleaned up")
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    async def cleanup_old_files(self):
        now = time.time()
        try:
            if not self.temp_dir.exists():
                return
            for f in self.temp_dir.iterdir():
                if f.is_file():
                    mtime = f.stat().st_mtime
                    if (now - mtime) > settings.auto_delete_after_hours * 3600:
                        f.unlink(missing_ok=True)
                        logger.debug(f"Cleaned old file: {f}")
        except Exception as e:
            logger.error(f"Old file cleanup failed: {e}")


file_manager = FileManager()
