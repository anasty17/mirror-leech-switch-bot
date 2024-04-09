from swibots import CommandHandler

from bot import user_data, DATABASE_URL, bot
from bot.helper.ext_utils.bot_utils import update_user_ldata
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendMessage


async def authorize(ctx):
    message = ctx.event.message
    msg = message.message.split()
    if len(msg) > 1:
        id_ = msg[1].strip()
        try:
            id_ = int(id_)
        except:
            pass
    elif reply_to := message.replied_to:
        id_ = reply_to.user_id
    else:
        id_ = message.community_id
    if not id:
        return
    if id_ in user_data and user_data[id_].get("is_auth"):
        msg = "Already Authorized!"
    else:
        update_user_ldata(id_, "is_auth", True)
        if DATABASE_URL:
            await DbManager().update_user_data(id_)
        msg = "Authorized"
    await sendMessage(message, msg)


async def unauthorize(ctx):
    message = ctx.event.message
    msg = message.message.split()
    if len(msg) > 1:
        id_ = msg[1].strip()
        try:
            id_ = int(id_)
        except:
            pass
    elif reply_to := message.replied_to:
        id_ = reply_to.user_id
    else:
        id_ = message.community_id
    if not id:
        return
    if id_ not in user_data or user_data[id_].get("is_auth"):
        update_user_ldata(id_, "is_auth", False)
        if DATABASE_URL:
            await DbManager().update_user_data(id_)
        msg = "Unauthorized"
    else:
        msg = "Already Unauthorized!"
    await sendMessage(message, msg)


async def addSudo(ctx):
    id_ = ""
    message = ctx.event.message
    msg = message.message.split()
    if len(msg) > 1:
        id_ = msg[1].strip()
        try:
            id_ = int(id_)
        except:
            pass
    elif reply_to := message.replied_to:
        id_ = reply_to.user_id
    if id_:
        if id_ in user_data and user_data[id_].get("is_sudo"):
            msg = "Already Sudo!"
        else:
            update_user_ldata(id_, "is_sudo", True)
            if DATABASE_URL:
                await DbManager().update_user_data(id_)
            msg = "Promoted as Sudo"
    else:
        msg = "Give ID or Reply To message of whom you want to Promote."
    await sendMessage(message, msg)


async def removeSudo(ctx):
    id_ = ""
    message = ctx.event.message
    msg = message.message.split()
    if len(msg) > 1:
        id_ = msg[1].strip()
        try:
            id_ = int(id_)
        except:
            pass
    elif reply_to := message.replied_to:
        id_ = reply_to.user_id
    if id_ and id_ not in user_data or user_data[id_].get("is_sudo"):
        update_user_ldata(id_, "is_sudo", False)
        if DATABASE_URL:
            await DbManager().update_user_data(id_)
        msg = "Demoted"
    else:
        msg = "Give ID or Reply To message of whom you want to remove from Sudo"
    await sendMessage(message, msg)


bot.add_handler(
    CommandHandler(BotCommands.AuthorizeCommand, authorize, filter=CustomFilters.sudo)
)
bot.add_handler(
    CommandHandler(
        BotCommands.UnAuthorizeCommand, unauthorize, filter=CustomFilters.sudo
    )
)
bot.add_handler(
    CommandHandler(BotCommands.AddSudoCommand, addSudo, filter=CustomFilters.sudo)
)
bot.add_handler(
    CommandHandler(BotCommands.RmSudoCommand, removeSudo, filter=CustomFilters.sudo)
)
