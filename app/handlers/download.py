import asyncio
import os
from datetime import datetime
from typing import Optional

from aiogram import Router, types
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot import bot
from app.config import settings
from app.database import db
from app.logger import logger
from app.models import DownloadTask, VIDEO_QUALITIES, AUDIO_BITRATES
from app.services.detector import detector
from app.utils.file_manager import file_manager
from app.utils.helpers import format_size, format_duration
from app.utils.progress import ProgressTracker
from app.utils.queue_manager import queue_manager

router = Router()

PENDING_QUALITY: dict[int, dict] = {}


@router.message(lambda msg: msg.text and detector.is_supported(msg.text.strip()))
async def handle_url(message: types.Message):
    user_id = message.from_user.id
    url = message.text.strip()

    if await db.is_banned(user_id):
        await message.answer("You are banned from using this bot.")
        return

    platform = detector.detect(url)
    logger.info(f"Download request from {user_id}: {platform} - {url[:60]}")

    quality = await db.get_user_setting(user_id, "quality") or settings.default_video_quality
    fmt = await db.get_user_setting(user_id, "format_pref") or "video"
    resolution = await db.get_user_setting(user_id, "video_resolution") or settings.default_video_quality
    audio_bitrate = await db.get_user_setting(user_id, "audio_bitrate") or settings.default_audio_quality

    if quality == "audio" or fmt == "audio":
        await _show_audio_quality_picker(message, user_id, url, platform)
        return

    if detector.needs_resolution_prompt(platform):
        await _show_resolution_picker(message, user_id, url, platform)
        return

    await _start_download(message.chat.id, user_id, url, platform, fmt, resolution, audio_bitrate)


async def _show_resolution_picker(message: types.Message, user_id: int, url: str, platform: str):
    builder = InlineKeyboardBuilder()
    for key, label in VIDEO_QUALITIES.items():
        builder.button(text=label, callback_data=f"dl_res_{key}")
    builder.button(text="Audio Only", callback_data="dl_fmt_audio")
    builder.adjust(3)

    PENDING_QUALITY[user_id] = {"url": url, "platform": platform}

    await message.answer(
        f"<b>Select video quality:</b>\n\n"
        f"Platform: {detector.get_platform_name(platform)}\n"
        f"Choose resolution or switch to audio:",
        reply_markup=builder.as_markup(),
    )


