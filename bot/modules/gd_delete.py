from swibots import CommandHandler

from bot import bot, LOGGER
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.links_utils import is_gdrive_link
from bot.helper.mirror_leech_utils.gdrive_utils.delete import gdDelete
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import auto_delete_message, sendMessage


async def deletefile(ctx):
    message = ctx.event.message
    args = message.message.split()
    if len(args) > 1:
        link = args[1]
    elif reply_to := message.replied_to:
        link = reply_to.message.split(maxsplit=1)[0].strip()
    else:
        link = ""
    if is_gdrive_link(link):
        LOGGER.info(link)
        msg = await sync_to_async(gdDelete().deletefile, link, message.user_id)
    else:
        msg = (
            "Send Gdrive link along with command or by replying to the link by command"
        )
    reply_message = await sendMessage(message, msg)
    await auto_delete_message(message, reply_message)


bot.add_handler(
    CommandHandler(
        BotCommands.DeleteCommand, deletefile, filter=CustomFilters.authorized
    )
)
