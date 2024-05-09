from aiofiles.os import remove, path as aiopath, makedirs
from asyncio import sleep
from functools import partial
from html import escape
from io import BytesIO
from os import getcwd
from time import time
from swibots import (
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    regexp,
    filters,
)

from bot import (
    bot,
    user_data,
    config_dict,
    DATABASE_URL,
    MAX_SPLIT_SIZE,
    GLOBAL_EXTENSION_FILTER,
)
from bot.helper.ext_utils.bot_utils import update_user_ldata, getSizeBytes
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.media_utils import createThumb
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.button_build import ButtonMaker
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import (
    sendMessage,
    editMessage,
    sendFile,
    deleteMessage,
)

handler_dict = {}


async def get_user_settings(user):
    user_id = user.id
    name = user.username
    buttons = ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    user_dict = user_data.get(user_id, {})

    if (
        user_dict.get("as_doc", False)
        or "as_doc" not in user_dict
        and config_dict["AS_DOCUMENT"]
    ):
        ltype = "DOCUMENT"
    else:
        ltype = "MEDIA"

    thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"

    if user_dict.get("split_size", False):
        split_size = user_dict["split_size"]
    else:
        split_size = config_dict["LEECH_SPLIT_SIZE"]

    if (
        user_dict.get("equal_splits", False)
        or "equal_splits" not in user_dict
        and config_dict["EQUAL_SPLITS"]
    ):
        equal_splits = "Enabled"
    else:
        equal_splits = "Disabled"

    if user_dict.get("lprefix", False):
        lprefix = user_dict["lprefix"]
    elif "lprefix" not in user_dict and (LP := config_dict["LEECH_FILENAME_PREFIX"]):
        lprefix = LP
    else:
        lprefix = "None"

    if user_dict.get("leech_dest", False):
        leech_dest = user_dict["leech_dest"]
    elif "leech_dest" not in user_dict and (LD := config_dict["LEECH_DUMP_CHAT"]):
        leech_dest = LD
    else:
        leech_dest = "None"

    buttons.ibutton("Leech", f"userset {user_id} leech")

    buttons.ibutton("Rclone", f"userset {user_id} rclone")
    rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
    if user_dict.get("rclone_path", False):
        rccpath = user_dict["rclone_path"]
    elif RP := config_dict["RCLONE_PATH"]:
        rccpath = RP
    else:
        rccpath = "None"

    buttons.ibutton("Gdrive Tools", f"userset {user_id} gdrive")
    tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
    if user_dict.get("gdrive_id", False):
        gdrive_id = user_dict["gdrive_id"]
    elif GI := config_dict["GDRIVE_ID"]:
        gdrive_id = GI
    else:
        gdrive_id = "None"
    index = user_dict["index_url"] if user_dict.get("index_url", False) else "None"
    if (
        user_dict.get("stop_duplicate", False)
        or "stop_duplicate" not in user_dict
        and config_dict["STOP_DUPLICATE"]
    ):
        sd_msg = "Enabled"
    else:
        sd_msg = "Disabled"

    upload_paths = "Added" if user_dict.get("upload_paths", False) else "None"
    buttons.ibutton("Upload Paths", f"userset {user_id} upload_paths")

    default_upload = (
        user_dict.get("default_upload", "") or config_dict["DEFAULT_UPLOAD"]
    )
    du = "Gdrive API" if default_upload == "gd" else "Rclone"
    dub = "Gdrive API" if default_upload != "gd" else "Rclone"
    buttons.ibutton(f"Upload using {dub}", f"userset {user_id} {default_upload}")

    buttons.ibutton("Excluded Extensions", f"userset {user_id} ex_ex")
    if user_dict.get("excluded_extensions", False):
        ex_ex = user_dict["excluded_extensions"]
    elif "excluded_extensions" not in user_dict and GLOBAL_EXTENSION_FILTER:
        ex_ex = GLOBAL_EXTENSION_FILTER
    else:
        ex_ex = "None"

    ns_msg = "Added" if user_dict.get("name_sub", False) else "None"
    buttons.ibutton("Name Subtitute", f"userset {user_id} name_subtitute")

    buttons.ibutton("YT-DLP Options", f"userset {user_id} yto")
    if user_dict.get("yt_opt", False):
        ytopt = user_dict["yt_opt"]
    elif "yt_opt" not in user_dict and (YTO := config_dict["YT_DLP_OPTIONS"]):
        ytopt = YTO
    else:
        ytopt = "None"

    if user_dict:
        buttons.ibutton("Reset All", f"userset {user_id} reset")

    buttons.ibutton("Close", f"userset {user_id} close")

    text = f"""<u>Settings for {name}</u>
Leech Type is <b>{ltype}</b>
Custom Thumbnail <b>{thumbmsg}</b>
Leech Split Size is <b>{split_size}</b>
Equal Splits is <b>{equal_splits}</b>
Leech Prefix is <copy>{escape(lprefix)}</copy>
Leech Destination is <copy>{leech_dest}</copy>
Rclone Config <b>{rccmsg}</b>
Rclone Path is <copy>{rccpath}</copy>
Gdrive Token <b>{tokenmsg}</b>
Upload Paths is <b>{upload_paths}</b>
Gdrive ID is <copy>{gdrive_id}</copy>
Index Link is <copy>{index}</copy>
Stop Duplicate is <b>{sd_msg}</b>
Default Upload is <b>{du}</b>
Name substitution is <b>{ns_msg}</b>
Excluded Extensions is <copy>{ex_ex}</copy>
YT-DLP Options is <b><copy>{escape(ytopt)}</copy></b>"""

    return text, buttons.build_menu(1)


