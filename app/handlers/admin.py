from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config import settings
from app.database import db
from app.logger import logger
from app.utils.helpers import format_size
from app.utils.file_manager import file_manager

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


@router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    stats = await db.get_stats()

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Stats", callback_data="admin_stats")
    builder.button(text="👥 Users", callback_data="admin_users")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")
    builder.button(text="🧹 Cleanup", callback_data="admin_cleanup")
    builder.button(text="🗄 Cache Info", callback_data="admin_cache")
    builder.adjust(2)

    text = (
        "<b>Admin Panel</b>\n\n"
        f"Total users: {stats['total_users']}\n"
        f"Downloads: {stats['total_downloads']}\n"
        f"Failed: {stats['failed_downloads']}\n"
        f"Data: {format_size(stats['total_size_bytes'])}"
    )

    await message.answer(text, reply_markup=builder.as_markup())


@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    stats = await db.get_stats()
    text = (
        "<b>Detailed Statistics</b>\n\n"
        f"👥 Total users: {stats['total_users']}\n"
        f"📥 Successful downloads: {stats['total_downloads']}\n"
        f"❌ Failed downloads: {stats['failed_downloads']}\n"
        f"💾 Total data transferred: {format_size(stats['total_size_bytes'])}"
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_users")
async def admin_users_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    users = await db.get_all_users()
    text = f"<b>Users ({len(users)})</b>\n\n"
    for u in users[:20]:
        name = u.get("first_name") or u.get("username") or str(u["user_id"])
        text += f"• {name} - {u.get('download_count', 0)} downloads\n"
    if len(users) > 20:
        text += f"\n... and {len(users) - 20} more"
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_cleanup")
async def admin_cleanup_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await file_manager.cleanup_all()
    await callback.message.edit_text("✅ Temporary files cleaned up.")
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_cache")
async def admin_cache_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    text = (
        "<b>Cache Info</b>\n\n"
        "Files are stored in the Telegram log channel using file_id.\n"
        "Temporary local files are deleted after upload.\n"
        "No permanent local storage is used.\n\n"
        "Log channel ID: "
        + (str(settings.log_channel_id) if settings.log_channel_id else "Not configured")
    )
    await callback.message.edit_text(text)
    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast_callback(callback: types.CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    await callback.message.edit_text(
        "Use /broadcast <message> to send a message to all users."
    )
    await callback.answer()


@router.message(Command("ban"))
async def ban_user(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if command.args:
        try:
            user_id = int(command.args.strip())
            await db.ban_user(user_id)
            await message.answer(f"✅ User {user_id} banned.")
            logger.info(f"User {user_id} banned by admin {message.from_user.id}")
        except ValueError:
            await message.answer("Invalid user ID.")
    else:
        await message.answer("Usage: /ban <user_id>")


@router.message(Command("unban"))
async def unban_user(message: types.Message, command: CommandObject):
    if not is_admin(message.from_user.id):
        return
    if command.args:
        try:
            user_id = int(command.args.strip())
            await db.unban_user(user_id)
            await message.answer(f"✅ User {user_id} unbanned.")
            logger.info(f"User {user_id} unbanned by admin {message.from_user.id}")
        except ValueError:
            await message.answer("Invalid user ID.")
    else:
        await message.answer("Usage: /unban <user_id>")
