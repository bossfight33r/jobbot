import asyncio
import json
import logging
import signal

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import config
from bot import handlers
from filters import ai as ai_filter
from filters.match import matches
from parser.client import Parser
from storage.db import DB
from webhook.server import create_app

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def check_once(parser: Parser, db: DB, bot: Bot):
    users = await db.active_users()
    if not users:
        return

    all_channels: set[str] = set()
    for u in users:
        for ch in json.loads(u["channels"]):
            all_channels.add(ch)

    if not all_channels:
        return

    for channel in all_channels:
        min_id = await db.get_cursor(channel)
        posts = await parser.fetch(channel, limit=50, min_id=min_id)
        if not posts:
            continue

        new_max_id = max(p["message_id"] for p in posts)
        await db.set_cursor(channel, new_max_id)

        for post in posts:
            post_id = await db.save_post(
                post["channel"],
                post["message_id"],
                post["text"],
                post["posted_at"],
            )
            if post_id is None:
                continue

            for user in users:
                if channel not in json.loads(user["channels"]):
                    continue

                keywords = json.loads(user["keywords"])
                ai_profile = user.get("ai_profile", "")

                if ai_profile:
                    if not await ai_filter.is_relevant(post["text"], ai_profile):
                        continue
                elif not matches(post["text"], keywords):
                    continue

                if await db.already_sent(user["user_id"], post_id):
                    continue

                try:
                    await bot.send_message(
                        user["user_id"],
                        f"{post['text'][:800]}\n\n{post['link']}",
                        disable_web_page_preview=True,
                    )
                    await db.mark_sent(user["user_id"], post_id)
                except Exception as e:
                    logger.warning("failed to send to %s: %s", user["user_id"], e)


async def scheduler(parser: Parser, db: DB, bot: Bot, interval: int, stop: asyncio.Event):
    while not stop.is_set():
        try:
            await check_once(parser, db, bot)
        except Exception as e:
            logger.error("check failed: %s", e)
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass


async def main():
    cfg = config.load()

    db = DB(cfg.db_path)
    await db.connect()

    parser = Parser(cfg.api_id, cfg.api_hash)
    await parser.start()

    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher(storage=MemoryStorage())
    handlers.setup(db, parser)
    dp.include_router(handlers.router)

    if cfg.gemini_api_key:
        ai_filter.init(cfg.gemini_api_key)
        logger.info("gemini AI filter enabled")

    webhook_app = create_app(db, bot)
    runner = web.AppRunner(webhook_app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", cfg.webhook_port)
    await site.start()
    logger.info("webhook server on port %d", cfg.webhook_port)

    logger.info("starting jobbot, check interval=%ds", cfg.check_interval)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    sched = asyncio.create_task(scheduler(parser, db, bot, cfg.check_interval, stop))
    poll = asyncio.create_task(dp.start_polling(bot))

    await stop.wait()
    logger.info("shutting down…")

    poll.cancel()
    sched.cancel()
    await asyncio.gather(poll, sched, return_exceptions=True)

    await runner.cleanup()
    await parser.stop()
    await db.close()
    logger.info("bye")


if __name__ == "__main__":
    asyncio.run(main())
