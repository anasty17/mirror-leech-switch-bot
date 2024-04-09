from aiofiles.os import path as aiopath, listdir, makedirs, remove
from aioshutil import move
from asyncio import sleep, gather
from html import escape
from requests import utils as rutils

from bot import (
    Intervals,
    aria2,
    DOWNLOAD_DIR,
    task_dict,
    task_dict_lock,
    LOGGER,
    config_dict,
    non_queued_up,
    non_queued_dl,
    queued_up,
    queued_dl,
    queue_dict_lock,
)
from bot.helper.common import TaskConfig
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.files_utils import (
    get_path_size,
    clean_download,
    clean_target,
    join_files,
)
from bot.helper.ext_utils.links_utils import is_gdrive_id
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.ext_utils.task_manager import start_from_queued, check_running_tasks
from bot.helper.mirror_leech_utils.gdrive_utils.upload import gdUpload
from bot.helper.mirror_leech_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.mirror_leech_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.mirror_leech_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_leech_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_leech_utils.status_utils.switch_status import SwitchStatus
from bot.helper.mirror_leech_utils.switchUploader import SwUploader
from bot.helper.switch_helper.button_build import ButtonMaker
from bot.helper.switch_helper.message_utils import (
    sendMessage,
    delete_status,
    update_status_message,
)


