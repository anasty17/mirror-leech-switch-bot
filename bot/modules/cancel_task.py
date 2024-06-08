from asyncio import sleep
from swibots import CommandHandler, CallbackQueryHandler, regexp

from bot import task_dict, bot, task_dict_lock, OWNER_ID, user_data, multi_tags
from bot.helper.ext_utils.status_utils import getTaskByGid, getAllTasks, MirrorStatus
from bot.helper.switch_helper import button_build
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import (
    sendMessage,
    auto_delete_message,
    deleteMessage,
    editMessage,
)


async def cancel_task(ctx):
    message = ctx.event.message
    user_id = message.user_id
    msg = message.message.split()
    if len(msg) > 1:
        gid = msg[1]
        if len(gid) == 4:
            multi_tags.discard(gid)
            return
        else:
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
    elif len(msg) == 1:
        msg = (
            "Reply to an active Command message which was used to start the download"
            f" or send <copy>/{BotCommands.CancelTaskCommand[0]} GID</copy> to cancel it!"
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
    await obj.cancel_task()


async def cancel_multi(ctx):
    data = ctx.event.callback_data.split()
    user_id = ctx.event.action_by.id
    if user_id != int(data[1]) and not await CustomFilters.sudo(ctx):
        await ctx.event.answer("Not Yours!", show_alert=True)
        return
    tag = int(data[2])
    if tag in multi_tags:
        multi_tags.discard(int(data[2]))
        msg = "Stopped!"
    else:
        msg = "Already Stopped/Finished!"
    await ctx.event.answer(msg, show_alert=True)
    await deleteMessage(ctx.event.message)


async def cancel_all(status, userId):
    matches = await getAllTasks(status.strip(), userId)
    if not matches:
        return False
    for task in matches:
        obj = task.task()
        await obj.cancel_task()
        await sleep(2)
    return True


def create_cancel_buttons(isSudo, userId=""):
    buttons = button_build.ButtonMaker()
    buttons.ibutton(
        "Downloading", f"canall ms {MirrorStatus.STATUS_DOWNLOADING} {userId}"
    )
    buttons.ibutton("Uploading", f"canall ms {MirrorStatus.STATUS_UPLOADING} {userId}")
    buttons.ibutton("Seeding", f"canall ms {MirrorStatus.STATUS_SEEDING} {userId}")
    buttons.ibutton("Spltting", f"canall ms {MirrorStatus.STATUS_SPLITTING} {userId}")
    buttons.ibutton("Cloning", f"canall ms {MirrorStatus.STATUS_CLONING} {userId}")
    buttons.ibutton(
        "Extracting", f"canall ms {MirrorStatus.STATUS_EXTRACTING} {userId}"
    )
    buttons.ibutton("Archiving", f"canall ms {MirrorStatus.STATUS_ARCHIVING} {userId}")
    buttons.ibutton("QueuedDl", f"canall ms {MirrorStatus.STATUS_QUEUEDL} {userId}")
    buttons.ibutton("QueuedUp", f"canall ms {MirrorStatus.STATUS_QUEUEUP} {userId}")
    buttons.ibutton("SampleVideo", f"canall ms {MirrorStatus.STATUS_SAMVID} {userId}")
    buttons.ibutton(
        "ConvertMedia", f"canall ms {MirrorStatus.STATUS_CONVERTING} {userId}"
    )
    buttons.ibutton("Paused", f"canall ms {MirrorStatus.STATUS_PAUSED} {userId}")
    buttons.ibutton("All", f"canall ms All {userId}")
    if isSudo:
        if userId:
            buttons.ibutton("All Added Tasks", f"canall bot ms {userId}")
        else:
            buttons.ibutton("My Tasks", f"canall user ms {userId}")
    buttons.ibutton("Close", f"canall close ms {userId}")
    return buttons.build_menu(2)


async def cancell_all_buttons(ctx):
    message = ctx.event.message
    async with task_dict_lock:
        count = len(task_dict)
    if count == 0:
        await sendMessage(message, "No active tasks!")
        return
    isSudo = await CustomFilters.sudo(ctx)
    button = create_cancel_buttons(isSudo, message.user_id)
    can_msg = await sendMessage(message, "Choose tasks to cancel!", button)
    await auto_delete_message(message, can_msg)


async def cancel_all_update(ctx):
    data = ctx.event.callback_data.split()
    message = ctx.event.message
    reply_to = message.replied_to
    userId = int(data[3]) if len(data) > 3 else ""
    isSudo = await CustomFilters.sudo(ctx)
    if not isSudo and userId and userId != ctx.event.action_by.id:
        await ctx.event.answer("Not Yours!", show_alert=True)
    if data[1] == "close":
        await deleteMessage(reply_to)
        await deleteMessage(message)
    elif data[1] == "back":
        button = create_cancel_buttons(isSudo, userId)
        await editMessage(message, "Choose tasks to cancel!", button)
    elif data[1] == "bot":
        button = create_cancel_buttons(isSudo, "")
        await editMessage(message, "Choose tasks to cancel!", button)
    elif data[1] == "user":
        button = create_cancel_buttons(isSudo, ctx.event.action_by.id)
        await editMessage(message, "Choose tasks to cancel!", button)
    elif data[1] == "ms":
        buttons = button_build.ButtonMaker()
        buttons.ibutton("Yes!", f"canall {data[2]} confirm {userId}")
        buttons.ibutton("Back", f"canall back confirm {userId}")
        buttons.ibutton("Close", f"canall close confirm {userId}")
        button = buttons.build_menu(2)
        await editMessage(
            message, f"Are you sure you want to cancel all {data[2]} tasks", button
        )
    else:
        button = create_cancel_buttons(isSudo, userId)
        await editMessage(message, "Choose tasks to cancel.", button)
        res = await cancel_all(data[1], userId)
        if not res:
            await sendMessage(reply_to, f"No matching tasks for {data[1]}!")


bot.add_handler(
    CommandHandler(
        BotCommands.CancelTaskCommand, cancel_task, filter=CustomFilters.authorized
    )
)
bot.add_handler(
    CommandHandler(
        BotCommands.CancelAllCommand, cancell_all_buttons, filter=CustomFilters.sudo
    )
)
bot.add_handler(CallbackQueryHandler(cancel_all_update, filter=regexp("^canall")))
bot.add_handler(CallbackQueryHandler(cancel_multi, filter=regexp("^stopm")))
