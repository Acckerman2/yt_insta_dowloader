import asyncio
from pathlib import Path
from typing import Optional, Callable, Any

import yt_dlp

from app.config import settings
from app.logger import logger
from app.utils.progress import ProgressTracker


YOUTUBE_RESOLUTIONS = {
    "144": "bestvideo[ext=mp4][height<=144]+bestaudio[ext=m4a]/best[ext=mp4][height<=144]/best[ext=mp4]/worst[ext=mp4]",
    "240": "bestvideo[ext=mp4][height<=240]+bestaudio[ext=m4a]/best[ext=mp4][height<=240]/best[ext=mp4]",
    "360": "bestvideo[ext=mp4][height<=360]+bestaudio[ext=m4a]/best[ext=mp4][height<=360]/best[ext=mp4]",
    "480": "bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4][height<=480]/best[ext=mp4]",
    "720": "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[ext=mp4]",
    "1080": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4][height<=1080]/best[ext=mp4]",
    "1440": "bestvideo[ext=mp4][height<=1440]+bestaudio[ext=m4a]/best[ext=mp4][height<=1440]/best[ext=mp4]",
    "2160": "bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/best[ext=mp4][height<=2160]/best[ext=mp4]",
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
}

YOUTUBE_RESOLUTIONS_NOFF = {
    "144": "best[ext=mp4][height<=144]/worst[ext=mp4]",
    "240": "best[ext=mp4][height<=240]/best[ext=mp4]",
    "360": "best[ext=mp4][height<=360]/best[ext=mp4]",
    "480": "best[ext=mp4][height<=480]/best[ext=mp4]",
    "720": "best[ext=mp4][height<=720]/best[ext=mp4]",
    "1080": "best[ext=mp4][height<=1080]/best[ext=mp4]",
    "1440": "best[ext=mp4][height<=1440]/best[ext=mp4]",
    "2160": "best[ext=mp4][height<=2160]/best[ext=mp4]",
    "best": "best[ext=mp4]/best",
}

AUDIO_FORMATS = {
    "64": "bestaudio[abr<=64]/worstaudio",
    "96": "bestaudio[abr<=96]/bestaudio[abr<=64]/worstaudio",
    "128": "bestaudio[abr<=128]/bestaudio[abr<=96]/worstaudio",
    "192": "bestaudio[abr<=192]/bestaudio[abr<=128]/worstaudio",
    "256": "bestaudio[abr<=256]/bestaudio[abr<=192]/worstaudio",
    "320": "bestaudio[abr<=320]/bestaudio[abr<=256]/bestaudio[abr<=192]",
    "best": "bestaudio/best",
}

AUDIO_FORMATS_NOFF = {
    "64": "bestaudio[ext=m4a][abr<=64]/worstaudio",
    "96": "bestaudio[ext=m4a][abr<=96]/bestaudio[ext=m4a][abr<=64]/worstaudio",
    "128": "bestaudio[ext=m4a][abr<=128]/bestaudio[ext=m4a][abr<=96]/worstaudio",
    "192": "bestaudio[ext=m4a][abr<=192]/bestaudio[ext=m4a][abr<=128]/worstaudio",
    "256": "bestaudio[ext=m4a][abr<=256]/bestaudio[ext=m4a][abr<=192]/worstaudio",
    "320": "bestaudio[ext=m4a][abr<=320]/bestaudio[ext=m4a][abr<=256]/bestaudio[ext=m4a][abr<=192]",
    "best": "bestaudio[ext=m4a]/bestaudio",
}


