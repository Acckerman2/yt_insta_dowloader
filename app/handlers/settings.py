from aiogram import Router, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.database import db
from app.models import VIDEO_QUALITIES, AUDIO_BITRATES
from app.config import settings

router = Router()


async def _settings_text(user_id: int) -> str:
    quality = await db.get_user_setting(user_id, "quality") or settings.default_video_quality
    fmt = await db.get_user_setting(user_id, "format_pref") or "video"
    resolution = await db.get_user_setting(user_id, "video_resolution") or settings.default_video_quality
    audio_bitrate = await db.get_user_setting(user_id, "audio_bitrate") or settings.default_audio_quality

    quality_label = VIDEO_QUALITIES.get(quality, quality)
    res_label = VIDEO_QUALITIES.get(resolution, resolution)
    abr_label = AUDIO_BITRATES.get(audio_bitrate, audio_bitrate)

    return (
        "<b>Download Settings</b>\n\n"
        f"Format: {fmt.capitalize()}\n"
        f"Video resolution: {res_label}\n"
        f"Audio bitrate: {abr_label}\n\n"
        "Click a button to change the setting."
    )


async def _settings_keyboard(user_id: int) -> types.InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Video Resolution", callback_data="set_video_res")
    builder.button(text="Audio Bitrate", callback_data="set_audio_br")
    builder.button(text=f"Format (Video/Audio)", callback_data="set_format")
    builder.button(text="Close", callback_data="close_settings")
    builder.adjust(1)
    return builder.as_markup()


@router.message(Command("settings"))
async def settings_handler(message: types.Message):
    user_id = message.from_user.id
    text = await _settings_text(user_id)
    keyboard = await _settings_keyboard(user_id)
    await message.answer(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "set_video_res")
async def set_video_res_callback(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for key, label in VIDEO_QUALITIES.items():
        builder.button(text=label, callback_data=f"vres_{key}")
    builder.button(text="Back", callback_data="back_settings")
    builder.adjust(3)

    await callback.message.edit_text(
        "<b>Select Video Resolution:</b>", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("vres_"))
async def video_res_chosen_callback(callback: types.CallbackQuery):
    resolution = callback.data.replace("vres_", "")
    user_id = callback.from_user.id
    await db.update_user_setting(user_id, "video_resolution", resolution)
    await db.update_user_setting(user_id, "quality", resolution)
    label = VIDEO_QUALITIES.get(resolution, resolution)
    await callback.answer(f"Video resolution set to {label}")

    text = await _settings_text(user_id)
    keyboard = await _settings_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "set_audio_br")
async def set_audio_br_callback(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    for key, label in AUDIO_BITRATES.items():
        builder.button(text=label, callback_data=f"abr_{key}")
    builder.button(text="Back", callback_data="back_settings")
    builder.adjust(3)

    await callback.message.edit_text(
        "<b>Select Audio Bitrate:</b>", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("abr_") and c.data != "abr_")
async def audio_br_chosen_callback(callback: types.CallbackQuery):
    bitrate = callback.data.replace("abr_", "")
    user_id = callback.from_user.id
    await db.update_user_setting(user_id, "audio_bitrate", bitrate)
    label = AUDIO_BITRATES.get(bitrate, bitrate)
    await callback.answer(f"Audio bitrate set to {label}")

    text = await _settings_text(user_id)
    keyboard = await _settings_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "set_format")
async def set_format_callback(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="Video", callback_data="format_video")
    builder.button(text="Audio", callback_data="format_audio")
    builder.button(text="Back", callback_data="back_settings")
    builder.adjust(1)

    await callback.message.edit_text(
        "<b>Select Format:</b>", reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("format_"))
async def format_chosen_callback(callback: types.CallbackQuery):
    fmt = callback.data.replace("format_", "")
    user_id = callback.from_user.id
    await db.update_user_setting(user_id, "format_pref", fmt)
    await callback.answer(f"Format set to {fmt}")

    text = await _settings_text(user_id)
    keyboard = await _settings_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "back_settings")
async def back_settings_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    text = await _settings_text(user_id)
    keyboard = await _settings_keyboard(user_id)
    await callback.message.edit_text(text, reply_markup=keyboard)


@router.callback_query(lambda c: c.data == "close_settings")
async def close_settings_callback(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer("Settings closed")
