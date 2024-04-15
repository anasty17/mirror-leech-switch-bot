from logging import getLogger
from aiofiles.os import (
    remove,
    path as aiopath,
    rename,
    makedirs,
)
from os import walk, path as ospath
from time import time
from tenacity import (
    retry,
    wait_exponential,
    stop_after_attempt,
    retry_if_exception_type,
    RetryError,
)
from re import sub as re_sub
from natsort import natsorted
from aioshutil import copy

from bot import config_dict, bot
from bot.helper.ext_utils.files_utils import clean_unwanted, get_mime_type
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.media_utils import (
    get_document_type,
    get_audio_thumb,
    create_thumbnail,
)
from bot.helper.switch_helper.button_build import ButtonMaker
from bot.helper.switch_helper.message_utils import editMessage

LOGGER = getLogger(__name__)


class SwUploader:
    def __init__(self, listener, path):
        self._processed_bytes = 0
        self._listener = listener
        self._path = path
        self._start_time = time()
        self._total_files = 0
        self._thumb = f"Thumbnails/{self._listener.userId}.jpg"
        self._corrupted = 0
        self._up_path = ""
        self._lprefix = ""
        self._sent_msg = None

    async def _upload_progress(self, progress):
        if self._listener.isCancelled:
            progress.client.cancel()
        self._processed_bytes += progress.current

    async def _user_settings(self):
        self._lprefix = self._listener.userDict.get("lprefix") or (
            config_dict["LEECH_FILENAME_PREFIX"]
            if "lprefix" not in self._listener.userDict
            else ""
        )

        if not await aiopath.exists(self._thumb):
            self._thumb = None

    async def _prepare_file(self, file_, dirpath, delete_file):
        if self._lprefix:
            description = f"{self._lprefix} <copy>{file_}</copy>"
            self._lprefix = re_sub("<.*?>", "", self._lprefix)
            if (
                self._listener.seed
                and not self._listener.newDir
                and not dirpath.endswith("/splited_files_mltb")
                and not delete_file
            ):
                dirpath = f"{dirpath}/copied_mltb"
                await makedirs(dirpath, exist_ok=True)
                new_path = ospath.join(dirpath, f"{self._lprefix} {file_}")
                self._up_path = await copy(self._up_path, new_path)
            else:
                new_path = ospath.join(dirpath, f"{self._lprefix} {file_}")
                await rename(self._up_path, new_path)
                self._up_path = new_path
        else:
            description = f"{file_}"
        return description

    async def _msg_to_reply(self):
        if self._listener.upDest:
            text = self._listener.message.message.lstrip("/").lstrip("@")
            if not isinstance(self._listener.upDest, int) and "|" in self._listener.upDest:
                commmunity_id, group_id = self._listener.upDest.split("|")
                receiver_id = None
            else:
                receiver_id = (
                    self._listener.upDest
                    if isinstance(self._listener.upDest, int)
                    else int(self._listener.upDest)
                )
                commmunity_id, group_id = None, None
            try:
                self._sent_msg = await bot.send_message(
                    text,
                    community_id=commmunity_id,
                    group_id=group_id,
                    user_id=receiver_id,
                )
            except Exception as e:
                await self._listener.onUploadError(str(e))
                return False
        else:
            self._sent_msg = self._listener.message
        return True

    async def upload(self, o_files, ft_delete):
        await self._user_settings()
        res = await self._msg_to_reply()
        if not res:
            return
        for dirpath, _, files in natsorted(await sync_to_async(walk, self._path)):
            if dirpath.endswith("/yt-dlp-thumb"):
                continue
            for file_ in natsorted(files):
                delete_file = False
                self._up_path = ospath.join(dirpath, file_)
                if self._up_path in ft_delete:
                    delete_file = True
                if self._up_path in o_files:
                    continue
                if file_.lower().endswith(tuple(self._listener.extensionFilter)):
                    if not self._listener.seed or self._listener.newDir:
                        await remove(self._up_path)
                    continue
                try:
                    self._total_files += 1
                    if self._listener.isCancelled:
                        return
                    description = await self._prepare_file(file_, dirpath, delete_file)
                    await self._upload_file(description, file_)
                    if self._listener.isCancelled:
                        return
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info(
                            f"Total Attempts: {err.last_attempt.attempt_number}"
                        )
                        err = err.last_attempt.exception()
                    LOGGER.error(f"{err}. Path: {self._up_path}")
                    self._corrupted += 1
                    if self._listener.isCancelled:
                        return
                    continue
                finally:
                    if (
                        not self._listener.isCancelled
                        and await aiopath.exists(self._up_path)
                        and (
                            not self._listener.seed
                            or self._listener.newDir
                            or dirpath.endswith("/splited_files_mltb")
                            or "/copied_mltb/" in self._up_path
                        )
                    ):
                        await remove(self._up_path)
                    continue
        if self._listener.isCancelled:
            return
        if self._listener.seed and not self._listener.newDir:
            await clean_unwanted(self._path)
        if self._total_files == 0:
            await self._listener.onUploadError(
                "No files to upload. In case you have filled EXTENSION_FILTER, then check if all files have those extensions or not."
            )
            return
        if self._total_files <= self._corrupted:
            await self._listener.onUploadError(
                "Files Corrupted or unable to upload. Check logs!"
            )
            return
        LOGGER.info(f"Leech Completed: {self._listener.name}")
        await self._listener.onUploadComplete(
            None, None, self._total_files, self._corrupted
        )

    @retry(
        wait=wait_exponential(multiplier=2, min=4, max=8),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type(Exception),
    )
    async def _upload_file(self, description, file):
        if self._thumb is not None and not await aiopath.exists(self._thumb):
            self._thumb = None
        thumb = self._thumb
        is_video, is_audio, is_image = await get_document_type(self._up_path)

        if not is_image and thumb is None:
            file_name = ospath.splitext(file)[0]
            thumb_path = f"{self._path}/yt-dlp-thumb/{file_name}.jpg"
            if await aiopath.isfile(thumb_path):
                thumb = thumb_path
            elif is_audio and not is_video:
                thumb = await get_audio_thumb(self._up_path)

        if is_video and thumb is None:
            thumb = await create_thumbnail(self._up_path, None)
        if self._listener.isCancelled:
            return

        mime_type = await sync_to_async(get_mime_type, self._up_path)

        self._sent_msg = await self._sent_msg.reply_media(
            document=self._up_path,
            message=description,
            description=file,
            mime_type=mime_type,
            thumb=thumb,
            progress=self._upload_progress,
            part_size=50 * 1024 * 1024,
            task_count=10,
            media_type=7 if self._listener.asDoc else None,
        )
        buttons = ButtonMaker()
        buttons.ubutton("Direct Download Link", self._sent_msg.media_link)
        button = buttons.build_menu()
        self._sent_msg = await editMessage(
            self._sent_msg, f"<copy>{file}</copy>\nMime Type: {mime_type}", button
        )
        if self._thumb is None and thumb is not None and await aiopath.exists(thumb):
            await remove(thumb)

    @property
    def speed(self):
        try:
            return self._processed_bytes / (time() - self._start_time)
        except:
            return 0

    @property
    def processed_bytes(self):
        return self._processed_bytes

    async def cancel_task(self):
        self._listener.isCancelled = True
        LOGGER.info(f"Cancelling Upload: {self._listener.name}")
        await self._listener.onUploadError("your upload has been stopped!")