class YouTubeDownloader:
    def __init__(self):
        self.has_ffmpeg = settings.has_ffmpeg
        self.base_opts = {
            "outtmpl": str(Path(settings.download_path) / "%(id)s.%(ext)s"),
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "ignoreerrors": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
        }
        if settings.cookies_file and Path(settings.cookies_file).exists():
            self.base_opts["cookiefile"] = settings.cookies_file
        if settings.ffmpeg_location:
            self.base_opts["ffmpeg_location"] = settings.ffmpeg_location

    async def _run_in_executor(self, func: Callable, *args, **kwargs) -> Any:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

    def _make_progress_hook(self, tracker: ProgressTracker):
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

    def _find_mp4(self, video_id: str) -> Optional[str]:
        for f in Path(settings.download_path).iterdir():
            if video_id in f.name and f.suffix == ".mp4":
                return str(f)
        return None

    def _find_file(self, video_id: str, suffix: str = ".mp4") -> Optional[str]:
        for f in Path(settings.download_path).iterdir():
            if video_id in f.name and f.suffix == suffix:
                return str(f)
        return None

    async def extract_info(self, url: str, tracker: Optional[ProgressTracker] = None) -> Optional[dict]:
        try:
            opts = {
                **self.base_opts,
                "format": "bestaudio/best",
                "skip_download": True,
            }
            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=False)
            return info
        except Exception as e:
            logger.error(f"Failed to extract YouTube info: {e}")
            return None

    async def download_video(
        self,
        url: str,
        quality: str = "best",
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[str]:
        try:
            if self.has_ffmpeg:
                format_spec = YOUTUBE_RESOLUTIONS.get(quality, YOUTUBE_RESOLUTIONS["best"])
                postprocessors = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
                merge_fmt = "mp4"
            else:
                format_spec = YOUTUBE_RESOLUTIONS_NOFF.get(quality, YOUTUBE_RESOLUTIONS_NOFF["best"])
                postprocessors = []
                merge_fmt = None

            if tracker:
                tracker.set_stage("downloading")
                await tracker.refresh(force=True)

            opts = {
                **self.base_opts,
                "format": format_spec,
                "postprocessors": postprocessors,
                "progress_hooks": [self._make_progress_hook(tracker)] if tracker else [],
            }
            if merge_fmt:
                opts["merge_output_format"] = merge_fmt

            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=True)

            if info is None:
                return None

            file_path = self._find_mp4(info["id"])
            if not file_path:
                file_path = self._find_file(info["id"])
            if file_path:
                return file_path

            logger.error(f"Failed to produce file for {info['id']}")
            return None

        except Exception as e:
            logger.error(f"YouTube download failed: {e}")
            if tracker:
                tracker.set_stage("error", str(e))
                await tracker.refresh(force=True)
            return None

    async def download_audio(
        self,
        url: str,
        bitrate: str = "192",
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[str]:
        try:
            if self.has_ffmpeg:
                audio_format = AUDIO_FORMATS.get(bitrate, AUDIO_FORMATS["192"])
                bitrate_val = int(bitrate) if bitrate != "best" else 320
                postprocessors = [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": str(bitrate_val),
                    }
                ]
                target_ext = ".mp3"
            else:
                audio_format = AUDIO_FORMATS_NOFF.get(bitrate, AUDIO_FORMATS_NOFF["192"])
                postprocessors = []
                target_ext = ".m4a"

            if tracker:
                tracker.set_stage("downloading")
                await tracker.refresh(force=True)

            opts = {
                **self.base_opts,
                "format": audio_format,
                "postprocessors": postprocessors,
                "progress_hooks": [self._make_progress_hook(tracker)] if tracker else [],
            }

            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=True)

            if info is None:
                return None

            fpath = self._find_file(info["id"], target_ext)
            if fpath:
                return fpath

            fpath = self._find_file(info["id"])
            if fpath:
                return fpath

            return None

        except Exception as e:
            logger.error(f"YouTube audio download failed: {e}")
            if tracker:
                tracker.set_stage("error", str(e))
                await tracker.refresh(force=True)
            return None

    async def download_playlist(
        self, url: str, tracker: Optional[ProgressTracker] = None
    ) -> list[str]:
        try:
            if self.has_ffmpeg:
                fmt = "bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4][height<=720]/best[ext=mp4]"
                postprocessors = [{"key": "FFmpegVideoConvertor", "preferedformat": "mp4"}]
                merge_fmt = "mp4"
            else:
                fmt = "best[ext=mp4][height<=720]/best[ext=mp4]"
                postprocessors = []
                merge_fmt = None

            if tracker:
                tracker.set_stage("downloading")
                await tracker.refresh(force=True)

            opts = {
                **self.base_opts,
                "format": fmt,
                "postprocessors": postprocessors,
                "progress_hooks": [self._make_progress_hook(tracker)] if tracker else [],
                "max_downloads": 10,
            }
            if merge_fmt:
                opts["merge_output_format"] = merge_fmt

            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=True)
            if not info or "entries" not in info:
                return []

            files = []
            for entry in info["entries"]:
                if entry:
                    fp = self._find_mp4(entry["id"])
                    if not fp:
                        fp = self._find_file(entry["id"])
                    if fp:
                        files.append(fp)
            return files
        except Exception as e:
            logger.error(f"Playlist download failed: {e}")
            return []

    async def get_available_resolutions(self, url: str) -> list[dict]:
        try:
            opts = {
                **self.base_opts,
                "format": "bestvideo+bestaudio/best",
                "skip_download": True,
            }
            ydl = yt_dlp.YoutubeDL(opts)
            info = await self._run_in_executor(ydl.extract_info, url, download=False)
            if not info:
                return []

            formats = info.get("formats", [])
            seen = set()
            resolutions = []
            for f in formats:
                height = f.get("height")
                if height and height not in seen:
                    seen.add(height)
                    resolutions.append({
                        "height": height,
                        "label": f"{height}p",
                        "format_note": f.get("format_note", ""),
                    })

            resolutions.sort(key=lambda x: x["height"])
            return resolutions
        except Exception as e:
            logger.error(f"Failed to get resolutions: {e}")
            return []


youtube = YouTubeDownloader()
