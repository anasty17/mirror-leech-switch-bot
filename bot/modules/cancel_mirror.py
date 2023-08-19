#!/usr/bin/env python3
from asyncio import sleep
from swibots import CommandHandler, CallbackQueryHandler, regexp

from bot import download_dict, bot, download_dict_lock, OWNER_ID, user_data
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendMessage, auto_delete_message, deleteMessage
from bot.helper.ext_utils.bot_utils import getDownloadByGid, getAllDownload, MirrorStatus
from bot.helper.switch_helper import button_build


async def cancel_mirror(ctx):
    message = ctx.event.message
    user_id = message.user_id
    msg = message.message.split()
    if len(msg) > 1:
        gid = msg[1]
        dl = await getDownloadByGid(gid)
        if dl is None:
            await sendMessage(message, f"GID: <copy>{gid}</copy> Not Found.")
            return
    elif reply_to_id := message.replied_to_id:
        async with download_dict_lock:
            dl = download_dict.get(reply_to_id, None)
        if dl is None:
            await sendMessage(message, "This is not an active task!")
            return
    elif len(msg) == 1:
        msg = "Reply to an active Command message which was used to start the download" \
              f" or send <copy>/{BotCommands.CancelMirror} GID</copy> to cancel it!"
        await sendMessage(message, msg)
        return
    if OWNER_ID != user_id and dl.message.user_id != user_id and \
       (user_id not in user_data or not user_data[user_id].get('is_sudo')):
        await sendMessage(message, "This task is not for you!")
        return
    obj = dl.download()
    await obj.cancel_download()


async def cancel_all(status):
    matches = await getAllDownload(status)
    if not matches:
        return False
    for dl in matches:
        obj = dl.download()
        await obj.cancel_download()
        await sleep(1)
    return True


async def cancell_all_buttons(ctx):
    message = ctx.event.message
    async with download_dict_lock:
        count = len(download_dict)
    if count == 0:
        await sendMessage(message, "No active tasks!")
        return
    buttons = button_build.ButtonMaker()
    buttons.ibutton("Downloading", f"canall {MirrorStatus.STATUS_DOWNLOADING}")
    buttons.ibutton("Uploading", f"canall {MirrorStatus.STATUS_UPLOADING}")
    buttons.ibutton("Seeding", f"canall {MirrorStatus.STATUS_SEEDING}")
    buttons.ibutton("Cloning", f"canall {MirrorStatus.STATUS_CLONING}")
    buttons.ibutton("Extracting", f"canall {MirrorStatus.STATUS_EXTRACTING}")
    buttons.ibutton("Archiving", f"canall {MirrorStatus.STATUS_ARCHIVING}")
    buttons.ibutton("QueuedDl", f"canall {MirrorStatus.STATUS_QUEUEDL}")
    buttons.ibutton("QueuedUp", f"canall {MirrorStatus.STATUS_QUEUEUP}")
    buttons.ibutton("Paused", f"canall {MirrorStatus.STATUS_PAUSED}")
    buttons.ibutton("All", "canall all")
    buttons.ibutton("Close", "canall close")
    button = buttons.build_menu(2)
    can_msg = await sendMessage(message, 'Choose tasks to cancel.', button)
    await auto_delete_message(message, can_msg)


async def cancel_all_update(ctx):
    data = ctx.event.callback_data.split()
    message = ctx.event.message
    reply_to = message.replied_to
    if data[1] == 'close':
        await deleteMessage(reply_to)
        await deleteMessage(message)
    else:
        res = await cancel_all(data[1])
        if not res:
            await sendMessage(reply_to, f"No matching tasks for {data[1]}!")


bot.add_handler(CommandHandler(BotCommands.CancelMirror,
                cancel_mirror, filter=CustomFilters.authorized))
bot.add_handler(CommandHandler(BotCommands.CancelAllCommand,
                cancell_all_buttons, filter=CustomFilters.sudo))
bot.add_handler(CallbackQueryHandler(cancel_all_update,
                filter=regexp("^canall") & CustomFilters.sudo))
