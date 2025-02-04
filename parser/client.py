import logging
from datetime import datetime, timezone

from telethon import TelegramClient
from telethon.errors import ChannelPrivateError, UsernameNotOccupiedError
from telethon.tl.types import Message

logger = logging.getLogger(__name__)


class Parser:
    def __init__(self, api_id: int, api_hash: str, session: str = "jobbot"):
        self.client = TelegramClient(session, api_id, api_hash)

    async def start(self):
        await self.client.start()

    async def stop(self):
        await self.client.disconnect()

    async def fetch(self, channel: str, limit: int = 20) -> list[dict]:
        try:
            entity = await self.client.get_entity(channel)
        except (ChannelPrivateError, UsernameNotOccupiedError, ValueError) as e:
            logger.warning("cannot access %s: %s", channel, e)
            return []

        results = []
        async for msg in self.client.iter_messages(entity, limit=limit):
            if not isinstance(msg, Message) or not msg.text:
                continue
            posted_at = msg.date.astimezone(timezone.utc).isoformat()
            results.append({
                "channel": channel,
                "message_id": msg.id,
                "text": msg.text,
                "posted_at": posted_at,
                "link": f"https://t.me/{channel.lstrip('@')}/{msg.id}",
            })

        return results
