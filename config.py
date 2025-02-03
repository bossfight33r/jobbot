import os
from dataclasses import dataclass


@dataclass
class Config:
    api_id: int
    api_hash: str
    bot_token: str
    db_path: str
    check_interval: int


def load() -> Config:
    return Config(
        api_id=int(os.environ["TG_API_ID"]),
        api_hash=os.environ["TG_API_HASH"],
        bot_token=os.environ["BOT_TOKEN"],
        db_path=os.environ.get("DB_PATH", "jobbot.db"),
        check_interval=int(os.environ.get("CHECK_INTERVAL", "300")),
    )
