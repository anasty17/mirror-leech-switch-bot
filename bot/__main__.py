#!/usr/bin/env python3
from signal import signal, SIGINT
from aiofiles.os import path as aiopath, remove as aioremove
from aiofiles import open as aiopen
from os import execl as osexecl
from psutil import disk_usage, cpu_percent, swap_memory, cpu_count, virtual_memory, net_io_counters, boot_time
from time import time
from sys import executable
from swibots import CommandHandler, Message, BotCommand
from asyncio import create_subprocess_exec, gather

from bot import bot, botStartTime, LOGGER, Interval, QbInterval, scheduler
from .helper.ext_utils.fs_utils import start_cleanup, clean_all, exit_clean_up
from .helper.ext_utils.bot_utils import get_readable_file_size, get_readable_time, cmd_exec, sync_to_async
from .helper.switch_helper.bot_commands import BotCommands
from .helper.switch_helper.message_utils import sendMessage, editMessage, sendFile
from .helper.switch_helper.filters import CustomFilters
from .helper.switch_helper.button_build import ButtonMaker
from bot.helper.listeners.aria2_listener import start_aria2_listener
from .modules import authorize, clone, gd_count, gd_delete, cancel_mirror, gd_search, mirror_leech, status, torrent_search, torrent_select, ytdlp, rss, shell, eval, users_settings, bot_settings


async def stats(ctx):
    if await aiopath.exists('.git'):
        last_commit = await cmd_exec("git log -1 --date=short --pretty=format:'%cd <b>From</b> %cr'", True)
        last_commit = last_commit[0]
    else:
        last_commit = 'No UPSTREAM_REPO'
    total, used, free, disk = disk_usage('/')
    swap = swap_memory()
    memory = virtual_memory()
    stats = f'<b>Commit Date:</b> {last_commit}\n\n'\
            f'<b>Bot Uptime:</b> {get_readable_time(time() - botStartTime)}\n'\
            f'<b>OS Uptime:</b> {get_readable_time(time() - boot_time())}\n\n'\
            f'<b>Total Disk Space:</b> {get_readable_file_size(total)}\n'\
            f'<b>Used:</b> {get_readable_file_size(used)} | <b>Free:</b> {get_readable_file_size(free)}\n\n'\
            f'<b>Upload:</b> {get_readable_file_size(net_io_counters().bytes_sent)}\n'\
            f'<b>Download:</b> {get_readable_file_size(net_io_counters().bytes_recv)}\n\n'\
            f'<b>CPU:</b> {cpu_percent(interval=0.5)}%\n'\
            f'<b>RAM:</b> {memory.percent}%\n'\
            f'<b>DISK:</b> {disk}%\n\n'\
            f'<b>Physical Cores:</b> {cpu_count(logical=False)}\n'\
            f'<b>Total Cores:</b> {cpu_count(logical=True)}\n\n'\
            f'<b>SWAP:</b> {get_readable_file_size(swap.total)} | <b>Used:</b> {swap.percent}%\n'\
            f'<b>Memory Total:</b> {get_readable_file_size(memory.total)}\n'\
            f'<b>Memory Free:</b> {get_readable_file_size(memory.available)}\n'\
            f'<b>Memory Used:</b> {get_readable_file_size(memory.used)}\n'
    await sendMessage(ctx.event.message, stats)


async def start(ctx):
    buttons = ButtonMaker()
    buttons.ubutton(
        "Repo", "https://www.github.com/anasty17/mirror-leech-switch-bot")
    buttons.ubutton("Owner", "https://t.me/anas_tayyar")
    reply_markup = buttons.build_menu(2)
    if await CustomFilters.authorized(ctx):
        start_string = f'''
This bot can mirror all your links|files|torrents to Google Drive or any rclone cloud or to switch.
Type /{BotCommands.HelpCommand} to get a list of available commands
'''
        await sendMessage(ctx.event.message, start_string, reply_markup)
    else:
        await sendMessage(ctx.event.message, 'You Are not authorized user! Deploy your own mirror-leech bot', reply_markup)


async def restart(ctx):
    restart_message = await sendMessage(ctx.event.message, "Restarting...")
    if scheduler.running:
        scheduler.shutdown(wait=False)
    for interval in [QbInterval, Interval]:
        if interval:
            interval[0].cancel()
    await sync_to_async(clean_all)
    proc1 = await create_subprocess_exec('pkill', '-9', '-f', 'gunicorn|aria2c|qbittorrent-nox|ffmpeg|rclone')
    proc2 = await create_subprocess_exec('python3', 'update.py')
    await gather(proc1.wait(), proc2.wait())
    async with aiopen(".restartmsg", "w") as f:
        await f.write(f"{restart_message.id}")
    osexecl(executable, executable, "-m", "bot")


