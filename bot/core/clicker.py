import sys
import asyncio
from base64 import b64decode
from math import floor
from random import randint
from time import time
from urllib.parse import unquote

import aiohttp
from loguru import logger
from pyrogram import Client
from pyrogram.raw import functions

from config import settings
from bot.exceptions import InvalidSession, TurboExpired, BadRequestStatus, ForbiddenStatus
from bot.utils import eval_js, scripts
from .headers import headers
from .TLS import TLSv1_3_BYPASS


class Clicker:
    def __init__(self, session_name: str, client: Client, proxy: str):
        self.session_name: str = session_name
        self.client: Client = client
        self.proxy = proxy

    async def get_access_token(self, client: aiohttp.ClientSession, tg_web_data: str) -> str:
        while True:
            response = None

            try:
                response: aiohttp.ClientResponse = await client.post(
                    url='https://clicker-api.joincommunity.xyz/auth/webapp-session',
                    proxy=self.proxy,
                    json={'webAppData': tg_web_data})

                response_json = await response.json(content_type=None)
                return response_json['data']['accessToken']

            except Exception as error:
                if response:
                    status_code = response.status
                    logger.error(f'{self.session_name} | Неизвестная ошибка при получении Access Token: {error} | '
                                 f'Статус: {status_code} | Ответ: {await response.text()}')
                else:
                    logger.error(f'{self.session_name} | Неизвестная ошибка при получении Access Token: {error}')

                await asyncio.sleep(delay=3)

    async def get_tg_web_data(self) -> str | None:
        while True:
            try:
                if self.proxy:
                    proxy_dict = scripts.get_proxy_dict(session_proxy=self.proxy)
                else:
                    proxy_dict: None = None

                self.client.proxy = proxy_dict

                with_tg = True

                if not self.client.is_connected:
                    with_tg = False
                    try:
                        await self.client.connect()
                    except:
                        self.client.proxy = None
                        await self.client.connect()

                web_view = await self.client.invoke(
                    functions.messages.RequestWebView(
                        peer=await self.client.resolve_peer('notcoin_bot'),
                        bot=await self.client.resolve_peer('notcoin_bot'),
                        platform='android',
                        from_bot_menu=False,
                        url='https://clicker.joincommunity.xyz/clicker'
                    )
                )

                if with_tg is False:
                    await self.client.disconnect()

                auth_url = web_view.url

                tg_web_data: str = unquote(
                    string=unquote(
                        string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0]))

                return tg_web_data

            except InvalidSession as error:
                raise error

            except Exception as error:
                logger.error(f'{self.session_name} | Неизвестная ошибка при авторизации: {error}')
                await asyncio.sleep(delay=3)

    async def get_profile_data(self, client: aiohttp.ClientSession) -> dict:
        while True:
            try:
                response: aiohttp.ClientResponse = await client.get(
                    url='https://clicker-api.joincommunity.xyz/clicker/profile', proxy=self.proxy)

                status_code = response.status
                try:
                    response_json = await response.json(content_type=None)

                except:
                    logger.error(f'{self.session_name} | Неизвестный ответ при получении данных профиля | '
                                 f'Статус: {status_code} | Ответ: {await response.text()}')

                    await asyncio.sleep(delay=3)
                    continue

                return response_json

            except Exception as error:
                logger.error(f'{self.session_name} | Неизвестная ошибка при получении данных профиля: {error}')
                await asyncio.sleep(delay=3)

    async def send_clicks(
            self,
            client: aiohttp.ClientSession,
            clicks_count: int,
            tg_web_data: str,
            balance: int,
            total_coins: str | int,
            click_hash: str | None = None,
            turbo: bool | None = None
    ) -> tuple[int | str, int | str | None, int | None, int | None, bool | None]:
        while True:
            try:
                json_data: dict = {
                    'count': clicks_count,
                    'hash': -1,
                    'webAppData': tg_web_data
                }

                if click_hash:
                    json_data['hash']: str = click_hash

                if turbo:
                    json_data['turbo']: bool = True

                response: aiohttp.ClientResponse = await client.post(
                    url='https://clicker-api.joincommunity.xyz/clicker/core/click',
                    proxy=self.proxy,
                    json=json_data)

                status_code = response.status
                if not str(status_code).startswith('2'):
                    return status_code, None, None, None, None

                response_json: dict = await response.json(content_type=None)

                if (response_json.get('data')
                        and isinstance(response_json['data'], dict)
                        and response_json['data'].get('message', '') == 'Turbo mode is expired'):
                    raise TurboExpired()

                if (response_json.get('data')
                        and isinstance(response_json['data'], dict)
                        and response_json['data'].get('message', '') == 'Try later'):
                    await asyncio.sleep(delay=3)
                    continue

                if response_json.get('ok'):
                    available_coins = response_json.get('data', [])[0].get('availableCoins')

                    logger.success(f'{self.session_name} | Successfull Click | Balance: '
                                   f'{balance + clicks_count} (+{clicks_count}) | Total Coins: {total_coins}')

                    next_hash: int | None = eval_js(
                        function=b64decode((await response.json())['data'][0]['hash'][0]).decode())

                    return (status_code, balance + clicks_count, available_coins, next_hash,
                            (await response.json())['data'][0]['turboTimes'] > 0)

                logger.error(f'{self.session_name} | Не удалось сделать Click, ответ: {await response.text()}')
                return status_code, None, None, None, None

            except Exception as error:
                logger.error(f'{self.session_name} | Неизвестная ошибка при попытке сделать Click: {error}')
                await asyncio.sleep(delay=3)

    async def get_merged_list(self, client: aiohttp.ClientSession) -> dict | None:
        response = None

        try:
            response: aiohttp.ClientResponse = await client.get(
                url='https://clicker-api.joincommunity.xyz/clicker/store/merged', proxy=self.proxy)

            response_json = await response.json(content_type=None)
            if response_json.get('ok'):
                return response_json

            logger.error(f'{self.session_name} | Не удалось получить список товаров, ответ: {await response.text()}')

            return None

        except Exception as error:
            if response:
                logger.error(f'{self.session_name} | Неизвестная ошибка при получении списка товаров: {error}, '
                             f'ответ: {await response.text()}')
            else:
                logger.error(f'{self.session_name} | Неизвестная ошибка при получении списка товаров: {error}')

            await asyncio.sleep(delay=3)

    async def buy_item(self, client: aiohttp.ClientSession, item_id: int | str) -> bool:
        response = None

        try:
            response: aiohttp.ClientResponse = await client.post(
                url=f'https://clicker-api.joincommunity.xyz/clicker/store/buy/{item_id}',
                headers={'accept-language': 'ru-RU,ru;q=0.9'},
                proxy=self.proxy,
                json=False)

            if (await response.json(content_type=None)).get('ok'):
                return True

            logger.error(f'{self.session_name} | Неизвестный ответ при покупке в магазине: {await response.text()}')

            return False

        except Exception as error:
            if response:
                logger.error(f'{self.session_name} | Неизвестная ошибка при покупке в магазине: {error}, '
                             f'ответ: {await response.text()}')
            else:
                logger.error(f'{self.session_name} | Неизвестная ошибка при покупке в магазине: {error}')

            await asyncio.sleep(delay=3)
            return False

    async def activate_turbo(self, client: aiohttp.ClientSession) -> int | None:
        response = None

        try:
            response: aiohttp.ClientResponse = await client.post(
                url=f'https://clicker-api.joincommunity.xyz/clicker/core/active-turbo',
                headers={'accept-language': 'ru-RU,ru;q=0.9'},
                proxy=self.proxy,
                json=False)

            return (await response.json(content_type=None))['data'][0].get('multiple', 1)

        except Exception as error:
            if response:
                logger.error(f'{self.session_name} | Неизвестная ошибка при активации Turbo: {error}, '
                             f'ответ: {await response.text()}')
            else:
                logger.error(f'{self.session_name} | Неизвестная ошибка при активации Turbo: {error}')

            await asyncio.sleep(delay=3)
            return None

    async def activate_task(self, client: aiohttp.ClientSession, task_id: int | str) -> bool | None:
        response = None

        try:
            response: aiohttp.ClientResponse = await client.post(
                url=f'https://clicker-api.joincommunity.xyz/clicker/task/{task_id}',
                headers={'accept-language': 'ru-RU,ru;q=0.9'},
                proxy=self.proxy,
                json=False)

            if (await response.json(content_type=None)).get('ok'):
                return True

            logger.error(
                f'{self.session_name} | Неизвестный ответ при активации Task {task_id}: {await response.text()}')

            return False

        except Exception as error:
            if response:
                logger.error(f'{self.session_name} | Неизвестная ошибка при активации Task {task_id}: {error}, '
                             f'ответ: {await response.text()}')
            else:
                logger.error(f'{self.session_name} | Неизвестная ошибка при активации Task {task_id}: {error}')

            await asyncio.sleep(delay=3)
            return False

    async def get_free_buffs_data(self, client: aiohttp.ClientSession) -> tuple[bool, bool]:
        max_turbo_times: int = 3
        max_full_energy_times: int = 3

        turbo_times_count: int = 0
        full_energy_times_count: int = 0

        response = None

        try:
            response: aiohttp.ClientResponse = await client.get(
                url=f'https://clicker-api.joincommunity.xyz/clicker/task/combine-completed', proxy=self.proxy)

            for current_buff in (await response.json(content_type=None))['data']:
                if current_buff['taskId'] == 3:
                    max_turbo_times: int = current_buff['task']['max']

                    if current_buff['task']['status'] == 'active':
                        turbo_times_count += 1

                elif current_buff['taskId'] == 2:
                    max_full_energy_times: int = current_buff['task']['max']

                    if current_buff['task']['status'] == 'active':
                        full_energy_times_count += 1

            return max_turbo_times > turbo_times_count, max_full_energy_times > full_energy_times_count

        except Exception as error:
            if response:
                logger.error(f'{self.session_name} | Неизвестная ошибка при получении статуса бесплатных баффов: '
                             f'{error}, ответ: {await response.text()}')
            else:
                logger.error(f'{self.session_name} | Неизвестная ошибка при получении статуса бесплатных баффов: '
                             f'{error}')

            await asyncio.sleep(delay=3)
            return False, False

    async def check_proxy(self) -> None:
        try:
            async with aiohttp.request('GET', 'https://httpbin.org/ip', proxy=self.proxy,
                                       timeout=aiohttp.ClientTimeout(5)) as response:
                ip = (await response.json()).get('origin')
                logger.info(f"{self.session_name} | Proxy IP: {ip}")
        except Exception as er:
            logger.error(f"{self.session_name} | Proxy: {self.proxy} | Error: {er}")

    @staticmethod
    async def close_connectors(*connectors: aiohttp.TCPConnector):
        for connector in connectors:
            try:
                if connector: await connector.close() if not connector.closed else ...
            except:
                ...

    async def run(self):
        access_token_created_time: float = 0
        tg_web_data: str | None = None
        click_hash: str | None = None
        active_turbo: bool = False
        turbo_multiplier: int = 1

        ssl_context = TLSv1_3_BYPASS.create_ssl_context()

        ssl_conn = aiohttp.TCPConnector(ssl=ssl_context)

        client = aiohttp.ClientSession(
            connector=ssl_conn,
            headers=headers
        )

        if self.proxy:
            await self.check_proxy()

        try:
            while True:
                try:
                    if time() - access_token_created_time >= (settings.SLEEP_TO_UPDATE_USER_DATA * 60):
                        tg_web_data: str = await self.get_tg_web_data()

                        access_token: str = await self.get_access_token(client=client, tg_web_data=tg_web_data)

                        client.headers['Authorization']: str = f'Bearer {access_token}'
                        headers['Authorization']: str = f'Bearer {access_token}'

                        access_token_created_time: float = time()

                    profile_data: dict = await self.get_profile_data(client=client)

                    if not active_turbo:
                        if settings.MIN_CLICKS_COUNT > floor(profile_data['data'][0]['availableCoins'] /
                                                             profile_data['data'][0]['multipleClicks']):
                            logger.info(f'{self.session_name} | Недостаточно монет для клика')
                            continue

                    if floor(profile_data['data'][0]['availableCoins'] /
                             profile_data['data'][0]['multipleClicks']) < settings.MAX_CLICK_COUNT:
                        max_clicks_count: int = floor(profile_data['data'][0]['availableCoins'] /
                                                      profile_data['data'][0]['multipleClicks'])

                    else:
                        max_clicks_count: int = settings.MAX_CLICK_COUNT

                    clicks_count: int = (randint(a=settings.MIN_CLICKS_COUNT, b=max_clicks_count) *
                                         profile_data['data'][0]['multipleClicks'] * turbo_multiplier)

                    try:
                        status_code, new_balance, available_coins, click_hash, have_turbo = \
                            await self.send_clicks(client=client,
                                                   clicks_count=int(clicks_count),
                                                   tg_web_data=tg_web_data,
                                                   balance=int(profile_data['data'][0]['balanceCoins']),
                                                   total_coins=profile_data['data'][0]['totalCoins'],
                                                   click_hash=click_hash,
                                                   turbo=active_turbo)

                        if status_code == 400:
                            logger.warning(f"{self.session_name} | Invalid data: {status_code}")
                            await asyncio.sleep(delay=35)

                            await self.close_connectors(client, ssl_conn)
                            access_token_created_time = 0

                            raise BadRequestStatus()

                        if status_code == 403:
                            logger.warning(f"{self.session_name} | Доступ к API запрещен: {status_code}")
                            logger.info(f"{self.session_name} | Сплю {settings.SLEEP_AFTER_FORBIDDEN_STATUS} сек")
                            await asyncio.sleep(delay=settings.SLEEP_AFTER_FORBIDDEN_STATUS)

                            await self.close_connectors(client, ssl_conn)
                            access_token_created_time = 0

                            raise ForbiddenStatus()

                        if not str(status_code).startswith('2'):
                            logger.error(f"{self.session_name} | Неизвестный статус ответа: {status_code}")
                            await asyncio.sleep(delay=15)

                            continue

                    except TurboExpired:
                        active_turbo: bool = False
                        turbo_multiplier: int = 1

                        continue

                    if have_turbo:
                        random_sleep_time: int = randint(a=settings.SLEEP_BEFORE_ACTIVATE_TURBO[0],
                                                         b=settings.SLEEP_BEFORE_ACTIVATE_TURBO[1])

                        logger.info(f'{self.session_name} | Сплю {random_sleep_time} перед активацией Turbo')

                        await asyncio.sleep(delay=random_sleep_time)

                        turbo_multiplier: int | None = await self.activate_turbo(client=client)

                        if turbo_multiplier:
                            logger.success(f'{self.session_name} | Успешно активировал Turbo: x{turbo_multiplier}')

                            active_turbo: bool = True
                            continue
                        else:
                            turbo_multiplier: int = 1

                    if new_balance:
                        merged_data: dict | None = await self.get_merged_list(client=client)

                        if merged_data:
                            for current_merge in merged_data['data']:
                                if current_merge['id'] == 1:
                                    if not settings.AUTO_BUY_ENERGY_BOOST:
                                        continue

                                    energy_price: int | None = current_merge['price']
                                    energy_count: int | None = current_merge['count']

                                    if energy_count >= settings.MAX_ENERGY_BOOST:
                                        continue

                                    if new_balance >= energy_price and current_merge['max'] > current_merge['count']:
                                        sleep_before_buy_merge: int = randint(a=settings.SLEEP_BEFORE_BUY_MERGE[0],
                                                                              b=settings.SLEEP_BEFORE_BUY_MERGE[1])

                                        logger.info(f'{self.session_name} | Улучшаем Energy Boost до '
                                                    f'{energy_count + 1} lvl')
                                        logger.info(f'{self.session_name} | Сплю {sleep_before_buy_merge} сек. '
                                                    f'перед покупкой Energy Boost')

                                        await asyncio.sleep(delay=sleep_before_buy_merge)

                                        if await self.buy_item(client=client, item_id=1):
                                            logger.success(f'{self.session_name} | Успешно купил Energy '
                                                           'Boost')
                                            continue

                                elif current_merge['id'] == 2:
                                    if not settings.AUTO_BUY_SPEED_BOOST:
                                        continue

                                    speed_price: int | None = current_merge['price']
                                    speed_count: int | None = current_merge['count']

                                    if speed_count >= settings.MAX_SPEED_BOOST:
                                        continue

                                    if new_balance >= speed_price and current_merge['max'] > current_merge['count']:
                                        sleep_before_buy_merge: int = randint(a=settings.SLEEP_BEFORE_BUY_MERGE[0],
                                                                              b=settings.SLEEP_BEFORE_BUY_MERGE[1])

                                        logger.info(f'{self.session_name} | Улучшаем Speed Boost до '
                                                    f'{speed_count + 1} lvl')
                                        logger.info(f'{self.session_name} | Сплю {sleep_before_buy_merge} сек. '
                                                    f'перед покупкой Speed Boost')

                                        await asyncio.sleep(delay=sleep_before_buy_merge)

                                        if await self.buy_item(client=client, item_id=2):
                                            logger.success(f'{self.session_name} | Успешно купил Speed Boost')
                                            continue

                                elif current_merge['id'] == 3:
                                    if not settings.AUTO_BUY_CLICK_BOOST:
                                        continue

                                    click_price: int | None = current_merge['price']
                                    click_count: int | None = current_merge['count']

                                    if click_count >= settings.MAX_CLICK_BOOST:
                                        continue

                                    if new_balance >= click_price and current_merge['max'] > current_merge['count']:
                                        sleep_before_buy_merge: int = randint(a=settings.SLEEP_BEFORE_BUY_MERGE[0],
                                                                              b=settings.SLEEP_BEFORE_BUY_MERGE[1])

                                        logger.info(f'{self.session_name} | Улучшаем Click Booster до '
                                                    f'{click_count + 1} lvl')
                                        logger.info(f'{self.session_name} | Сплю {sleep_before_buy_merge} сек. '
                                                    f'перед покупкой Click Booster')

                                        await asyncio.sleep(delay=sleep_before_buy_merge)

                                        if await self.buy_item(client=client, item_id=3):
                                            logger.success(f'{self.session_name} | Успешно купил Click Boost')
                                            continue

                                elif current_merge['id'] == 4:
                                    ...

                    free_daily_turbo, free_daily_full_energy = await self.get_free_buffs_data(client=client)
                    min_available_coins = settings.MIN_AVAILABLE_COINS

                    if settings.ACTIVATE_DAILY_ENERGY:
                        if available_coins < min_available_coins:
                            if free_daily_full_energy:
                                random_sleep_time: int = randint(a=settings.SLEEP_BEFORE_ACTIVATE_FREE_BUFFS[0],
                                                                 b=settings.SLEEP_BEFORE_ACTIVATE_FREE_BUFFS[1])

                                logger.info(
                                    f'{self.session_name} | Sleep {random_sleep_time} seconds before activating '
                                    f'daily Full Energy')

                                await asyncio.sleep(delay=random_sleep_time)

                                if await self.activate_task(client=client, task_id=2):
                                    logger.success(f'{self.session_name} | Successfully requested daily Full Energy')

                                    continue

                    if settings.SLEEP_BY_MIN_COINS:
                        if available_coins:

                            if available_coins < min_available_coins:
                                sleep_time_to_min_coins = settings.SLEEP_BY_MIN_COINS_TIME

                                logger.info(f"{self.session_name} | Minimum balance reached: {available_coins}")
                                logger.info(f"{self.session_name} | Sleep {sleep_time_to_min_coins} seconds.")

                                await asyncio.sleep(delay=sleep_time_to_min_coins)

                                logger.info(f"{self.session_name} | I keep clicking!")

                                continue

                    if settings.ACTIVATE_DAILY_TURBO:
                        if free_daily_turbo:
                            random_sleep_time: int = randint(a=settings.SLEEP_BEFORE_ACTIVATE_FREE_BUFFS[0],
                                                             b=settings.SLEEP_BEFORE_ACTIVATE_FREE_BUFFS[1])

                            logger.info(
                                f'{self.session_name} | Sleep {random_sleep_time} seconds before requesting daily Turbo')

                            await asyncio.sleep(delay=random_sleep_time)

                            if await self.activate_task(client=client, task_id=3):
                                logger.success(f'{self.session_name} | Successfully requested daily Turbo')

                                random_sleep_time: int = randint(a=settings.SLEEP_BEFORE_ACTIVATE_TURBO[0],
                                                                 b=settings.SLEEP_BEFORE_ACTIVATE_TURBO[1])

                                logger.info(f'{self.session_name} | Sleep {random_sleep_time} seconds before activating Turbo')

                                await asyncio.sleep(delay=random_sleep_time)

                                turbo_multiplier: int | None = await self.activate_turbo(client=client)

                                if turbo_multiplier:
                                    logger.success(f'{self.session_name} | Successfully activated Turbo: '
                                                   f'x{turbo_multiplier}')
                                    active_turbo: bool = True
                                    continue

                                else:
                                    turbo_multiplier: int = 1

                except InvalidSession as error:
                    raise error

                except Exception as error:
                    logger.error(f'{self.session_name} | Неизвестная ошибка: {error}')

                    random_sleep_time: int = randint(a=settings.SLEEP_BETWEEN_CLICK[0],
                                                     b=settings.SLEEP_BETWEEN_CLICK[1])

                    logger.info(f'{self.session_name} | Sleep {random_sleep_time} second.')
                    await asyncio.sleep(delay=random_sleep_time)

                else:
                    random_sleep_time: int = randint(a=settings.SLEEP_BETWEEN_CLICK[0],
                                                     b=settings.SLEEP_BETWEEN_CLICK[1])

                    logger.info(f'{self.session_name} | Sleep {random_sleep_time} second.')
                    await asyncio.sleep(delay=random_sleep_time)

        except InvalidSession as error:
            await self.close_connectors(client, ssl_conn)
            raise error

        except Exception as error:
            await self.close_connectors(client, ssl_conn)

            logger.error(f'{self.session_name} | Неизвестная ошибка: {error}')
            await asyncio.sleep(delay=3)


async def run_clicker(session_name: str, client: Client, proxy: str | None = None) -> None:
    try:
        sys.setrecursionlimit(100000)

        await Clicker(session_name=session_name, client=client, proxy=proxy).run()

    except (BadRequestStatus, ForbiddenStatus):
        await run_clicker(session_name=session_name, client=client, proxy=proxy)

    except InvalidSession:
        logger.error(f'{session_name} | Invalid Session')
