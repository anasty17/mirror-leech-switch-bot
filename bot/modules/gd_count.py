from swibots import CommandHandler

from bot import bot
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.links_utils import is_gdrive_link
from bot.helper.ext_utils.status_utils import get_readable_file_size
from bot.helper.mirror_leech_utils.gdrive_utils.count import gdCount
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import deleteMessage, sendMessage


async def countNode(ctx):
    message = ctx.event.message
    args = message.message.split()
    tag = f"@{message.user.username}"

    link = args[1] if len(args) > 1 else ""
    if len(link) == 0 and (reply_to := message.replied_to):
        link = reply_to.message.split(maxsplit=1)[0].strip()

    if is_gdrive_link(link):
        msg = await sendMessage(message, f"Counting: <copy>{link}</copy>")
        name, mime_type, size, files, folders = await sync_to_async(
            gdCount().count, link, message.user_id
        )
        if mime_type is None:
            await sendMessage(message, name)
            return
        await deleteMessage(msg)
        msg = f"<b>Name: </b><copy>{name}</copy>"
        msg += f"\n\n<b>Size: </b>{get_readable_file_size(size)}"
        msg += f"\n\n<b>Type: </b>{mime_type}"
        if mime_type == "Folder":
            msg += f"\n<b>SubFolders: </b>{folders}"
            msg += f"\n<b>Files: </b>{files}"
        msg += f"\n\n<b>cc: </b>{tag}"
    else:
        msg = (
            "Send Gdrive link along with command or by replying to the link by command"
        )

    await sendMessage(message, msg)


bot.add_handler(
    CommandHandler(BotCommands.CountCommand, countNode, filter=CustomFilters.authorized)
)