async def ping(ctx):
    start_time = int(round(time() * 1000))
    reply = await sendMessage(ctx.event.message, "Starting Ping")
    end_time = int(round(time() * 1000))
    await editMessage(reply, f'{end_time - start_time} ms')


async def log(ctx):
    await sendFile(ctx.event.message, 'log.txt', 'log.txt')

help_string = f'''
NOTE: Try each command without any argument to see more detalis.
/ {BotCommands.MirrorCommand[0]} or /{BotCommands.MirrorCommand[1]}: Start mirroring to cloud.
/ {BotCommands.QbMirrorCommand[0]} or /{BotCommands.QbMirrorCommand[1]}: Start Mirroring to cloud using qBittorrent.
/ {BotCommands.YtdlCommand[0]} or /{BotCommands.YtdlCommand[1]}: Mirror yt-dlp supported link.
/ {BotCommands.LeechCommand[0]} or /{BotCommands.LeechCommand[1]}: Start leeching to Switch.
/ {BotCommands.QbLeechCommand[0]} or /{BotCommands.QbLeechCommand[1]}: Start leeching using qBittorrent.
/ {BotCommands.YtdlLeechCommand[0]} or /{BotCommands.YtdlLeechCommand[1]}: Leech yt-dlp supported link.
/ {BotCommands.CloneCommand} [drive_url]: Copy file/folder to Google Drive.
/ {BotCommands.CountCommand} [drive_url]: Count file/folder of Google Drive.
/ {BotCommands.DeleteCommand} [drive_url]: Delete file/folder from Google Drive (Only Owner & Sudo).
/ {BotCommands.UserSetCommand} [query]: Users settings.
/ {BotCommands.BotSetCommand} [query]: Bot settings.
/ {BotCommands.BtSelectCommand}: Select files from torrents by gid or reply.
/ {BotCommands.CancelMirror}: Cancel task by gid or reply.
/ {BotCommands.CancelAllCommand} [query]: Cancel all [status] tasks.
/ {BotCommands.ListCommand} [query]: Search in Google Drive(s).
/ {BotCommands.SearchCommand} [query]: Search for torrents with API.
/ {BotCommands.StatusCommand}: Shows a status of all the downloads.
/ {BotCommands.StatsCommand}: Show stats of the machine where the bot is hosted in.
/ {BotCommands.PingCommand}: Check how long it takes to Ping the Bot (Only Owner & Sudo).
/ {BotCommands.AuthorizeCommand}: Authorize a chat or a user to use the bot (Only Owner & Sudo).
/ {BotCommands.UnAuthorizeCommand}: Unauthorize a chat or a user to use the bot (Only Owner & Sudo).
/ {BotCommands.UsersCommand}: show users settings (Only Owner & Sudo).
/ {BotCommands.AddSudoCommand}: Add sudo user (Only Owner).
/ {BotCommands.RmSudoCommand}: Remove sudo users (Only Owner).
/ {BotCommands.RestartCommand}: Restart and update the bot (Only Owner & Sudo).
/ {BotCommands.LogCommand}: Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo).
/ {BotCommands.ShellCommand}: Run shell commands (Only Owner).
/ {BotCommands.EvalCommand}: Run Python Code Line | Lines (Only Owner).
/ {BotCommands.ExecCommand}: Run Commands In Exec (Only Owner).
/ {BotCommands.ClearLocalsCommand}: Clear {BotCommands.EvalCommand} or {BotCommands.ExecCommand} locals (Only Owner).
/ {BotCommands.RssCommand}: RSS Menu.
'''


async def bot_help(ctx):
    await sendMessage(ctx.event.message, help_string)


async def restart_notification():
    if not await aiopath.isfile(".restartmsg"):
        return
    with open(".restartmsg") as f:
        msg_id = int(f.read())
    await bot.edit_message(msg_id, 'Restarted Successfully!')
    await aioremove(".restartmsg")


