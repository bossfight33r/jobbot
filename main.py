import asyncio
import json
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

import config
from bot import handlers
from filters import ai as ai_filter
from filters.match import matches
from parser.client import Parser
from storage.db import DB

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
        posts = await parser.fetch(channel)
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


async def scheduler(parser: Parser, db: DB, bot: Bot, interval: int):
    while True:
        try:
            await check_once(parser, db, bot)
        except Exception as e:
            logger.error("check failed: %s", e)
        await asyncio.sleep(interval)


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

    logger.info("starting jobbot, check interval=%ds", cfg.check_interval)

    await asyncio.gather(
        dp.start_polling(bot),
        scheduler(parser, db, bot, cfg.check_interval),
    )


if __name__ == "__main__":
    asyncio.run(main())
