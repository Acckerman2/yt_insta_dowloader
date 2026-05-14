from aiogram import Router, types
from aiogram.filters import CommandStart

from app.database import db
from app.logger import logger

router = Router()


@router.message(CommandStart())
async def start_handler(message: types.Message):
    user = message.from_user
    await db.upsert_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name,
        last_name=user.last_name,
    )
    logger.info(f"User {user.id} started the bot")

    text = (
        f"<b>Welcome, {user.first_name}!</b>\n\n"
        "I can download media from YouTube and Instagram in high quality.\n\n"
        "<b>Supported platforms:</b>\n"
        "• YouTube videos, shorts, music, playlists\n"
        "• Instagram reels, posts, photos, stories\n\n"
        "<b>How to use:</b>\n"
        "Just send me any supported link and I'll handle the rest.\n"
        "You'll be prompted to choose quality before downloading.\n\n"
        "<b>Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - Show help\n"
        "/settings - Configure quality preferences\n"
        "/stats - Your download stats\n"
        "/cancel - Cancel current download"
    )
    await message.answer(text, disable_web_page_preview=True)
