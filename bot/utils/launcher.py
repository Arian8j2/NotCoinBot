import os
import glob
import asyncio
import argparse
from itertools import cycle
from typing import Literal

from TGConvertor import SessionManager
from pyrogram import Client, compose
from better_proxy import Proxy
from loguru._logger import Logger

from config import settings
from bot.core import run_clicker, create_sessions


clients = []


def get_session_files() -> list[str]:
    return ["bot"]


def get_proxies() -> list[Proxy]:
    if settings.USE_PROXY_FROM_FILE:
        with open(file='config/proxies.txt',
                  mode='r',
                  encoding='utf-8-sig') as file:
            proxies: list[Proxy] = [Proxy.from_str(proxy=row.strip()).as_url for row in file]
    else:
        proxies = []

    return proxies


async def get_clients(session_files: list[str]) -> list[Client]:
    global clients

    if not settings.SESSION_STRING:
        raise ValueError("SESSION_STRING not found in the .env file.")

    clients = [Client(
        name=session_name,
        session_string=settings.SESSION_STRING,
        workdir='sessions/',
        plugins=dict(root='bot/plugins')
    ) for session_name in session_files]

    return clients


async def start_process(logger: Logger) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--action', type=int, help='Action to perform')

    args = parser.parse_args()

    session_files: list[str] = get_session_files()
    proxies: list[Proxy] = get_proxies()

    logger.info(f"{len(session_files)} sessions / {len(proxies)} proxies detected")

    await asyncio.sleep(delay=.25)

    user_action: Literal[1, 2, 3] = args.action if args.action else int(input(
        "\n1. Создать сессию"
        "\n2. Запустить бота С возможностью управления через телеграмм"
        "\n3. Запустить бота БЕЗ возможности управления через телеграмм"
        "\nВыберите ваше действие: "
    ))
    print()

    if user_action == 1:
        await create_sessions()

    elif user_action == 2:
        clients = await get_clients(session_files=session_files)

        logger.info(f"Бот запущен на {len(session_files)} сессиях.\n"
                    f"Отправьте /help в чате Избранное/Saved Messages \n")

        await compose(clients)

    elif user_action == 3:
        clients = await get_clients(session_files=session_files)

        logger.info("The bot is launched without the ability to control via Telegram")

        await run_tasks(clients=clients)

    else:
        logger.error("Действие выбрано некорректно")


async def run_tasks(clients: list[Client]):
    session_files = get_session_files()
    proxies = get_proxies()
    proxies_cycled = cycle(proxies) if proxies else None

    tasks: list = [
        asyncio.create_task(coro=run_clicker(
            session_name=current_session_name, client=client, proxy=next(proxies_cycled) if proxies_cycled else None)
        )
        for client, current_session_name in zip(clients, session_files)
    ]

    await asyncio.gather(*tasks)
