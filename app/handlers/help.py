from aiogram import Router, types
from aiogram.filters import Command

router = Router()


@router.message(Command("help"))
async def help_handler(message: types.Message):
    text = (
        "<b>Help & Commands</b>\n\n"
        "<b>How to use:</b>\n"
        "Send any supported URL and I'll download it.\n\n"
        "<b>Supported URLs:</b>\n"
        "• YouTube: <code>https://youtube.com/watch?v=...</code>\n"
        "• YouTube Shorts: <code>https://youtube.com/shorts/...</code>\n"
        "• YouTube Music: <code>https://music.youtube.com/...</code>\n"
        "• YouTube Playlists: <code>https://youtube.com/playlist?list=...</code>\n"
        "• Instagram Reels: <code>https://instagram.com/reel/...</code>\n"
        "• Instagram Posts: <code>https://instagram.com/p/...</code>\n"
        "• Instagram Stories: <code>https://instagram.com/stories/username/...</code>\n\n"
        "<b>Video Quality Options:</b>\n"
        "• 144p, 360p, 720p HD, 1080p Full HD, 2K, 4K\n"
        "• Download in best available quality by default\n"
        "• Audio extraction with bitrate selection (64-320 kbps)\n\n"
        "<b>Commands:</b>\n"
        "/start - Welcome message\n"
        "/help - Show this help\n"
        "/settings - Change download preferences\n"
        "/stats - View your statistics\n"
        "/cancel - Cancel active downloads\n\n"
        "<b>Limits:</b>\n"
        "• Max file size: 50MB\n"
        "• Rate limit: 5 requests per minute\n\n"
        "<b>Tips:</b>\n"
        "• For best quality, use /settings to choose HD\n"
        "• Audio extraction with custom bitrate available in /settings\n"
        "• Playlists are limited to first 10 videos"
    )
    await message.answer(text, disable_web_page_preview=True)
