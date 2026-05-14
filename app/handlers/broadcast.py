import asyncio

from aiogram import Router, types
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.bot import bot
from app.config import settings
from app.database import db
from app.logger import logger
from app.utils.helpers import format_size

router = Router()


class BroadcastStates(StatesGroup):
    waiting_message = State()


@router.message(Command("broadcast"))
async def broadcast_start(message: types.Message, state: FSMContext, command: CommandObject):
    if message.from_user.id not in settings.admin_ids:
        await message.answer("You are not authorized to use this command.")
        return

    if command.args:
        msg_text = command.args
        await _execute_broadcast(message, msg_text)
    else:
        await message.answer(
            "Send the message you want to broadcast to all users.\n"
            "Send /cancel to abort."
        )
        await state.set_state(BroadcastStates.waiting_message)


@router.message(BroadcastStates.waiting_message)
async def broadcast_receive(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith("/cancel"):
        await state.clear()
        await message.answer("Broadcast cancelled.")
        return

    await _execute_broadcast(message, message.text or message.caption or " ")
    await state.clear()


async def _execute_broadcast(message: types.Message, text: str):
    status_msg = await message.answer("Starting broadcast...")

    users = await db.get_all_users()
    total = len(users)
    success = 0
    failed = 0

    for i, user in enumerate(users):
        try:
            await bot.send_message(
                chat_id=user["user_id"],
                text=f"<b>Broadcast</b>\n\n{text}",
                disable_web_page_preview=True,
            )
            success += 1
        except Exception as e:
            failed += 1
            logger.warning(f"Broadcast failed for {user['user_id']}: {e}")

        if i % 10 == 0:
            try:
                await status_msg.edit_text(
                    f"Broadcasting... {i}/{total}\n"
                    f"Success: {success} | Failed: {failed}"
                )
            except Exception:
                pass

        await asyncio.sleep(0.05)

    await db.log_broadcast(message.from_user.id, text, total, success, failed)

    await status_msg.edit_text(
        f"<b>Broadcast Complete</b>\n\n"
        f"Total users: {total}\n"
        f"Success: {success}\n"
        f"Failed: {failed}"
    )
