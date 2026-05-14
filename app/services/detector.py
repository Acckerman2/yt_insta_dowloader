import re
from typing import Optional


class PlatformDetector:
    YOUTUBE_PATTERNS = [
        r"(?:https?://)?(?:www\.)?(?:youtube\.com|youtu\.be)/",
        r"(?:https?://)?(?:www\.)?youtube\.com/shorts/",
        r"(?:https?://)?(?:www\.)?youtube\.com/playlist",
        r"(?:https?://)?(?:www\.)?music\.youtube\.com/",
    ]

    INSTAGRAM_PATTERNS = [
        r"(?:https?://)?(?:www\.)?instagram\.com/p/",
        r"(?:https?://)?(?:www\.)?instagram\.com/reel/",
        r"(?:https?://)?(?:www\.)?instagram\.com/tv/",
        r"(?:https?://)?(?:www\.)?instagram\.com/stories/",
    ]

    @classmethod
    def detect(cls, url: str) -> Optional[str]:
        url = url.strip()
        for pattern in cls.YOUTUBE_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                if "/shorts/" in url:
                    return "youtube_shorts"
                if "/playlist" in url:
                    return "youtube_playlist"
                if "music.youtube.com" in url:
                    return "youtube_music"
                return "youtube"
        for pattern in cls.INSTAGRAM_PATTERNS:
            if re.match(pattern, url, re.IGNORECASE):
                if "/reel/" in url:
                    return "instagram_reel"
                if "/stories/" in url:
                    return "instagram_story"
                return "instagram"
        return None

    @classmethod
    def is_supported(cls, url: str) -> bool:
        return cls.detect(url) is not None

    @classmethod
    def needs_resolution_prompt(cls, platform: str) -> bool:
        return platform in ("youtube", "youtube_shorts")

    @classmethod
    def get_platform_name(cls, platform: str) -> str:
        names = {
            "youtube": "YouTube Video",
            "youtube_shorts": "YouTube Shorts",
            "youtube_playlist": "YouTube Playlist",
            "youtube_music": "YouTube Music",
            "instagram": "Instagram Post",
            "instagram_reel": "Instagram Reel",
            "instagram_story": "Instagram Story",
        }
        return names.get(platform, platform.replace("_", " ").title())


detector = PlatformDetector()
