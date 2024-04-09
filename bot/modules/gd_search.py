from swibots import CommandHandler, CallbackQueryHandler, regexp

from bot import LOGGER, bot, user_data
from bot.helper.ext_utils.bot_utils import sync_to_async, get_telegraph_list
from bot.helper.mirror_leech_utils.gdrive_utils.search import gdSearch
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.button_build import ButtonMaker
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendMessage, editMessage


async def list_buttons(user_id, isRecursive=True, user_token=False):
    buttons = ButtonMaker()
    buttons.ibutton(
        "Folders", f"list_types {user_id} folders {isRecursive} {user_token}"
    )
    buttons.ibutton("Files", f"list_types {user_id} files {isRecursive} {user_token}")
    buttons.ibutton("Both", f"list_types {user_id} both {isRecursive} {user_token}")
    buttons.ibutton(
        f"Recursive: {isRecursive}",
        f"list_types {user_id} rec {isRecursive} {user_token}",
    )
    buttons.ibutton(
        f"User Token: {user_token}",
        f"list_types {user_id} ut {isRecursive} {user_token}",
    )
    buttons.ibutton("Cancel", f"list_types {user_id} cancel")
    return buttons.build_menu(2)


async def _list_drive(key, message, item_type, isRecursive, user_token, user_id):
    LOGGER.info(f"listing: {key}")
    if user_token:
        user_dict = user_data.get(user_id, {})
        target_id = user_dict.get("gdrive_id", "") or ""
        LOGGER.info(target_id)
    else:
        target_id = ""
    telegraph_content, contents_no = await sync_to_async(
        gdSearch(isRecursive=isRecursive, itemType=item_type).drive_list,
        key,
        target_id,
        user_id,
    )
    if telegraph_content:
        try:
            button = await get_telegraph_list(telegraph_content)
        except Exception as e:
            await editMessage(message, e)
            return
        msg = f"<b>Found {contents_no} result for <i>{key}</i></b>"
        await editMessage(message, msg, button)
    else:
        await editMessage(message, f"No result found for <i>{key}</i>")


async def select_type(ctx):
    data = ctx.event.callback_data.split()
    message = ctx.event.message
    user_id = ctx.event.action_by_id
    key = message.replied_to.message.split(maxsplit=1)[1].strip()
    if user_id != int(data[1]):
        return await ctx.event.answer(text="Not Yours!", show_alert=True)
    elif data[2] == "rec":
        isRecursive = not bool(eval(data[3]))
        buttons = await list_buttons(user_id, isRecursive, eval(data[4]))
        return await editMessage(message, "Choose list options:", buttons)
    elif data[2] == "ut":
        user_token = not bool(eval(data[4]))
        buttons = await list_buttons(user_id, eval(data[3]), user_token)
        return await editMessage(message, "Choose list options:", buttons)
    elif data[2] == "cancel":
        return await editMessage(message, "list has been canceled!")
    item_type = data[2]
    isRecursive = eval(data[3])
    user_token = eval(data[4])
    await editMessage(message, f"<b>Searching for <i>{key}</i></b>")
    await _list_drive(key, message, item_type, isRecursive, user_token, user_id)


async def gdrive_search(ctx):
    message = ctx.event.message
    if len(message.message.split()) == 1:
        return await sendMessage(message, "Send a search key along with command")
    user_id = ctx.event.action_by_id
    buttons = await list_buttons(user_id)
    await sendMessage(message, "Choose list options:", buttons)


bot.add_handler(
    CommandHandler(
        BotCommands.ListCommand, gdrive_search, filter=CustomFilters.authorized
    )
)
bot.add_handler(CallbackQueryHandler(select_type, filter=regexp("^list_types")))