async def update_user_settings(ctx):
    msg, button = await get_user_settings(ctx.event.action_by)
    await editMessage(ctx.event.message, msg, button)


async def user_settings(ctx):
    message = ctx.event.message
    user = message.user
    handler_dict[user.id] = False
    msg, button = await get_user_settings(user)
    await sendMessage(message, msg, button)


async def set_thumb(ctx, pre_event):
    message = ctx.event.message
    user_id = message.user_id
    handler_dict[user_id] = False
    des_dir = await createThumb(message, user_id)
    update_user_ldata(user_id, "thumb", des_dir)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "thumb", des_dir)


async def add_rclone(ctx, pre_event):
    message = ctx.event.message
    user_id = message.user_id
    handler_dict[user_id] = False
    rpath = f"{getcwd()}/rclone/"
    await makedirs(rpath, exist_ok=True)
    des_dir = f"{rpath}{user_id}.conf"
    await message.download(file_name=des_dir)
    update_user_ldata(user_id, "rclone_config", f"rclone/{user_id}.conf")
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "rclone_config", des_dir)


async def add_token_pickle(ctx, pre_event):
    message = ctx.event.message
    user_id = message.user_id
    handler_dict[user_id] = False
    tpath = f"{getcwd()}/tokens/"
    await makedirs(tpath, exist_ok=True)
    des_dir = f"{tpath}{user_id}.pickle"
    await message.download(file_name=des_dir)
    update_user_ldata(user_id, "token_pickle", f"tokens/{user_id}.pickle")
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "token_pickle", des_dir)


async def delete_path(ctx, pre_event):
    message = ctx.event.message
    user_id = message.user_id
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    names = message.message.split()
    for name in names:
        if name in user_dict["upload_paths"]:
            del user_dict["upload_paths"][name]
    new_value = user_dict["upload_paths"]
    update_user_ldata(user_id, "upload_paths", new_value)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "upload_paths", new_value)


