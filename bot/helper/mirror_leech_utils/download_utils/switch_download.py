#!/usr/bin/env python3
from time import time
from asyncio import Lock

from bot import LOGGER, task_dict, task_dict_lock, non_queued_dl, queue_dict_lock
from bot.helper.mirror_leech_utils.status_utils.switch_status import SwitchStatus
from bot.helper.mirror_leech_utils.status_utils.queue_status import QueueStatus
from bot.helper.switch_helper.message_utils import sendStatusMessage
from bot.helper.ext_utils.task_manager import check_running_tasks, stop_duplicate_check

global_lock = Lock()
GLOBAL_GID = set()


class SwitchDownloadHelper:
    def __init__(self, listener):
        self._processed_bytes = 0
        self._start_time = time()
        self._listener = listener
        self._id = ""

    @property
    def speed(self):
        return self._processed_bytes / (time() - self._start_time)

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def _onDownloadStart(self, file_id, from_queue):
        async with global_lock:
            GLOBAL_GID.add(file_id)
        self._id = file_id
        async with task_dict_lock:
            task_dict[self._listener.mid] = SwitchStatus(
                self._listener, self, file_id[:12], "dl"
            )
        if not from_queue:
            await sendStatusMessage(self._listener.message)
            LOGGER.info(f"Download from Switch: {self._listener.name}")
        else:
            LOGGER.info(f"Start Queued Download from Switch: {self._listener.name}")

    async def _onDownloadProgress(self, progress):
        if self._listener.isCancelled:
            progress.client.cancel()
        self._processed_bytes = progress.downloaded

    async def _onDownloadError(self, error):
        async with global_lock:
            try:
                GLOBAL_GID.remove(self._id)
            except:
                pass
        await self._listener.onDownloadError(error)

    async def _onDownloadComplete(self):
        await self._listener.onDownloadComplete()
        async with global_lock:
            GLOBAL_GID.remove(self._id)

    async def _download(self, message, path):
        try:
            download = await message.download(file_name=path, block=True, progress=self._onDownloadProgress)
            if self._listener.isCancelled:
                await self._onDownloadError('Cancelled by user!')
                return
        except Exception as e:
            LOGGER.error(str(e))
            await self._onDownloadError(str(e))
            return
        if download is not None:
            await self._onDownloadComplete()
        elif not self._listener.isCancelled:
            await self._onDownloadError('Internal error occurred')

    async def add_download(self, message, path):
        if message.is_media:
            media = message.media_info
            async with global_lock:
                download = media.source_id not in GLOBAL_GID

            if download:
                if not self._listener.name:
                    self._listener.name = media.description
                path = path + self._listener.name
                self._listener.size = media.file_size
                gid = media.source_id

                msg, button = await stop_duplicate_check(self._listener)
                if msg:
                    await self._listener.onDownloadError(msg, button)
                    return

                add_to_queue, event = await check_running_tasks(self._listener)
                if add_to_queue:
                    LOGGER.info(f"Added to Queue/Download: {self._listener.name}")
                    async with task_dict_lock:
                        task_dict[self._listener.mid] = QueueStatus(
                            self._listener, gid, "dl"
                        )
                    await self._listener.onDownloadStart()
                    if self._listener.multi <= 1:
                        await sendStatusMessage(self._listener.message)
                    await event.wait()
                    if self._listener.isCancelled:
                        return
                    async with queue_dict_lock:
                        non_queued_dl.add(self._listener.mid)

                await self._onDownloadStart(gid, add_to_queue)
                await self._download(message, path)
            else:
                await self._onDownloadError('File already being downloaded!')
        else:
            await self._onDownloadError('No document in the replied message!')

    async def cancel_download(self):
        self._listener.isCancelled = True
        LOGGER.info(
            f"Cancelling download on user request: name: {self._listener.name} id: {self._id}"
        )
