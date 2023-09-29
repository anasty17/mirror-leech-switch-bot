#!/usr/bin/env python3
from logging import getLogger, ERROR
from aiofiles.os import remove as aioremove, path as aiopath, rename as aiorename, makedirs
from os import walk, path as ospath
from time import time
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type, RetryError
from re import sub as re_sub
from natsort import natsorted
from aioshutil import copy

from bot import config_dict, GLOBAL_EXTENSION_FILTER, bot
from bot.helper.ext_utils.fs_utils import clean_unwanted, get_mime_type
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.leech_utils import get_document_type, take_ss
from bot.helper.switch_helper.button_build import ButtonMaker
from bot.helper.switch_helper.message_utils import editMessage

LOGGER = getLogger(__name__)
getLogger("swibots.app").setLevel(ERROR)


class SwUploader:

    def __init__(self, name=None, path=None, listener=None):
        self.name = name
        self.__processed_bytes = 0
        self.__listener = listener
        self.__path = path
        self.__start_time = time()
        self.__total_files = 0
        self.__is_cancelled = False
        self.__thumb = f"Thumbnails/{self.__listener.user_id}.jpg"
        self.__corrupted = 0
        self.__up_path = ''
        self.__lprefix = ''
        self.__as_doc = False
        self.__sent_msg = self.__listener.message

    async def __upload_progress(self, progress):
        if self.__is_cancelled:
            progress.client.cancel()
        self.__processed_bytes += progress.current

    async def __user_settings(self):
        self.__as_doc = self.__listener.user_dict.get(
            'as_doc', False) or (config_dict['AS_DOCUMENT'] if 'as_doc' not in self.__listener.user_dict else False)
        self.__lprefix = self.__listener.user_dict.get(
            'lprefix') or (config_dict['LEECH_FILENAME_PREFIX'] if 'lprefix' not in self.__listener.user_dict else '')
        if not await aiopath.exists(self.__thumb):
            self.__thumb = None

    async def __prepare_file(self, file_, dirpath):
        if self.__lprefix:
            description = f"{self.__lprefix} {file_}"
            self.__lprefix = re_sub('<.*?>', '', self.__lprefix)
            if self.__listener.seed and not self.__listener.newDir and not dirpath.endswith("/splited_files_mltb"):
                dirpath = f'{dirpath}/copied_mltb'
                await makedirs(dirpath, exist_ok=True)
                new_path = ospath.join(
                    dirpath, f"{self.__lprefix} {file_}")
                self.__up_path = await copy(self.__up_path, new_path)
            else:
                new_path = ospath.join(
                    dirpath, f"{self.__lprefix} {file_}")
                await aiorename(self.__up_path, new_path)
                self.__up_path = new_path
        else:
            description = f"{file_}"
        return description

    async def __msg_to_reply(self):
        if LD := config_dict['LEECH_DUMP_CHAT']:
            text = self.__listener.message.message.lstrip('/').lstrip('@')
            if '|' in LD:
                commmunity_id, group_id = LD.split('|')
                receiver_id = None
            else:
                receiver_id = int(LD)
                commmunity_id, group_id = None, None
            try:
                self.__sent_msg = await bot.send_message(text, community_id=commmunity_id, group_id=group_id, user_id=receiver_id)
            except Exception as e:
                await self.__listener.onUploadError(str(e))
                return False
        else:
            self.__sent_msg = self.__listener.message
        return True

    async def upload(self, excluded_files, size):
        await self.__user_settings()
        res = await self.__msg_to_reply()
        if not res:
            return
        if self.__listener.user_dict.get('excluded_extensions', False):
            extension_filter = self.__listener.user_dict['excluded_extensions']
        elif 'excluded_extensions' not in self.__listener.user_dict:
            extension_filter = GLOBAL_EXTENSION_FILTER
        else:
            extension_filter = ['aria2', '!qB']
        for dirpath, _, files in sorted(await sync_to_async(walk, self.__path)):
            if dirpath.endswith('/yt-dlp-thumb'):
                continue
            for file_ in natsorted(files):
                self.__up_path = ospath.join(dirpath, file_)
                if file_.lower().endswith(tuple(extension_filter)):
                    if not self.__listener.seed or self.__listener.newDir:
                        await aioremove(self.__up_path)
                    continue
                try:
                    f_size = await aiopath.getsize(self.__up_path)
                    if self.__listener.seed and file_ in excluded_files and f_size in list(excluded_files.values()):
                        continue
                    self.__total_files += 1
                    if f_size == 0:
                        LOGGER.error(
                            f"{self.__up_path} size is zero, switch don't upload zero size files")
                        self.__corrupted += 1
                        continue
                    if self.__is_cancelled:
                        return
                    description = await self.__prepare_file(file_, dirpath)
                    await self.__upload_file(description, file_)
                    if self.__is_cancelled:
                        return
                except Exception as err:
                    if isinstance(err, RetryError):
                        LOGGER.info(
                            f"Total Attempts: {err.last_attempt.attempt_number}")
                        err = err.last_attempt.exception()
                    LOGGER.error(f"{err}. Path: {self.__up_path}")
                    self.__corrupted += 1
                    if self.__is_cancelled:
                        return
                    continue
                finally:
                    if not self.__is_cancelled and await aiopath.exists(self.__up_path) and \
                          (not self.__listener.seed or self.__listener.newDir or
                           dirpath.endswith("/splited_files_mltb") or '/copied_mltb/' in self.__up_path):
                        await aioremove(self.__up_path)
                    continue
        if self.__is_cancelled:
            return
        if self.__listener.seed and not self.__listener.newDir:
            await clean_unwanted(self.__path)
        if self.__total_files == 0:
            await self.__listener.onUploadError("No files to upload. In case you have filled EXTENSION_FILTER, then check if all files have those extensions or not.")
            return
        if self.__total_files <= self.__corrupted:
            await self.__listener.onUploadError('Files Corrupted or unable to upload. Check logs!')
            return
        LOGGER.info(f"Leech Completed: {self.name}")
        await self.__listener.onUploadComplete(None, size, self.__corrupted, self.__total_files, _, self.name)

    @retry(wait=wait_exponential(multiplier=2, min=4, max=8), stop=stop_after_attempt(3),
           retry=retry_if_exception_type(Exception))
    async def __upload_file(self, description, file):
        if self.__thumb is not None and not await aiopath.exists(self.__thumb):
            self.__thumb = None
        thumb = self.__thumb
        is_video, _, is_image = await get_document_type(self.__up_path)

        if not is_image and thumb is None:
            file_name = ospath.splitext(file)[0]
            thumb_path = f"{self.__path}/yt-dlp-thumb/{file_name}.jpg"
            if await aiopath.isfile(thumb_path):
                thumb = thumb_path

        if is_video and thumb is None:
            thumb = await take_ss(self.__up_path, None)
        if self.__is_cancelled:
            return

        mime_type = await sync_to_async(get_mime_type, self.__up_path)

        self.__sent_msg = await self.__sent_msg.reply_media(document=self.__up_path,
                                                            message=description,
                                                            description=file,
                                                            mime_type=mime_type,
                                                            thumb=thumb,
                                                            progress=self.__upload_progress,
                                                            media_type=7 if self.__as_doc else None)
        buttons = ButtonMaker()
        buttons.ubutton("Direct Download Link", self.__sent_msg.media_link)
        button = buttons.build_menu()
        self.__sent_msg = await editMessage(self.__sent_msg, f"<copy>{file}</copy>\nMime Type: {mime_type}", button)
        if self.__thumb is None and thumb is not None and await aiopath.exists(thumb):
            await aioremove(thumb)

    @property
    def speed(self):
        try:
            return self.__processed_bytes / (time() - self.__start_time)
        except:
            return 0

    @property
    def processed_bytes(self):
        return self.__processed_bytes

    async def cancel_download(self):
        self.__is_cancelled = True
        LOGGER.info(f"Cancelling Upload: {self.name}")
        await self.__listener.onUploadError('your upload has been stopped!')
