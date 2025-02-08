import json
import hashlib
import aiosqlite


CREATE_TABLES = """
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    keywords   TEXT    NOT NULL DEFAULT '[]',
    channels   TEXT    NOT NULL DEFAULT '[]',
    active     INTEGER NOT NULL DEFAULT 1,
    ai_profile TEXT    NOT NULL DEFAULT '',
    created_at TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    channel      TEXT NOT NULL,
    message_id   INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    text         TEXT,
    posted_at    TEXT,
    UNIQUE(channel, message_id)
);

CREATE TABLE IF NOT EXISTS sent (
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    sent_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, post_id)
);
"""


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


class DB:
    def __init__(self, path: str):
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(CREATE_TABLES)
        # migrate: add ai_profile if missing
        try:
            await self._conn.execute("ALTER TABLE users ADD COLUMN ai_profile TEXT NOT NULL DEFAULT ''")
            await self._conn.commit()
        except Exception:
            pass

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def get_or_create_user(self, user_id: int) -> dict:
        await self._conn.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )
        await self._conn.commit()
        async with self._conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row)

    async def set_keywords(self, user_id: int, keywords: list[str]):
        await self._conn.execute(
            "UPDATE users SET keywords = ? WHERE user_id = ?",
            (json.dumps(keywords), user_id),
        )
        await self._conn.commit()

    async def set_channels(self, user_id: int, channels: list[str]):
        await self._conn.execute(
            "UPDATE users SET channels = ? WHERE user_id = ?",
            (json.dumps(channels), user_id),
        )
        await self._conn.commit()

    async def set_ai_profile(self, user_id: int, profile: str):
        await self._conn.execute(
            "UPDATE users SET ai_profile = ? WHERE user_id = ?",
            (profile, user_id),
        )
        await self._conn.commit()

    async def set_active(self, user_id: int, active: bool):
        await self._conn.execute(
            "UPDATE users SET active = ? WHERE user_id = ?",
            (int(active), user_id),
        )
        await self._conn.commit()

    async def active_users(self) -> list[dict]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE active = 1"
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def save_post(self, channel: str, message_id: int, text: str, posted_at: str) -> int | None:
        h = _hash(text)
        try:
            async with self._conn.execute(
                "INSERT INTO posts (channel, message_id, content_hash, text, posted_at) VALUES (?, ?, ?, ?, ?)",
                (channel, message_id, h, text, posted_at),
            ) as cur:
                await self._conn.commit()
                return cur.lastrowid
        except aiosqlite.IntegrityError:
            return None

    async def already_sent(self, user_id: int, post_id: int) -> bool:
        async with self._conn.execute(
            "SELECT 1 FROM sent WHERE user_id = ? AND post_id = ?",
            (user_id, post_id),
        ) as cur:
            return await cur.fetchone() is not None

    async def mark_sent(self, user_id: int, post_id: int):
        await self._conn.execute(
            "INSERT OR IGNORE INTO sent (user_id, post_id) VALUES (?, ?)",
            (user_id, post_id),
        )
        await self._conn.commit()
