import asyncio
import uuid
from collections import defaultdict
from typing import Optional

from app.bot import bot
from app.logger import logger
from app.models import DownloadTask
from app.utils.progress import ProgressTracker


class QueueManager:
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.user_queues: dict[int, asyncio.Queue] = defaultdict(asyncio.Queue)
        self.processing: dict[int, bool] = defaultdict(bool)
        self.results: dict[str, asyncio.Future] = {}
        self._trackers: dict[str, ProgressTracker] = {}

    async def add_task(self, task: DownloadTask, tracker: Optional[ProgressTracker] = None) -> str:
        task_id = str(uuid.uuid4())
        future = asyncio.get_event_loop().create_future()
        self.results[task_id] = future
        if tracker:
            self._trackers[task_id] = tracker
        await self.user_queues[task.user_id].put((task, task_id))
        queue_size = self.user_queues[task.user_id].qsize()

        if not self.processing[task.user_id]:
            self.processing[task.user_id] = True
            asyncio.create_task(self._process_user_queue(task.user_id))

        logger.info(
            f"Task {task_id[:8]} queued for user {task.user_id}: "
            f"{task.url[:60]} (queue: {queue_size})"
        )
        return task_id

    async def wait_for_result(self, task_id: str, timeout: int = 600) -> Optional[dict]:
        future = self.results.get(task_id)
        if not future:
            return None
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Task {task_id[:8]} timed out")
            self.results.pop(task_id, None)
            return None
        except Exception as e:
            logger.error(f"Task {task_id[:8]} failed: {e}")
            self.results.pop(task_id, None)
            return None

    async def _process_user_queue(self, user_id: int):
        try:
            while not self.user_queues[user_id].empty():
                task, task_id = await self.user_queues[user_id].get()

                async with self.semaphore:
                    result = await self._execute_task(task, task_id)

                future = self.results.pop(task_id, None)
                if future and not future.done():
                    future.set_result(result)

                self.user_queues[user_id].task_done()
        except Exception as e:
            logger.error(f"Queue processing error for user {user_id}: {e}")
        finally:
            self.processing[user_id] = False

    async def _execute_task(self, task: DownloadTask, task_id: str) -> Optional[dict]:
        from app.services.downloader import downloader

        tracker = self._trackers.pop(task_id, None)
        refresh_task = None

        if not tracker and task.chat_id and task.message_id:
            quality_label = ""
            if task.format == "video":
                from app.models import VIDEO_QUALITIES
                quality_label = f"Video - {VIDEO_QUALITIES.get(task.resolution, task.resolution)}"
            else:
                from app.models import AUDIO_BITRATES
                quality_label = f"Audio - {AUDIO_BITRATES.get(task.audio_bitrate, task.audio_bitrate)} kbps"

            tracker = ProgressTracker(
                bot=bot,
                chat_id=task.chat_id,
                message_id=task.message_id,
                quality_label=quality_label,
            )

        if tracker:
            tracker.set_stage("detecting")
            await tracker.refresh(force=True)
            refresh_task = asyncio.create_task(self._periodic_refresh(tracker, task))

        for attempt in range(task.max_retries):
            try:
                result = await downloader.download(
                    url=task.url,
                    quality=task.quality,
                    fmt=task.format,
                    resolution=getattr(task, 'resolution', 'best'),
                    audio_bitrate=getattr(task, 'audio_bitrate', '192'),
                    tracker=tracker,
                )
                if result:
                    return result
            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1}/{task.max_retries} failed "
                    f"for user {task.user_id}: {e}"
                )
                task.retry_count += 1
                if tracker:
                    tracker.set_stage("error", str(e))
                    await tracker.refresh(force=True)
                if attempt < task.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        else:
            if refresh_task:
                refresh_task.cancel()
            if tracker:
                tracker.set_stage("error")
                await tracker.refresh(force=True)

        logger.error(f"All {task.max_retries} attempts failed for {task.url[:60]}")
        return None

    async def _periodic_refresh(self, tracker: ProgressTracker, task: DownloadTask):
        try:
            while True:
                await asyncio.sleep(1.5)
                if tracker.stage in ("done", "error"):
                    break
                await tracker.refresh()
        except asyncio.CancelledError:
            pass

    def get_tracker(self, task_id: str) -> Optional[ProgressTracker]:
        return self._trackers.get(task_id)

    def get_queue_size(self, user_id: int) -> int:
        return self.user_queues[user_id].qsize()

    def get_total_pending(self) -> int:
        return sum(q.qsize() for q in self.user_queues.values())

    async def cancel_user_downloads(self, user_id: int):
        queue = self.user_queues[user_id]
        while not queue.empty():
            try:
                _, task_id = queue.get_nowait()
                future = self.results.pop(task_id, None)
                if future and not future.done():
                    future.cancel()
                queue.task_done()
            except asyncio.QueueEmpty:
                break
        logger.info(f"Cancelled all downloads for user {user_id}")


queue_manager = QueueManager()
