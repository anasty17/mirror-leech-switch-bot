from re import match as re_match
from time import time
from asyncio import sleep

from bot import config_dict, LOGGER, status_dict, task_dict_lock, Intervals, bot, tg
from bot.helper.ext_utils.bot_utils import setInterval
from bot.helper.ext_utils.exceptions import TgLinkException
from bot.helper.ext_utils.status_utils import get_readable_message


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


async def sendFile(msg, file, description=""):
    try:
        return await msg.reply_media(description, file, description=description)
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def sendRss(text):
    RC = config_dict["RSS_CHAT"]
    if "|" in RC:
        commmunity_id, group_id = RC.split("|")
        receiver_id = None
    else:
        receiver_id = int(RC)
        commmunity_id, group_id = None, None
    try:
        return await bot.send_message(
            text, community_id=commmunity_id, group_id=group_id, user_id=receiver_id
        )
    except Exception as e:
        LOGGER.error(str(e))
        return str(e)


async def deleteMessage(message):
    try:
        await message.delete()
    except Exception as e:
        LOGGER.error(str(e))


async def auto_delete_message(cmd_message=None, bot_message=None):
    await sleep(60)
    if cmd_message is not None:
        await deleteMessage(cmd_message)
    if bot_message is not None:
        await deleteMessage(bot_message)


async def delete_status():
    async with task_dict_lock:
        for key, data in list(status_dict.items()):
            try:
                await deleteMessage(data["message"])
                del status_dict[key]
            except Exception as e:
                LOGGER.error(str(e))


async def get_tg_link_message(link):
    message = None
    links = []
    if link.startswith("https://t.me/"):
        private = False
        msg = re_match(
            r"https:\/\/t\.me\/(?:c\/)?([^\/]+)(?:\/[^\/]+)?\/([0-9-]+)", link
        )
    else:
        private = True
        msg = re_match(
            r"tg:\/\/openmessage\?user_id=([0-9]+)&message_id=([0-9-]+)", link
        )

    chat = msg[1]
    msg_id = msg[2]
    if "-" in msg_id:
        start_id, end_id = msg_id.split("-")
        msg_id = start_id = int(start_id)
        end_id = int(end_id)
        btw = end_id - start_id
        if private:
            link = link.split("&message_id=")[0]
            links.append(f"{link}&message_id={start_id}")
            for _ in range(btw):
                start_id += 1
                links.append(f"{link}&message_id={start_id}")
        else:
            link = link.rsplit("/", 1)[0]
            links.append(f"{link}/{start_id}")
            for _ in range(btw):
                start_id += 1
                links.append(f"{link}/{start_id}")
    else:
        msg_id = int(msg_id)

    if chat.isdigit():
        chat = int(chat) if private else int(f"-100{chat}")

    try:
        message = await tg.get_messages(chat_id=chat, message_ids=msg_id)
        if message.empty:
            return None
    except Exception as e:
        raise TgLinkException(f"You don't have access to this chat!. ERROR: {e}") from e

    return links or message


async def update_status_message(sid, force=False):
    async with task_dict_lock:
        if not status_dict.get(sid):
            if obj := Intervals["status"].get(sid):
                obj.cancel()
                del Intervals["status"][sid]
            return
        if not force and time() - status_dict[sid]["time"] < 3:
            return
        status_dict[sid]["time"] = time()
        page_no = status_dict[sid]["page_no"]
        status = status_dict[sid]["status"]
        is_user = status_dict[sid]["is_user"]
        page_step = status_dict[sid]["page_step"]
        text, buttons = await get_readable_message(
            sid, is_user, page_no, status, page_step
        )
        if text is None:
            del status_dict[sid]
            if obj := Intervals["status"].get(sid):
                obj.cancel()
                del Intervals["status"][sid]
            return
        if text != status_dict[sid]["message"].message:
            message = await editMessage(status_dict[sid]["message"], text, buttons)
            if isinstance(message, str):
                del status_dict[sid]
                if obj := Intervals["status"].get(sid):
                    obj.cancel()
                    del Intervals["status"][sid]
                LOGGER.error(
                    f"Status with id: {sid} haven't been updated. Error: {message}"
                )
                return
            status_dict[sid]["message"] = message
            status_dict[sid]["message"].message = text
            status_dict[sid]["time"] = time()


async def sendStatusMessage(msg, user_id=0):
    async with task_dict_lock:
        sid = msg.receiver_id or msg.group_id
        is_user = bool(user_id)
        if sid in list(status_dict.keys()):
            page_no = status_dict[sid]["page_no"]
            status = status_dict[sid]["status"]
            page_step = status_dict[sid]["page_step"]
            text, buttons = await get_readable_message(
                sid, is_user, page_no, status, page_step
            )
            if text is None:
                del status_dict[sid]
                if obj := Intervals["status"].get(sid):
                    obj.cancel()
                    del Intervals["status"][sid]
                return
            message = status_dict[sid]["message"]
            await deleteMessage(message)
            message = await sendMessage(msg, text, buttons)
            if isinstance(message, str):
                LOGGER.error(
                    f"Status with id: {sid} haven't been sent. Error: {message}"
                )
                return
            message.message = text
            status_dict[sid].update({"message": message, "time": time()})
        else:
            text, buttons = await get_readable_message(sid, is_user)
            if text is None:
                return
            message = await sendMessage(msg, text, buttons)
            if isinstance(message, str):
                LOGGER.error(
                    f"Status with id: {sid} haven't been sent. Error: {message}"
                )
                return
            message.message = text
            status_dict[sid] = {
                "message": message,
                "time": time(),
                "page_no": 1,
                "page_step": 1,
                "status": "All",
                "is_user": is_user,
            }
    if not Intervals["status"].get(sid) and not is_user:
        Intervals["status"][sid] = setInterval(
            config_dict["STATUS_UPDATE_INTERVAL"], update_status_message, sid
        )
