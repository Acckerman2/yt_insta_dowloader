import asyncio
import os
from pathlib import Path
from typing import Optional, Callable, Any

import yt_dlp

from app.config import settings
from app.logger import logger
from app.utils.progress import ProgressTracker


IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


class InstagramDownloader:
    def __init__(self):
        self.has_ffmpeg = settings.has_ffmpeg
        self.base_opts = {
            "outtmpl": str(Path(settings.download_path) / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
            "retries": 3,
            "socket_timeout": 30,
        }
        if settings.cookies_file and Path(settings.cookies_file).exists():
            self.base_opts["cookiefile"] = settings.cookies_file
        if settings.ffmpeg_location:
            self.base_opts["ffmpeg_location"] = settings.ffmpeg_location

    async def _run_in_executor(self, func: Callable, *args, **kwargs) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _make_progress_hook(self, tracker: Optional[ProgressTracker] = None):
        if not tracker:
            return None
        has_ffmpeg = self.has_ffmpeg
        loop = asyncio.get_event_loop()
        def hook(status: dict):
            if status.get("status") == "downloading":
                total = status.get("total_bytes") or status.get("total_bytes_estimate", 0)
                downloaded = status.get("downloaded_bytes", 0)
                speed = status.get("speed", 0)
                eta = status.get("eta", 0)
                if total > 0:
                    percent = (downloaded / total) * 100
                else:
                    percent = 0
                tracker.update_download(percent, downloaded, total, speed, eta)
                asyncio.run_coroutine_threadsafe(tracker.refresh(), loop)
            elif status.get("status") == "finished":
                if has_ffmpeg:
                    tracker.set_stage("converting")
                    asyncio.run_coroutine_threadsafe(tracker.refresh(force=True), loop)
        return hook

    def _find_mp4(self, media_id: str) -> Optional[str]:
        for f in Path(settings.download_path).iterdir():
            if media_id in f.name and f.suffix == ".mp4":
                return str(f)
        return None

    def _find_image(self, media_id: str) -> Optional[str]:
        for f in Path(settings.download_path).iterdir():
            if media_id in f.name and f.suffix in IMAGE_EXTS:
                return str(f)
        return None

    async def extract_info(self, url: str, tracker: Optional[ProgressTracker] = None) -> Optional[dict]:
        try:
            opts = {**self.base_opts, "skip_download": True}
            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=False)
            return info
        except Exception as e:
            logger.error(f"Failed to extract Instagram info: {e}")
            return None

    async def download_media(
        self,
        url: str,
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[list[dict]]:
        try:
            if tracker:
                tracker.set_stage("downloading")
                await tracker.refresh(force=True)

            if self.has_ffmpeg:
                fmt = "best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                postprocessors = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
                merge_fmt = "mp4"
            else:
                fmt = "best[ext=mp4]/best"
                postprocessors = []
                merge_fmt = None

            opts = {
                **self.base_opts,
                "format": fmt,
                "postprocessors": postprocessors,
                "progress_hooks": [self._make_progress_hook(tracker)] if tracker else [],
            }
            if merge_fmt:
                opts["merge_output_format"] = merge_fmt

            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=True)

            if info is None:
                return None

            results = []
            entries = info.get("entries", [info])

            for entry in entries:
                if not entry:
                    continue

                media_id = entry.get("id", "")

                file_path = self._find_mp4(media_id)
                if not file_path:
                    file_path = self._find_image(media_id)

                if file_path and os.path.exists(file_path):
                    results.append({
                        "file_path": file_path,
                        "media_id": media_id,
                        "title": entry.get("title") or entry.get("description", "Instagram Media")[:100],
                        "thumbnail": entry.get("thumbnail"),
                    })

            return results if results else None
        except Exception as e:
            logger.error(f"Instagram download failed: {e}")
            if tracker:
                tracker.set_stage("error", str(e))
                await tracker.refresh(force=True)
            return None

    async def download_stories(
        self,
        url: str,
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[list[dict]]:
        return await self.download_media(url, tracker)

    async def download_carousel(
        self,
        url: str,
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[list[dict]]:
        return await self.download_media(url, tracker)


instagram = InstagramDownloader()
