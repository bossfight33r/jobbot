import json
import logging

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from storage.db import DB

logger = logging.getLogger(__name__)
router = Router()
_db: DB | None = None


def setup(db: DB):
    global _db
    _db = db


@router.message(Command("start"))
async def cmd_start(msg: Message):
    await _db.get_or_create_user(msg.from_user.id)
    await msg.answer(
        "Привет! Я слежу за каналами с вакансиями и присылаю подходящие.\n\n"
        "/add_filter <keyword> — добавить фильтр\n"
        "/remove_filter <keyword> — удалить фильтр\n"
        "/filters — мои фильтры\n"
        "/add_channel <@channel> — добавить канал\n"
        "/remove_channel <@channel> — удалить канал\n"
        "/channels — мои каналы\n"
        "/pause — приостановить\n"
        "/resume — возобновить\n"
        "/status — текущие настройки"
    )


@router.message(Command("add_filter"))
async def cmd_add_filter(msg: Message):
    kw = msg.text.removeprefix("/add_filter").strip().lower()
    if not kw:
        await msg.answer("Укажи ключевое слово: /add_filter python")
        return

    user = await _db.get_or_create_user(msg.from_user.id)
    keywords = json.loads(user["keywords"])
    if kw in keywords:
        await msg.answer(f"«{kw}» уже есть в фильтрах")
        return

    keywords.append(kw)
    await _db.set_keywords(msg.from_user.id, keywords)
    await msg.answer(f"Добавил фильтр: «{kw}»")


@router.message(Command("remove_filter"))
async def cmd_remove_filter(msg: Message):
    kw = msg.text.removeprefix("/remove_filter").strip().lower()
    if not kw:
        await msg.answer("Укажи ключевое слово: /remove_filter python")
        return

    user = await _db.get_or_create_user(msg.from_user.id)
    keywords = json.loads(user["keywords"])
    if kw not in keywords:
        await msg.answer(f"«{kw}» нет в фильтрах")
        return

    keywords.remove(kw)
    await _db.set_keywords(msg.from_user.id, keywords)
    await msg.answer(f"Удалил фильтр: «{kw}»")


@router.message(Command("filters"))
async def cmd_filters(msg: Message):
    user = await _db.get_or_create_user(msg.from_user.id)
    keywords = json.loads(user["keywords"])
    if not keywords:
        await msg.answer("Фильтров нет — присылаю все вакансии из твоих каналов")
    else:
        await msg.answer("Фильтры:\n" + "\n".join(f"• {k}" for k in keywords))


@router.message(Command("add_channel"))
async def cmd_add_channel(msg: Message):
    ch = msg.text.removeprefix("/add_channel").strip()
    if not ch.startswith("@"):
        ch = "@" + ch
    if len(ch) < 2:
        await msg.answer("Укажи канал: /add_channel @python_jobs")
        return

    user = await _db.get_or_create_user(msg.from_user.id)
    channels = json.loads(user["channels"])
    if ch in channels:
        await msg.answer(f"{ch} уже отслеживается")
        return

    channels.append(ch)
    await _db.set_channels(msg.from_user.id, channels)
    await msg.answer(f"Добавил канал: {ch}")


@router.message(Command("remove_channel"))
async def cmd_remove_channel(msg: Message):
    ch = msg.text.removeprefix("/remove_channel").strip()
    if not ch.startswith("@"):
        ch = "@" + ch

    user = await _db.get_or_create_user(msg.from_user.id)
    channels = json.loads(user["channels"])
    if ch not in channels:
        await msg.answer(f"{ch} не найден в списке")
        return

    channels.remove(ch)
    await _db.set_channels(msg.from_user.id, channels)
    await msg.answer(f"Удалил канал: {ch}")


@router.message(Command("channels"))
async def cmd_channels(msg: Message):
    user = await _db.get_or_create_user(msg.from_user.id)
    channels = json.loads(user["channels"])
    if not channels:
        await msg.answer("Каналов нет. Добавь: /add_channel @python_jobs")
    else:
        await msg.answer("Каналы:\n" + "\n".join(f"• {c}" for c in channels))


@router.message(Command("pause"))
async def cmd_pause(msg: Message):
    await _db.get_or_create_user(msg.from_user.id)
    await _db.set_active(msg.from_user.id, False)
    await msg.answer("Уведомления приостановлены. /resume — возобновить")


@router.message(Command("resume"))
async def cmd_resume(msg: Message):
    await _db.get_or_create_user(msg.from_user.id)
    await _db.set_active(msg.from_user.id, True)
    await msg.answer("Уведомления возобновлены")


@router.message(Command("status"))
async def cmd_status(msg: Message):
    user = await _db.get_or_create_user(msg.from_user.id)
    keywords = json.loads(user["keywords"])
    channels = json.loads(user["channels"])
    active = bool(user["active"])

    lines = [
        f"Статус: {'активен' if active else 'пауза'}",
        f"Каналов: {len(channels)}",
        f"Фильтров: {len(keywords)}",
    ]
    if channels:
        lines.append("\nКаналы: " + ", ".join(channels))
    if keywords:
        lines.append("Фильтры: " + ", ".join(keywords))

    await msg.answer("\n".join(lines))