async def set_option(ctx, pre_event, option):
    message = ctx.event.message
    user_id = message.user_id
    handler_dict[user_id] = False
    value = message.message
    if option == "split_size":
        if not value.isdigit():
            value = getSizeBytes(value)
        value = min(int(value), MAX_SPLIT_SIZE)
    elif option == "excluded_extensions":
        fx = value.split()
        value = ["aria2", "!qB"]
        for x in fx:
            x = x.lstrip(".")
            value.append(x.strip().lower())
    elif option == "upload_paths":
        user_dict = user_data.get(user_id, {})
        user_dict.setdefault("upload_paths", {})
        lines = value.split("/n")
        for line in lines:
            data = line.split(maxsplit=1)
            if len(data) != 2:
                await sendMessage(message, "Wrong format! Add <name> <path>")
                await update_user_settings(pre_event)
                return
            name, path = data
            user_dict["upload_paths"][name] = path
        value = user_dict["upload_paths"]
    update_user_ldata(user_id, option, value)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_data(user_id)


async def event_handler(ctx, pfunc, document=False, photo=False):
    message = ctx.event.message
    user_id = ctx.event.action_by_id
    chat_id = message.group_id or message.receiver_id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, rctx):
        rmsg = rctx.event.message
        if rmsg.media_info:
            if photo:
                mtype = rmsg.media_info.media_type == 1
            elif document:
                mtype = rmsg.media_info.media_type == 7
            else:
                mtype = False
        else:
            mtype = rmsg.message
        rchat_id = rmsg.group_id or rmsg.user_id
        return bool(
            not rmsg.user.is_bot
            and rmsg.user_id == user_id
            and rchat_id == chat_id
            and mtype
        )

    handler = MessageHandler(pfunc, filter=filters.create(event_filter))
    ctx.app.add_handler(handler)
    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await update_user_settings(ctx)
    ctx.app.remove_handler(handler)