def register_bot_cmds():
    bot.set_bot_commands(
        [BotCommand(BotCommands.MirrorCommand[0], "Start mirroring to cloud", True),
         BotCommand(BotCommands.MirrorCommand[1],
                    "Start mirroring to cloud", True),
         BotCommand(
             BotCommands.QbMirrorCommand[0], "Start Mirroring to cloud using qBittorrent", True),
         BotCommand(
             BotCommands.QbMirrorCommand[1], "Start Mirroring to cloud using qBittorrent", True),
         BotCommand(
             BotCommands.YtdlCommand[0], "Mirror yt-dlp supported link", True),
         BotCommand(
             BotCommands.YtdlCommand[1], "Mirror yt-dlp supported link", True),
         BotCommand(
             BotCommands.LeechCommand[0], "Start leeching to Switch", True),
         BotCommand(
             BotCommands.LeechCommand[1], "Start leeching to Switch", True),
         BotCommand(
             BotCommands.QbLeechCommand[0], "Start leeching using qBittorrent", True),
         BotCommand(
             BotCommands.QbLeechCommand[1], "Start leeching using qBittorrent", True),
         BotCommand(
             BotCommands.YtdlLeechCommand[0], "Leech yt-dlp supported link", True),
         BotCommand(
             BotCommands.YtdlLeechCommand[1], "Leech yt-dlp supported link", True),
         BotCommand(BotCommands.CloneCommand,
                    "Copy file/folder to Google Drive", True),
         BotCommand(BotCommands.CountCommand,
                    "Count file/folder of Google Drive", True),
         BotCommand(BotCommands.DeleteCommand,
                    "Delete file/folder from Google Drive (Only Owner & Sudo)", True),
         BotCommand(BotCommands.UserSetCommand, "Users settings", True),
         BotCommand(BotCommands.BotSetCommand, "Bot settings", True),
         BotCommand(BotCommands.BtSelectCommand,
                    "Select files from torrents by gid or reply", True),
         BotCommand(BotCommands.CancelMirror,
                    "Cancel task by gid or reply", True),
         BotCommand(BotCommands.CancelAllCommand,
                    "Cancel all [status] tasks", True),
         BotCommand(BotCommands.ListCommand,
                    "Search in Google Drive(s)", True),
         BotCommand(BotCommands.SearchCommand,
                    "Search for torrents with API", True),
         BotCommand(BotCommands.StatusCommand,
                    "Shows a status of all the downloads", True),
         BotCommand(BotCommands.PingCommand,
                    "Check how long it takes to Ping the Bot (Only Owner & Sudo)", True),
         BotCommand(BotCommands.AuthorizeCommand,
                    "Authorize a chat or a user to use the bot (Only Owner & Sudo)", True),
         BotCommand(BotCommands.UnAuthorizeCommand,
                    "Unauthorize a chat or a user to use the bot (Only Owner & Sudo)", True),
         BotCommand(BotCommands.UsersCommand,
                    "Show users settings (Only Owner & Sudo)", True),
         BotCommand(BotCommands.AddSudoCommand,
                    "Add sudo user (Only Owner)", True),
         BotCommand(BotCommands.RmSudoCommand,
                    "Remove sudo users (Only Owner)", True),
         BotCommand(BotCommands.RestartCommand,
                    "Restart and update the bot (Only Owner & Sudo)", True),
         BotCommand(BotCommands.LogCommand,
                    "Get a log file of the bot. Handy for getting crash reports (Only Owner & Sudo)", True),
         BotCommand(BotCommands.ShellCommand,
                    "Run shell commands (Only Owner)", True),
         BotCommand(BotCommands.EvalCommand,
                    "Run Python Code Line | Lines (Only Owner)", True),
         BotCommand(BotCommands.ExecCommand,
                    "Run Commands In Exec (Only Owner)", True),
         BotCommand(BotCommands.ClearLocalsCommand,
                    "Clear locals (Only Owner)", True),
         BotCommand(BotCommands.RssCommand, "RSS Menu", True)])


async def main():

    register_bot_cmds()

    await bot.start()

    await gather(start_cleanup(), torrent_search.initiate_search_tools(), restart_notification())

    await sync_to_async(start_aria2_listener, wait=False)

    bot.add_handler(CommandHandler(BotCommands.StartCommand, start))
    bot.add_handler(CommandHandler(BotCommands.LogCommand,
                    log, filter=CustomFilters.sudo))
    bot.add_handler(CommandHandler(BotCommands.RestartCommand,
                    restart, filter=CustomFilters.sudo))
    bot.add_handler(CommandHandler(BotCommands.PingCommand,
                    ping, filter=CustomFilters.authorized))
    bot.add_handler(CommandHandler(BotCommands.HelpCommand,
                    bot_help, filter=CustomFilters.authorized))
    bot.add_handler(CommandHandler(BotCommands.StatsCommand,
                    stats, filter=CustomFilters.authorized))
    LOGGER.info("Bot Started!")
    signal(SIGINT, exit_clean_up)

bot._loop.run_until_complete(main())
bot._loop.run_forever()
