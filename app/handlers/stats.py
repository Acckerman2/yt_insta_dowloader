from aiogram import Router, types
from aiogram.filters import Command

from app.database import db
from app.utils.helpers import format_size

router = Router()


@router.message(Command("stats"))
async def stats_handler(message: types.Message):
    user_id = message.from_user.id
    user = await db.get_user(user_id)

    if not user:
        await message.answer("No stats available yet. Start downloading!")
        return

    text = (
        "<b>Your Statistics</b>\n\n"
        f"Downloads: {user.get('download_count', 0)}\n"
        f"First used: {user.get('joined_at', 'N/A')}\n"
        f"Last active: {user.get('last_active', 'N/A')}\n"
    )

    is_admin = user_id in (await _get_admin_ids())
    if is_admin:
        global_stats = await db.get_stats()
        text += (
            "\n<b>Global Statistics</b>\n\n"
            f"Total users: {global_stats['total_users']}\n"
            f"Total downloads: {global_stats['total_downloads']}\n"
            f"Failed downloads: {global_stats['failed_downloads']}\n"
            f"Total data: {format_size(global_stats['total_size_bytes'])}"
        )

    await message.answer(text)


async def _get_admin_ids() -> list[int]:
    from app.config import settings
    return settings.admin_ids