class TaskListener(TaskConfig):
    def __init__(self):
        super().__init__()

    async def clean(self):
        try:
            if st := Intervals["status"]:
                for intvl in list(st.values()):
                    intvl.cancel()
            Intervals["status"].clear()
            await gather(sync_to_async(aria2.purge), delete_status())
        except:
            pass

    def removeFromSameDir(self):
        if self.sameDir and self.mid in self.sameDir["tasks"]:
            self.sameDir["tasks"].remove(self.mid)
            self.sameDir["total"] -= 1

    async def onDownloadStart(self):
        pass

    async def onDownloadComplete(self):
        multi_links = False
        if self.sameDir and self.mid in self.sameDir["tasks"]:
            while not (
                self.sameDir["total"] in [1, 0]
                or self.sameDir["total"] > 1
                and len(self.sameDir["tasks"]) > 1
            ):
                await sleep(0.5)

        async with task_dict_lock:
            if (
                self.sameDir
                and self.sameDir["total"] > 1
                and self.mid in self.sameDir["tasks"]
            ):
                self.sameDir["tasks"].remove(self.mid)
                self.sameDir["total"] -= 1
                folder_name = self.sameDir["name"]
                spath = f"{self.dir}{folder_name}"
                des_path = (
                    f"{DOWNLOAD_DIR}{list(self.sameDir['tasks'])[0]}{folder_name}"
                )
                await makedirs(des_path, exist_ok=True)
                for item in await listdir(spath):
                    if item.endswith((".aria2", ".!qB")):
                        continue
                    item_path = f"{self.dir}{folder_name}/{item}"
                    if item in await listdir(des_path):
                        await move(item_path, f"{des_path}/{self.mid}-{item}")
                    else:
                        await move(item_path, f"{des_path}/{item}")
                multi_links = True
            download = task_dict[self.mid]
            self.name = download.name()
            gid = download.gid()
        LOGGER.info(f"Download completed: {self.name}")

        if not (self.isTorrent or self.isQbit):
            self.seed = False

        unwanted_files = []
        unwanted_files_size = []
        files_to_delete = []

        if multi_links:
            await self.onUploadError("Downloaded! Waiting for other tasks...")
            return

        if not await aiopath.exists(f"{self.dir}/{self.name}"):
            try:
                files = await listdir(self.dir)
                self.name = files[-1]
                if self.name == "yt-dlp-thumb":
                    self.name = files[0]
            except Exception as e:
                await self.onUploadError(str(e))
                return

        up_path = f"{self.dir}/{self.name}"
        self.size = await get_path_size(up_path)
        if not config_dict["QUEUE_ALL"]:
            async with queue_dict_lock:
                if self.mid in non_queued_dl:
                    non_queued_dl.remove(self.mid)
            await start_from_queued()

        if self.join and await aiopath.isdir(up_path):
            await join_files(up_path)

        if self.extract:
            up_path = await self.proceedExtract(up_path, gid)
            if self.isCancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.nameSub:
            up_path = await self.substitute(up_path)
            if self.isCancelled:
                return
            self.name = up_path.rsplit("/", 1)[1]

        if self.convertAudio or self.convertVideo:
            up_path = await self.convertMedia(
                up_path, gid, unwanted_files, unwanted_files_size, files_to_delete
            )
            if self.isCancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.sampleVideo:
            up_path = await self.generateSampleVideo(
                up_path, gid, unwanted_files, files_to_delete
            )
            if self.isCancelled:
                return
            up_dir, self.name = up_path.rsplit("/", 1)
            self.size = await get_path_size(up_dir)

        if self.compress:
            up_path = await self.proceedCompress(
                up_path, gid, unwanted_files, files_to_delete
            )
            if self.isCancelled:
                return

        up_dir, self.name = up_path.rsplit("/", 1)
        self.size = await get_path_size(up_dir)

        if self.isLeech and not self.compress:
            await self.proceedSplit(up_dir, unwanted_files_size, unwanted_files, gid)
            if self.isCancelled:
                return

        add_to_queue, event = await check_running_tasks(self, "up")
        await start_from_queued()
        if add_to_queue:
            LOGGER.info(f"Added to Queue/Upload: {self.name}")
            async with task_dict_lock:
                task_dict[self.mid] = QueueStatus(self, gid, "Up")
            await event.wait()
            if self.isCancelled:
                return
            async with queue_dict_lock:
                non_queued_up.add(self.mid)
            LOGGER.info(f"Start from Queued/Upload: {self.name}")

        self.size = await get_path_size(up_dir)
        for s in unwanted_files_size:
            self.size -= s

        if self.isLeech:
            LOGGER.info(f"Leech Name: {self.name}")
            sw = SwUploader(self, up_dir)
            async with task_dict_lock:
                task_dict[self.mid] = SwitchStatus(self, sw, gid, "up")
            await gather(
                update_status_message(self.chat),
                sw.upload(unwanted_files, files_to_delete),
            )
        elif is_gdrive_id(self.upDest):
            LOGGER.info(f"Gdrive Upload Name: {self.name}")
            drive = gdUpload(self, up_path)
            async with task_dict_lock:
                task_dict[self.mid] = GdriveStatus(self, drive, gid, "up")
            await gather(
                update_status_message(self.chat),
                sync_to_async(drive.upload, unwanted_files, files_to_delete),
            )
        else:
            LOGGER.info(f"Rclone Upload Name: {self.name}")
            RCTransfer = RcloneTransferHelper(self)
            async with task_dict_lock:
                task_dict[self.mid] = RcloneStatus(self, RCTransfer, gid, "up")
            await gather(
                update_status_message(self.chat),
                RCTransfer.upload(up_path, unwanted_files, files_to_delete),
            )

    async def onUploadComplete(
        self, link, files, folders, mime_type, rclonePath="", dir_id=""
    ):
        msg = f"<b>Name: </b><copy>{escape(self.name)}</copy>\n\n<b>Size: </b>{get_readable_file_size(self.size)}"
        LOGGER.info(f"Task Done: {self.name}")
        if self.isLeech:
            msg += f"\n<b>Total Files: </b>{folders}"
            if mime_type != 0:
                msg += f"\n<b>Corrupted Files: </b>{mime_type}"
            msg += f"\n<b>cc: </b>{self.tag}"
            await sendMessage(self.message, msg)
        else:
            msg += f"\n\n<b>Type: </b>{mime_type}"
            if mime_type == "Folder":
                msg += f"\n<b>SubFolders: </b>{folders}"
                msg += f"\n<b>Files: </b>{files}"
            if (
                link
                or rclonePath
                and config_dict["RCLONE_SERVE_URL"]
                and not self.privateLink
            ):
                buttons = ButtonMaker()
                if link:
                    buttons.ubutton("☁️ Cloud Link", link)
                else:
                    msg += f"\n\nPath: <copy>{rclonePath}</copy>"
                if (
                    rclonePath
                    and (RCLONE_SERVE_URL := config_dict["RCLONE_SERVE_URL"])
                    and not self.privateLink
                ):
                    remote, path = rclonePath.split(":", 1)
                    url_path = rutils.quote(f"{path}")
                    share_url = f"{RCLONE_SERVE_URL}/{remote}/{url_path}"
                    if mime_type == "Folder":
                        share_url += "/"
                    buttons.ubutton("🔗 Rclone Link", share_url)
                if not rclonePath and dir_id:
                    INDEX_URL = ""
                    if self.privateLink:
                        INDEX_URL = self.userDict.get("index_url", "") or ""
                    elif config_dict["INDEX_URL"]:
                        INDEX_URL = config_dict["INDEX_URL"]
                    if INDEX_URL:
                        share_url = f"{INDEX_URL}findpath?id={dir_id}"
                        buttons.ubutton("⚡ Index Link", share_url)
                        if mime_type.startswith(("image", "video", "audio")):
                            share_urls = f"{INDEX_URL}findpath?id={dir_id}&view=true"
                            buttons.ubutton("🌐 View Link", share_urls)
                button = buttons.build_menu(2)
            else:
                msg += f"\n\nPath: <copy>{rclonePath}</copy>"
                button = None
            msg += f"\n\n<b>cc: </b>{self.tag}"
            await sendMessage(self.message, msg, button)
        if self.seed:
            if self.newDir:
                await clean_target(self.newDir)
            async with queue_dict_lock:
                if self.mid in non_queued_up:
                    non_queued_up.remove(self.mid)
            await start_from_queued()
            return
        await clean_download(self.dir)
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.chat)

        async with queue_dict_lock:
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()

    async def onDownloadError(self, error, button=None):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
            self.removeFromSameDir()
        msg = f"{self.tag} Download: {escape(error)}"
        await sendMessage(self.message, msg, button)
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.chat)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.newDir:
            await clean_download(self.newDir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)

    async def onUploadError(self, error):
        async with task_dict_lock:
            if self.mid in task_dict:
                del task_dict[self.mid]
            count = len(task_dict)
        await sendMessage(self.message, f"{self.tag} {escape(error)}")
        if count == 0:
            await self.clean()
        else:
            await update_status_message(self.chat)

        async with queue_dict_lock:
            if self.mid in queued_dl:
                queued_dl[self.mid].set()
                del queued_dl[self.mid]
            if self.mid in queued_up:
                queued_up[self.mid].set()
                del queued_up[self.mid]
            if self.mid in non_queued_dl:
                non_queued_dl.remove(self.mid)
            if self.mid in non_queued_up:
                non_queued_up.remove(self.mid)

        await start_from_queued()
        await sleep(3)
        await clean_download(self.dir)
        if self.newDir:
            await clean_download(self.newDir)
        if self.thumb and await aiopath.exists(self.thumb):
            await remove(self.thumb)
