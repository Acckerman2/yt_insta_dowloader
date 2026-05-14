import time
from typing import Optional

from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter, TelegramBadRequest

from app.utils.helpers import format_size, progress_bar


STAGES = {
    "detecting": "🔍 Detecting URL...",
    "fetching": "📡 Fetching media info...",
    "downloading": "📥 Downloading...",
    "converting": "🔄 Converting to MP4...",
    "uploading": "📤 Uploading to Telegram...",
    "saving": "💾 Saving to log channel...",
    "done": "✅ Completed",
    "error": "❌ Failed",
    "queued": "⏳ Queued...",
}


class ProgressTracker:
    def __init__(self, bot: Bot, chat_id: int, message_id: int, quality_label: str = ""):
        self.bot = bot
        self.chat_id = chat_id
        self.message_id = message_id
        self.quality_label = quality_label

        self.percent: float = 0
        self.speed: Optional[float] = None
        self.downloaded_bytes: int = 0
        self.total_bytes: Optional[int] = None
        self.eta: Optional[int] = None
        self.stage: str = "queued"
        self.error_message: Optional[str] = None

        self.detail: Optional[str] = None

        self._last_update: float = 0
        self._last_percent: int = -1
        self._min_interval: float = 2.0

    def _throttle(self, force: bool = False) -> bool:
        now = time.time()
        current_pct = int(self.percent)
        if force or current_pct != self._last_percent:
            if force or (now - self._last_update >= self._min_interval):
                self._last_update = now
                self._last_percent = current_pct
                return True
        return False

    def update_download(self, percent: float, downloaded: int, total: int, speed: float, eta: int):
        self.percent = percent
        self.downloaded_bytes = downloaded
        self.total_bytes = total if total > 0 else None
        self.speed = speed if speed and speed > 0 else None
        self.eta = eta if eta and eta > 0 else None
        if self.stage == "queued":
            self.stage = "downloading"

    def set_stage(self, stage: str, error: Optional[str] = None, detail: Optional[str] = None):
        self.stage = stage
        self.error_message = error
        self.detail = detail
        if stage == "uploading":
            self.percent = 0
            self.speed = None
            self.eta = None

    def _build_message(self) -> str:
        stage_icon = STAGES.get(self.stage, self.stage)

        lines = [f"<b>{stage_icon}</b>"]

        if self.stage == "downloading" and self.total_bytes and self.total_bytes > 0:
            bar = progress_bar(self.percent)
            lines.append(f"<code>{bar}</code>  <b>{self.percent:.0f}%</b>")

            parts = []
            if self.speed:
                parts.append(f"⚡ Speed: {format_size(int(self.speed))}/s")
            if self.downloaded_bytes and self.total_bytes:
                parts.append(f"📦 Size: {format_size(self.downloaded_bytes)} / {format_size(self.total_bytes)}")
            elif self.downloaded_bytes:
                parts.append(f"📦 Size: {format_size(self.downloaded_bytes)}")
            if self.eta:
                parts.append(f"⏳ ETA: {self._format_eta(self.eta)}")
            if parts:
                lines.extend(parts)

        elif self.stage == "uploading":
            lines.append("⏫ Sending file to Telegram...")
            if self.detail:
                lines.append(f"📄 {self.detail}")

        elif self.stage == "saving":
            lines.append("🏦 Caching to log channel...")

        elif self.stage == "converting":
            lines.append("🎞 Merging audio & video...")

        elif self.stage == "error" and self.error_message:
            lines.append(f"⚠️ {self.error_message[:200]}")

        if self.quality_label:
            lines.append(f"\n🎯 Quality: {self.quality_label}")

        return "\n".join(lines)

    def _format_eta(self, eta: int) -> str:
        if eta <= 0:
            return "N/A"
        hours, remainder = divmod(int(eta), 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        if minutes > 0:
            return f"{minutes}m {secs}s"
        return f"{secs}s"

    async def refresh(self, force: bool = False):
        if not self._throttle(force):
            return
        try:
            text = self._build_message()
            await self.bot.edit_message_text(
                chat_id=self.chat_id,
                message_id=self.message_id,
                text=text,
            )
        except TelegramRetryAfter as e:
            self._last_update = time.time()
            self._min_interval = min(self._min_interval + 0.5, 5.0)
        except TelegramBadRequest:
            pass
        except Exception:
            pass