async def _show_audio_quality_picker(message: types.Message, user_id: int, url: str, platform: str):
    builder = InlineKeyboardBuilder()
    for key, label in AUDIO_BITRATES.items():
        builder.button(text=label, callback_data=f"dl_abr_{key}")
    builder.adjust(3)

    PENDING_QUALITY[user_id] = {"url": url, "platform": platform, "fmt": "audio"}

    await message.answer(
        f"<b>Select audio quality:</b>\n\n"
        f"Platform: {detector.get_platform_name(platform)}\n"
        f"Choose bitrate:",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(lambda c: c.data.startswith("dl_res_"))
async def resolution_chosen(callback: types.CallbackQuery):
    resolution = callback.data.replace("dl_res_", "")
    user_id = callback.from_user.id
    await db.update_user_setting(user_id, "video_resolution", resolution)

    await callback.answer(f"Quality set to {VIDEO_QUALITIES.get(resolution, resolution)}")
    await callback.message.delete()

    pending = PENDING_QUALITY.pop(user_id, None)
    if not pending:
        await callback.message.answer("Session expired. Please send the URL again.")
        return

    await _start_download(callback.message.chat.id, user_id, pending["url"], pending["platform"], "video", resolution, "192")


@router.callback_query(lambda c: c.data.startswith("dl_abr_"))
async def audio_bitrate_chosen(callback: types.CallbackQuery):
    bitrate = callback.data.replace("dl_abr_", "")
    user_id = callback.from_user.id
    await db.update_user_setting(user_id, "audio_bitrate", bitrate)

    await callback.answer(f"Audio quality set to {AUDIO_BITRATES.get(bitrate, bitrate)}")
    await callback.message.delete()

    pending = PENDING_QUALITY.pop(user_id, None)
    if not pending:
        await callback.message.answer("Session expired. Please send the URL again.")
        return

    await _start_download(callback.message.chat.id, user_id, pending["url"], pending["platform"], "audio", "best", bitrate)


def _ensure_mp4_filename(file_name: str) -> str:
    root, ext = os.path.splitext(file_name)
    ext_lower = ext.lower()
    if ext_lower in (".webm", ".mkv", ".mov", ".avi", ".flv"):
        return root + ".mp4"
    return file_name


@router.callback_query(lambda c: c.data == "dl_fmt_audio")
async def format_audio_chosen(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer("Switching to audio mode")
    await callback.message.delete()

    pending = PENDING_QUALITY.pop(user_id, None)
    if not pending:
        await callback.message.answer("Session expired. Please send the URL again.")
        return

    await _show_audio_quality_picker(callback.message, user_id, pending["url"], pending["platform"])


async def _start_download(
    chat_id: int, user_id: int, url: str, platform: str, fmt: str, resolution: str, audio_bitrate: str,
):
    url_hash = file_manager.get_url_hash(url)
    cached = await db.get_cached_file(url_hash)
    if cached:
        caption = (
            f"<b>{cached['file_name'][:100]}</b>\n"
            f"Source: {detector.get_platform_name(platform)}"
        )
        ok = await file_manager.send_from_cache(chat_id, cached, caption)
        if ok:
            await db.increment_cache_access(url_hash)
            await db.log_download(
                user_id=user_id, url=url, platform=platform,
                fmt=fmt, quality=resolution if fmt == "video" else audio_bitrate,
                file_size=cached['file_size'], file_id=cached['file_id'], success=True,
            )
            await db.increment_downloads(user_id)
            await bot.send_message(chat_id, "✅ Download complete (from cache)!")
            return
        else:
            logger.info("Cache expired, re-downloading...")

    quality_label = ""
    if fmt == "video":
        quality_label = f"Video - {VIDEO_QUALITIES.get(resolution, resolution)}"
    else:
        quality_label = f"Audio - {AUDIO_BITRATES.get(audio_bitrate, audio_bitrate)} kbps"

    status_msg = await bot.send_message(
        chat_id,
        f"📥 <b>Queued</b>\n"
        f"Platform: {detector.get_platform_name(platform)}\n"
        f"{quality_label}\n"
        f"⏳ Waiting for your turn...",
    )

    tracker = ProgressTracker(
        bot=bot,
        chat_id=chat_id,
        message_id=status_msg.message_id,
        quality_label=quality_label,
    )
    tracker.set_stage("queued")
    await tracker.refresh(force=True)

    task = DownloadTask(
        user_id=user_id,
        url=url,
        platform=platform,
        quality=resolution if fmt == "video" else audio_bitrate,
        format=fmt,
        resolution=resolution,
        audio_bitrate=audio_bitrate,
        chat_id=chat_id,
        message_id=status_msg.message_id,
        created_at=datetime.utcnow(),
    )

    task_id = await queue_manager.add_task(task, tracker=tracker)

    result = await queue_manager.wait_for_result(task_id, timeout=600)

    if result:
        await _send_media(chat_id, user_id, status_msg, result, url, url_hash, tracker)
    else:
        tracker.set_stage("error", "Download failed after retries")
        await tracker.refresh(force=True)


async def _send_media(
    chat_id: int, user_id: int, status_msg: types.Message, result: dict, url: str, url_hash: str,
    tracker: Optional[ProgressTracker] = None,
):
    file_path = result.get("file_path", "")
    results_list = result.get("results")

    if not results_list and (not file_path or not os.path.exists(file_path)):
        if tracker:
            tracker.set_stage("error", "File not found after download")
            await tracker.refresh(force=True)
        return

    if not results_list:
        results_list = [{"file_path": file_path}]

    total_files = len(results_list)

    if tracker:
        tracker.set_stage("uploading", detail=f"{total_files} file(s)")
        await tracker.refresh(force=True)

    for idx, media_item in enumerate(results_list):
        fp = media_item.get("file_path", "")
        if not fp or not os.path.exists(fp):
            continue

        file_size = file_manager.get_file_size(fp)
        if not file_manager.is_within_limit(fp):
            if tracker:
                tracker.set_stage("error", f"File too large ({format_size(file_size)})")
                await tracker.refresh(force=True)
            else:
                await bot.send_message(
                    chat_id,
                    f"❌ File too large ({format_size(file_size)}). "
                    f"Max allowed: {format_size(settings.max_file_size)}",
                )
            await file_manager.delete_file(fp)
            continue

        if tracker:
            tracker.set_stage("uploading", detail=f"File {idx + 1}/{total_files}")
            await tracker.refresh(force=True)

        cached_info = await file_manager.get_cached_or_upload(fp, url, result.get("platform", "unknown"))

        raw_name = cached_info.get("file_name", os.path.basename(fp))
        file_name = _ensure_mp4_filename(raw_name)
        title = result.get("title", media_item.get("title", "Media"))
        platform = result.get("platform", "unknown")
        duration = result.get("duration", 0)
        is_carousel = result.get("is_carousel", False)

        caption_parts = [f"<b>{title[:100]}</b>"]
        caption_parts.append(f"Source: {detector.get_platform_name(platform)}")
        if duration:
            caption_parts.append(f"⏱ {format_duration(duration)}")
        if file_size:
            caption_parts.append(f"📦 {format_size(file_size)}")
        if is_carousel and total_files > 1:
            caption_parts.append(f"📸 Media {idx + 1} of {total_files}")
        caption = " | ".join(caption_parts)

        file_id = cached_info.get("file_id")
        if file_id:
            cached_info["file_name"] = file_name
            ok = await file_manager.send_from_cache(chat_id, cached_info, caption)
            if ok:
                await db.log_download(
                    user_id=user_id, url=url, platform=platform,
                    fmt=result.get("format_type", "video"),
                    quality=result.get("quality", "best"),
                    file_size=file_size,
                    file_id=file_id,
                    success=True,
                )
                await file_manager.delete_file(fp)
                continue

        try:
            ext = os.path.splitext(fp)[1].lower()
            is_audio = ext in (".mp3", ".m4a", ".wav", ".flac")
            is_video = ext in (".mp4", ".mkv", ".webm", ".mov", ".avi")

            input_file = FSInputFile(fp, filename=file_name)
            if is_audio:
                await bot.send_audio(
                    chat_id=chat_id,
                    audio=input_file,
                    caption=caption,
                    title=title[:50],
                )
            elif is_video and file_size < settings.max_file_size:
                await bot.send_video(
                    chat_id=chat_id,
                    video=input_file,
                    caption=caption,
                    supports_streaming=True,
                )
            else:
                await bot.send_document(
                    chat_id=chat_id,
                    document=input_file,
                    caption=caption,
                )
        except TelegramRetryAfter as e:
            logger.warning(f"Flood wait {e.retry_after}s, retrying...")
            await asyncio.sleep(e.retry_after)
            await _send_media(chat_id, user_id, status_msg, result, url, url_hash, tracker)
            return
        except Exception as e:
            logger.error(f"Send failed for {fp}: {e}")
            await file_manager.delete_file(fp)
            continue

        await db.log_download(
            user_id=user_id, url=url, platform=platform,
            fmt=result.get("format_type", "video"),
            quality=result.get("quality", "best"),
            file_size=file_size,
            file_id=None,
            success=True,
        )

        await file_manager.delete_file(fp)

    await db.increment_downloads(user_id)

    if tracker:
        tracker.set_stage("done")
        await tracker.refresh(force=True)

    await asyncio.sleep(0.5)

    try:
        await status_msg.delete()
        status_text = "✅ Download complete!"
        if total_files > 1:
            status_text = f"✅ Download complete! ({total_files} files)"
        await bot.send_message(chat_id, status_text)
    except Exception:
        pass


@router.message(Command("cancel"))
async def cancel_handler(message: types.Message):
    user_id = message.from_user.id
    await queue_manager.cancel_user_downloads(user_id)
    await message.answer("✅ All your active downloads have been cancelled.")
