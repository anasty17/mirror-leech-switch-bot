from swibots import CommandHandler
from aiofiles import open as aiopen
from contextlib import redirect_stdout
from io import StringIO, BytesIO
from os import path as ospath, getcwd, chdir
from textwrap import indent
from traceback import format_exc

from bot import LOGGER, bot
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.switch_helper.bot_commands import BotCommands
from bot.helper.switch_helper.filters import CustomFilters
from bot.helper.switch_helper.message_utils import sendFile, sendMessage

namespaces = {}


def namespace_of(message):
    chat = message.group or message.user
    chat_id = chat.id
    if chat_id not in namespaces:
        namespaces[chat_id] = {
            "__builtins__": globals()["__builtins__"],
            "bot": bot,
            "message": message,
            "user": message.user,
            "chat": chat,
        }

    return namespaces[chat_id]


def log_input(message):
    chat_id = message.group_id or message.user_id
    LOGGER.info(f"IN: {message.message} (user={message.user_id}, chat={chat_id})")


async def send(msg, message):
    if len(str(msg)) > 2000:
        with BytesIO(str.encode(msg)) as out_file:
            await sendFile(message, out_file, "output.txt")
    else:
        LOGGER.info(f"OUT: '{msg}'")
        await sendMessage(message, f"<copy>{msg}</copy>")


async def aioexecute(ctx):
    message = ctx.event.message
    await send(await do("aexec", message), message)


async def execute(ctx):
    message = ctx.event.message
    await send(await do("exec", message), message)


def cleanup_code(code):
    if code.startswith("```") and code.endswith("```"):
        return "\n".join(code.split("\n")[1:-1])
    return code.strip("` \n")


async def do(func, message):
    log_input(message)
    content = message.message.split(maxsplit=1)[-1]
    body = cleanup_code(content)
    env = namespace_of(message)

    chdir(getcwd())
    async with aiopen(ospath.join(getcwd(), "bot/modules/temp.txt"), "w") as temp:
        await temp.write(body)

    stdout = StringIO()

    try:
        if func == "exec":
            exec(f"def func():\n{indent(body, '  ')}", env)
        else:
            exec(f"async def func():\n{indent(body, '  ')}", env)
    except Exception as e:
        return f"{e.__class__.__name__}: {e}"

    rfunc = env["func"]

    try:
        with redirect_stdout(stdout):
            func_return = (
                await sync_to_async(rfunc) if func == "exec" else await rfunc()
            )
    except:
        value = stdout.getvalue()
        return f"{value}{format_exc()}"
    else:
        value = stdout.getvalue()
        result = None
        if func_return is None:
            if value:
                result = f"{value}"
            else:
                try:
                    result = f"{repr(await sync_to_async(eval, body, env))}"
                except:
                    pass
        else:
            result = f"{value}{func_return}"
        if result:
            return result


async def clear(ctx):
    message = ctx.event.message
    chat_id = message.group_id or message.user_id
    log_input(message)
    global namespaces
    if chat_id in namespaces:
        del namespaces[chat_id]
    await send("Locals Cleared.", message)


bot.add_handler(
    CommandHandler(BotCommands.AExecCommand, aioexecute, filter=CustomFilters.owner)
)
bot.add_handler(
    CommandHandler(BotCommands.ExecCommand, execute, filter=CustomFilters.owner)
)
bot.add_handler(
    CommandHandler(BotCommands.ClearLocalsCommand, clear, filter=CustomFilters.owner)
)
