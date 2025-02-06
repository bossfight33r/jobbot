import asyncio
from dotenv import load_dotenv
import config
from telethon import TelegramClient

load_dotenv()

async def main():
    cfg = config.load()
    client = TelegramClient("jobbot", cfg.api_id, cfg.api_hash)
    await client.start()
    me = await client.get_me()
    print(f"Авторизован как: {me.first_name} (@{me.username})")
    print("Сессия сохранена в jobbot.session — теперь запускай make run")
    await client.disconnect()

asyncio.run(main())