async def edit_user_settings(ctx):
    user = ctx.event.action_by
    user_id = user.id
    name = user.username
    message = ctx.event.message
    data = ctx.event.callback_data.split()
    handler_dict[user_id] = False
    thumb_path = f"Thumbnails/{user_id}.jpg"
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    user_dict = user_data.get(user_id, {})
    if user_id != int(data[1]):
        await ctx.event.answer("Not Yours!", show_alert=True)
    elif data[2] in [
        "as_doc",
        "equal_splits",
        "stop_duplicate",
    ]:
        update_user_ldata(user_id, data[2], data[3] == "true")
        await update_user_settings(ctx)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] in ["thumb", "rclone_config", "token_pickle"]:
        if data[2] == "thumb":
            fpath = thumb_path
        elif data[2] == "rclone_config":
            fpath = rclone_conf
        else:
            fpath = token_pickle
        if await aiopath.exists(fpath):
            await remove(fpath)
            update_user_ldata(user_id, data[2], "")
            await update_user_settings(ctx)
            if DATABASE_URL:
                await DbManager().update_user_doc(user_id, data[2])
        else:
            await ctx.event.answer("Old Settings", show_alert=True)
            await update_user_settings(ctx)
    elif data[2] in [
        "yt_opt",
        "lprefix",
        "index_url",
        "excluded_extensions",
        "name_sub",
    ]:
        update_user_ldata(user_id, data[2], "")
        await update_user_settings(ctx)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] in ["split_size", "leech_dest", "rclone_path", "gdrive_id"]:
        if data[2] in user_data.get(user_id, {}):
            del user_data[user_id][data[2]]
            await update_user_settings(ctx)
            if DATABASE_URL:
                await DbManager().update_user_data(user_id)
    elif data[2] == "leech":
        thumbpath = f"Thumbnails/{user_id}.jpg"
        buttons = ButtonMaker()
        buttons.ibutton("Thumbnail", f"userset {user_id} sthumb")
        thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"
        buttons.ibutton("Leech Split Size", f"userset {user_id} lss")
        if user_dict.get("split_size", False):
            split_size = user_dict["split_size"]
        else:
            split_size = config_dict["LEECH_SPLIT_SIZE"]
        buttons.ibutton("Leech Destination", f"userset {user_id} ldest")
        if user_dict.get("leech_dest", False):
            leech_dest = user_dict["leech_dest"]
        elif "leech_dest" not in user_dict and (LD := config_dict["LEECH_DUMP_CHAT"]):
            leech_dest = LD
        else:
            leech_dest = "None"
        buttons.ibutton("Leech Prefix", f"userset {user_id} leech_prefix")
        if user_dict.get("lprefix", False):
            lprefix = user_dict["lprefix"]
        elif "lprefix" not in user_dict and (
            LP := config_dict["LEECH_FILENAME_PREFIX"]
        ):
            lprefix = LP
        else:
            lprefix = "None"
        if (
            user_dict.get("as_doc", False)
            or "as_doc" not in user_dict
            and config_dict["AS_DOCUMENT"]
        ):
            ltype = "DOCUMENT"
            buttons.ibutton("Send As Media", f"userset {user_id} as_doc false")
        else:
            ltype = "MEDIA"
            buttons.ibutton("Send As Document", f"userset {user_id} as_doc true")
        if (
            user_dict.get("equal_splits", False)
            or "equal_splits" not in user_dict
            and config_dict["EQUAL_SPLITS"]
        ):
            buttons.ibutton(
                "Disable Equal Splits", f"userset {user_id} equal_splits false"
            )
            equal_splits = "Enabled"
        else:
            buttons.ibutton(
                "Enable Equal Splits", f"userset {user_id} equal_splits true"
            )
            equal_splits = "Disabled"

        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        text = f"""<u>Leech Settings for {name}</u>
Leech Type is <b>{ltype}</b>
Custom Thumbnail <b>{thumbmsg}</b>
Leech Split Size is <b>{split_size}</b>
Equal Splits is <b>{equal_splits}</b>
Leech Prefix is <copy>{escape(lprefix)}</copy>
Leech Destination is <copy>{leech_dest}</copy>
"""
        await editMessage(message, text, buttons.build_menu(2))
    elif data[2] == "rclone":
        buttons = ButtonMaker()
        buttons.ibutton("Rclone Config", f"userset {user_id} rcc")
        buttons.ibutton("Default Rclone Path", f"userset {user_id} rcp")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
        if user_dict.get("rclone_path", False):
            rccpath = user_dict["rclone_path"]
        elif RP := config_dict["RCLONE_PATH"]:
            rccpath = RP
        else:
            rccpath = "None"
        text = f"""<u>Rclone Settings for {name}</u>
Rclone Config <b>{rccmsg}</b>
Rclone Path is <copy>{rccpath}</copy>"""
        await editMessage(message, text, buttons.build_menu(1))
    elif data[2] == "gdrive":
        buttons = ButtonMaker()
        buttons.ibutton("token.pickle", f"userset {user_id} token")
        buttons.ibutton("Default Gdrive ID", f"userset {user_id} gdid")
        buttons.ibutton("Index URL", f"userset {user_id} index")
        if (
            user_dict.get("stop_duplicate", False)
            or "stop_duplicate" not in user_dict
            and config_dict["STOP_DUPLICATE"]
        ):
            buttons.ibutton(
                "Disable Stop Duplicate", f"userset {user_id} stop_duplicate false"
            )
            sd_msg = "Enabled"
        else:
            buttons.ibutton(
                "Enable Stop Duplicate", f"userset {user_id} stop_duplicate true"
            )
            sd_msg = "Disabled"
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
        if user_dict.get("gdrive_id", False):
            gdrive_id = user_dict["gdrive_id"]
        elif GDID := config_dict["GDRIVE_ID"]:
            gdrive_id = GDID
        else:
            gdrive_id = "None"
        index = user_dict["index_url"] if user_dict.get("index_url", False) else "None"
        text = f"""<u>Gdrive Tools Settings for {name}</u>
Gdrive Token <b>{tokenmsg}</b>
Gdrive ID is <copy>{gdrive_id}</copy>
Index URL is <copy>{index}</copy>
Stop Duplicate is <b>{sd_msg}</b>"""
        await editMessage(message, text, buttons.build_menu(1))
    elif data[2] == "vthumb":
        await sendFile(message, thumb_path, name)
        await update_user_settings(ctx)
    elif data[2] == "sthumb":
        buttons = ButtonMaker()
        if await aiopath.exists(thumb_path):
            buttons.ibutton("View Thumbnail", f"userset {user_id} vthumb")
            buttons.ibutton("Delete Thumbnail", f"userset {user_id} thumb")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send a photo to save it as custom thumbnail. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_thumb, pre_event=ctx)
        await event_handler(ctx, pfunc, True)
    elif data[2] == "yto":
        buttons = ButtonMaker()
        if user_dict.get("yt_opt", False) or config_dict["YT_DLP_OPTIONS"]:
            buttons.ibutton(
                "Remove YT-DLP Options", f"userset {user_id} yt_opt", "header"
            )
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = """
Send YT-DLP Options. Timeout: 60 sec
Format: key:value|key:value|key:value.
Example: format:bv*+mergeall[vcodec=none]|nocheckcertificate:True
Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official/177'>script</a> to convert cli arguments to api options.
        """
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=ctx, option="yt_opt")
        await event_handler(ctx, pfunc)
    elif data[2] == "lss":
        buttons = ButtonMaker()
        if user_dict.get("split_size", False):
            buttons.ibutton("Reset Split Size", f"userset {user_id} split_size")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send Leech split size in bytes. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="split_size")
        await event_handler(ctx, pfunc)
    elif data[2] == "rcc":
        buttons = ButtonMaker()
        if await aiopath.exists(rclone_conf):
            buttons.ibutton("Delete rclone.conf", f"userset {user_id} rclone_config")
        buttons.ibutton("Back", f"userset {user_id} rclone")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message, "Send rclone.conf. Timeout: 60 sec", buttons.build_menu(1)
        )
        pfunc = partial(add_rclone, pre_event=ctx)
        await event_handler(ctx, pfunc, document=True)
    elif data[2] == "rcp":
        buttons = ButtonMaker()
        if user_dict.get("rclone_path", False):
            buttons.ibutton("Reset Rclone Path", f"userset {user_id} rclone_path")
        buttons.ibutton("Back", f"userset {user_id} rclone")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Rclone Path. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=ctx, option="rclone_path")
        await event_handler(ctx, pfunc)
    elif data[2] == "token":
        buttons = ButtonMaker()
        if await aiopath.exists(token_pickle):
            buttons.ibutton("Delete token.pickle", f"userset {user_id} token_pickle")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message, "Send token.pickle. Timeout: 60 sec", buttons.build_menu(1)
        )
        pfunc = partial(add_token_pickle, pre_event=ctx)
        await event_handler(ctx, pfunc, document=True)
    elif data[2] == "gdid":
        buttons = ButtonMaker()
        if user_dict.get("gdrive_id", False):
            buttons.ibutton("Reset Gdrive ID", f"userset {user_id} gdrive_id")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Gdrive ID. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=ctx, option="gdrive_id")
        await event_handler(ctx, pfunc)
    elif data[2] == "index":
        buttons = ButtonMaker()
        if user_dict.get("index_url", False):
            buttons.ibutton("Remove Index URL", f"userset {user_id} index_url")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Index URL. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=ctx, option="index_url")
        await event_handler(ctx, pfunc)
    elif data[2] == "leech_prefix":
        buttons = ButtonMaker()
        if (
            user_dict.get("lprefix", False)
            or "lprefix" not in user_dict
            and config_dict["LEECH_FILENAME_PREFIX"]
        ):
            buttons.ibutton("Remove Leech Prefix", f"userset {user_id} lprefix")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send Leech Filename Prefix. You can add HTML tags. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="lprefix")
        await event_handler(ctx, pfunc)
    elif data[2] == "ldest":
        buttons = ButtonMaker()
        if (
            user_dict.get("leech_dest", False)
            or "leech_dest" not in user_dict
            and config_dict["LEECH_DUMP_CHAT"]
        ):
            buttons.ibutton("Reset Leech Destination", f"userset {user_id} leech_dest")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send leech destination community_id|group_id/user_id/pm. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="leech_dest")
        await event_handler(ctx, pfunc)
    elif data[2] == "ex_ex":
        buttons = ButtonMaker()
        if (
            user_dict.get("excluded_extensions", False)
            or "excluded_extensions" not in user_dict
            and GLOBAL_EXTENSION_FILTER
        ):
            buttons.ibutton(
                "Remove Excluded Extensions", f"userset {user_id} excluded_extensions"
            )
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send exluded extenions seperated by space without dot at beginning. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="excluded_extensions")
        await event_handler(ctx, pfunc)
    elif data[2] == "name_subtitute":
        buttons = ButtonMaker()
        if user_dict.get("name_sub", False):
            buttons.ibutton("Remove Name Subtitute", f"userset {user_id} name_sub")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        emsg = f"""Word Subtitions. You can add pattern instead of normal text. Timeout: 60 sec
Example: 'text : code : s|mirror : leech|tea :  : s|clone'

1. text will get replaced by code with sensitive case
2. mirror will get replaced by leech
4. tea will get removed with sensitive case
5. clone will get removed

Your Current Value is {user_dict.get('name_sub') or 'not added yet!'}
"""
        await editMessage(
            message,
            emsg,
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="name_sub")
        await event_handler(ctx, pfunc)
    elif data[2] in ["gd", "rc"]:
        du = "rc" if data[2] == "gd" else "gd"
        update_user_ldata(user_id, "default_upload", du)
        await update_user_settings(ctx)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] == "upload_paths":
        buttons = ButtonMaker()
        buttons.ibutton("New Path", f"userset {user_id} new_path")
        if user_dict.get(data[2], False):
            buttons.ibutton("Show All Paths", f"userset {user_id} show_path")
            buttons.ibutton("Remove Path", f"userset {user_id} rm_path")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Add or remove upload path.\n",
            buttons.build_menu(1),
        )
    elif data[2] == "new_path":
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send path name(no space in name) which you will use it as a shortcut and the path/id seperated by space. You can add multiple names and paths separated by new line. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=ctx, option="upload_paths")
        await event_handler(ctx, pfunc)
    elif data[2] == "rm_path":
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send paths names which you want to delete, separated by space. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(delete_path, pre_event=ctx)
        await event_handler(ctx, pfunc)
    elif data[2] == "show_path":
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        user_dict = user_data.get(user_id, {})
        msg = "".join(
            f"<b>{key}</b>: <copy>{value}</copy>\n"
            for key, value in user_dict["upload_paths"].items()
        )
        await editMessage(
            message,
            msg,
            buttons.build_menu(1),
        )
    elif data[2] == "reset":
        if ud := user_data.get(user_id, {}):
            if ud and ("is_sudo" in ud or "is_auth" in ud):
                for k in list(ud.keys()):
                    if k not in ["is_sudo", "is_auth"]:
                        del user_data[user_id][k]
            else:
                user_data[user_id].clear()
        await update_user_settings(ctx)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
        for fpath in [thumb_path, rclone_conf, token_pickle]:
            if await aiopath.exists(fpath):
                await remove(fpath)
    elif data[2] == "back":
        await update_user_settings(ctx)
    else:
        await deleteMessage(message.replied_to)
        await deleteMessage(message)


async def send_users_settings(ctx):
    message = ctx.event.message
    if user_data:
        msg = ""
        for u, d in user_data.items():
            kmsg = f"\n<b>{u}:</b>\n"
            if vmsg := "".join(
                f"{k}: <copy>{v}</copy>\n" for k, v in d.items() if f"{v}"
            ):
                msg += kmsg + vmsg

        msg_ecd = msg.encode()
        if len(msg_ecd) > 4000:
            with BytesIO(msg_ecd) as ofile:
                ofile.name = "users_settings.txt"
                await sendFile(message, ofile)
        else:
            await sendMessage(message, msg)
    else:
        await sendMessage(message, "No users data!")


bot.add_handler(
    CommandHandler(
        BotCommands.UsersCommand, send_users_settings, filter=CustomFilters.sudo
    )
)
bot.add_handler(
    CommandHandler(
        BotCommands.UserSetCommand, user_settings, filter=CustomFilters.authorized
    )
)
bot.add_handler(CallbackQueryHandler(edit_user_settings, filter=regexp("^userset")))
