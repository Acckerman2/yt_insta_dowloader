import asyncio
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable, Optional

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject

from app.config import settings
from app.database import db
from app.logger import logger


class RateLimitMiddleware(BaseMiddleware):
    def __init__(self, max_messages: int = 5, time_window: int = 60):
        self.max_messages = max_messages
        self.time_window = time_window
        self.user_messages: dict[int, list[float]] = defaultdict(list)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            now = time.time()
            timestamps = self.user_messages[user_id]
            timestamps[:] = [t for t in timestamps if now - t < self.time_window]

            if len(timestamps) >= self.max_messages:
                if isinstance(event, Message):
                    await event.answer(
                        f"Slow down! You're limited to {self.max_messages} "
                        f"requests per {self.time_window}s."
                    )
                return

            timestamps.append(now)

        return await handler(event, data)


class ForceSubscribeMiddleware(BaseMiddleware):
    def __init__(self):
        self.channel = settings.force_subscribe_channel

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not self.channel:
            return await handler(event, data)

        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            bot = data.get("bot")
            try:
                member = await bot.get_chat_member(
                    chat_id=self.channel, user_id=user_id
                )
                status = member.status if member else None
                if status in ("left", "kicked", "restricted"):
                    chat = await bot.get_chat(self.channel)
                    invite_link = chat.invite_link or f"https://t.me/{self.channel[1:]}"
                    text = (
                        f"Please join <b>{self.channel}</b> to use this bot.\n"
                        f"<a href='{invite_link}'>Join Channel</a>"
                    )
                    if isinstance(event, Message):
                        await event.answer(text, disable_web_page_preview=True)
                    return
            except Exception as e:
                logger.warning(f"Force subscribe check failed: {e}")

        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, throttle_time: float = 0.5):
        self.throttle_time = throttle_time
        self.last_execution: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id:
            last = self.last_execution.get(user_id, 0)
            now = time.time()
            if now - last < self.throttle_time:
                return
            self.last_execution[user_id] = now

        return await handler(event, data)
