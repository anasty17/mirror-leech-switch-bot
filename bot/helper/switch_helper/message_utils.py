#!/usr/bin/env python3
from asyncio import sleep
from time import time

from bot import config_dict, LOGGER, status_reply_dict, status_reply_dict_lock, Interval, bot, download_dict_lock
from bot.helper.ext_utils.bot_utils import get_readable_message, setInterval, sync_to_async


async def sendMessage(message, text, buttons=None):
    try:
        return await message.reply_text(text, inline_markup=buttons)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def editMessage(message, text, buttons=None):
    try:
        return await message.edit_text(text, inline_markup=buttons)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def sendFile(msg, file, description=''):
    try:
        return await msg.reply_media(description, file, description=description)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def sendRss(text):
    RC = config_dict['RSS_CHAT']
    if '|' in RC:
        commmunity_id, group_id = RC.split('|')
        receiver_id = None
    else:
        receiver_id = int(RC)
        commmunity_id, group_id = None, None
    try:
        return await bot.send_message(text, community_id=commmunity_id, group_id=group_id, user_id=receiver_id)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def deleteMessage(message):
    try:
        await message.delete()
    except Exception as e:
        LOGGER.error(str(e))


async def auto_delete_message(cmd_message=None, bot_message=None):
    if config_dict['AUTO_DELETE_MESSAGE_DURATION'] != -1:
        await sleep(config_dict['AUTO_DELETE_MESSAGE_DURATION'])
        if cmd_message is not None:
            await deleteMessage(cmd_message)
        if bot_message is not None:
            await deleteMessage(bot_message)


async def delete_all_messages():
    async with status_reply_dict_lock:
        for key, data in list(status_reply_dict.items()):
            try:
                del status_reply_dict[key]
                await deleteMessage(data[0])
            except Exception as e:
                LOGGER.error(str(e))


async def update_all_messages(force=False):
    async with status_reply_dict_lock:
        if not status_reply_dict or not Interval or (not force and time() - list(status_reply_dict.values())[0][1] < 3):
            return
        for chat_id in list(status_reply_dict.keys()):
            status_reply_dict[chat_id][1] = time()
    async with download_dict_lock:
        msg, buttons = await sync_to_async(get_readable_message)
    if msg is None:
        return
    async with status_reply_dict_lock:
        for chat_id in list(status_reply_dict.keys()):
            if status_reply_dict[chat_id] and msg != status_reply_dict[chat_id][0].message:
                rmsg = await editMessage(status_reply_dict[chat_id][0], msg, buttons)
                if isinstance(rmsg, str):
                    del status_reply_dict[chat_id]
                    continue
                status_reply_dict[chat_id][0].message = msg
                status_reply_dict[chat_id][1] = time()


async def sendStatusMessage(msg):
    async with download_dict_lock:
        progress, buttons = await sync_to_async(get_readable_message)
    if progress is None:
        return
    async with status_reply_dict_lock:
        chat_id = msg.receiver_id or msg.group_id
        if chat_id in list(status_reply_dict.keys()):
            message = status_reply_dict[chat_id][0]
            await deleteMessage(message)
            del status_reply_dict[chat_id]
        message = await sendMessage(msg, progress, buttons)
        message.message = progress
        status_reply_dict[chat_id] = [message, time()]
        if not Interval:
            Interval.append(setInterval(
                config_dict['STATUS_UPDATE_INTERVAL'], update_all_messages))
