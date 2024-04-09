from io import BytesIO
from swibots import CommandHandler

from bot import LOGGER, bot
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendMessage, sendFile


async def shell(ctx):
    message = ctx.event.message
    cmd = message.message.split(maxsplit=1)
    if len(cmd) == 1:
        await sendMessage(message, "No command to execute was given.")
        return
    cmd = cmd[1]
    stdout, stderr, _ = await cmd_exec(cmd, shell=True)
    reply = ""
    if len(stdout) != 0:
        reply += f"*Stdout*\n<copy>{stdout}</copy>\n"
        LOGGER.info(f"Shell - {cmd} - {stdout}")
    if len(stderr) != 0:
        reply += f"*Stderr*\n<copy>{stderr}</copy>"
        LOGGER.error(f"Shell - {cmd} - {stderr}")
    if len(reply) > 3000:
        with BytesIO(str.encode(reply)) as out_file:
            out_file.name = "shell_output.txt"
            await sendFile(message, out_file)
    elif len(reply) != 0:
        await sendMessage(message, reply)
    else:
        await sendMessage(message, "No Reply")


bot.add_handler(
    CommandHandler(BotCommands.ShellCommand, shell, filter=CustomFilters.owner)
)
