from swibots import CommandHandler

from bot import (
    task_dict,
    bot,
    task_dict_lock,
    OWNER_ID,
    user_data,
    queued_up,
    queued_dl,
    queue_dict_lock,
)
from bot.helper.ext_utils.status_utils import getTaskByGid
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendMessage
from bot.helper.ext_utils.task_manager import start_dl_from_queued, start_up_from_queued


async def remove_from_queue(ctx):
    message = ctx.event.message
    user_id = message.user_id
    msg = message.message.split()
    status = msg[1] if len(msg) > 1 and msg[1] in ["fd", "fu"] else ""
    if status and len(msg) > 2 or not status and len(msg) > 1:
        gid = msg[2] if status else msg[1]
        task = await getTaskByGid(gid)
        if task is None:
            await sendMessage(message, f"GID: <copy>{gid}</copy> Not Found.")
            return
    elif reply_to_id := message.replied_to_id:
        async with task_dict_lock:
            task = task_dict.get(reply_to_id)
        if task is None:
            await sendMessage(message, "This is not an active task!")
            return
    elif len(msg) in {1, 2}:
        msg = (
            "Reply to an active Command message which was used to start the download"
            f" or send <copy>/{BotCommands.ForceStartCommand[0]} GID</copy> to force start download and upload! Add you can use /cmd <b>fd</b> to force downlaod only or /cmd <b>fu</b> to force upload only!"
        )
        await sendMessage(message, msg)
        return
    if (
        OWNER_ID != user_id
        and task.listener.userId != user_id
        and (user_id not in user_data or not user_data[user_id].get("is_sudo"))
    ):
        await sendMessage(message, "This task is not for you!")
        return
    obj = task.task()
    listener = obj.listener
    msg = ""
    async with queue_dict_lock:
        if status == "fu":
            listener.forceUpload = True
            if listener.mid in queued_up:
                await start_up_from_queued(listener.mid)
                msg = "Task have been force started to upload!"
        elif status == "fd":
            listener.forceDownload = True
            if listener.mid in queued_dl:
                await start_dl_from_queued(listener.mid)
                msg = "Task have been force started to download only!"
        else:
            listener.forceDownload = True
            listener.forceUpload = True
            if listener.mid in queued_up:
                await start_up_from_queued(listener.mid)
                msg = "Task have been force started to upload!"
            elif listener.mid in queued_dl:
                await start_dl_from_queued(listener.mid)
                msg = "Task have been force started to download and upload will start once download finish!"
    if msg:
        await sendMessage(message, msg)


bot.add_handler(
    CommandHandler(
        BotCommands.ForceStartCommand,
        remove_from_queue,
        filter=CustomFilters.authorized,
    )
)
