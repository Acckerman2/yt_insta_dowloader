from typing import Optional

from app.services.youtube import youtube
from app.services.instagram import instagram
from app.services.detector import detector
from app.logger import logger
from app.utils.progress import ProgressTracker


class DownloaderService:
    async def download(
        self,
        url: str,
        quality: str = "best",
        fmt: str = "video",
        resolution: str = "best",
        audio_bitrate: str = "192",
        tracker: Optional[ProgressTracker] = None,
    ) -> Optional[dict]:
        platform = detector.detect(url)
        if not platform:
            logger.warning(f"Unsupported platform for URL: {url}")
            return None

        try:
            if platform in ("youtube", "youtube_shorts"):
                if fmt == "audio":
                    file_path = await youtube.download_audio(url, audio_bitrate, tracker)
                else:
                    file_path = await youtube.download_video(url, resolution, tracker)

                if file_path:
                    info = await youtube.extract_info(url)
                    return {
                        "file_path": file_path,
                        "platform": platform,
                        "title": info.get("title", "Video") if info else "Video",
                        "duration": info.get("duration", 0) if info else 0,
                        "thumbnail": info.get("thumbnail") if info else None,
                        "format_type": "audio" if fmt == "audio" else "video",
                    }
                return None

            elif platform == "youtube_playlist":
                files = await youtube.download_playlist(url, tracker)
                if files:
                    return {
                        "file_path": files[0],
                        "files": files,
                        "platform": platform,
                        "title": "Playlist",
                        "is_playlist": True,
                    }
                return None

            elif platform == "youtube_music":
                file_path = await youtube.download_audio(url, audio_bitrate, tracker)
                if file_path:
                    info = await youtube.extract_info(url)
                    return {
                        "file_path": file_path,
                        "platform": platform,
                        "title": info.get("title", "Audio") if info else "Audio",
                        "thumbnail": info.get("thumbnail") if info else None,
                        "format_type": "audio",
                    }
                return None

            elif platform in ("instagram", "instagram_reel"):
                results = await instagram.download_media(url, tracker)
                if results:
                    first = results[0]
                    info = await instagram.extract_info(url)
                    return {
                        "file_path": first["file_path"],
                        "platform": platform,
                        "title": first.get("title", "Media"),
                        "thumbnail": first.get("thumbnail") or (info.get("thumbnail") if info else None),
                        "results": results,
                        "is_carousel": len(results) > 1,
                    }
                return None

            elif platform == "instagram_story":
                results = await instagram.download_stories(url, tracker)
                if results:
                    first = results[0]
                    return {
                        "file_path": first["file_path"],
                        "platform": platform,
                        "title": first.get("title", "Story"),
                        "thumbnail": first.get("thumbnail"),
                        "results": results,
                        "is_carousel": len(results) > 1,
                    }
                return None

            return None
        except Exception as e:
            logger.error(f"Download failed for {url}: {e}")
            if tracker:
                tracker.set_stage("error", str(e))
                await tracker.refresh(force=True)
            return None


downloader = DownloaderService()
