import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.keyboards import back_to_main, channels_menu, filters_menu, main_menu
from storage.db import DB

logger = logging.getLogger(__name__)
router = Router()
_db: DB | None = None


def setup(db: DB):
    global _db
    _db = db


class Form(StatesGroup):
    adding_filter = State()
    adding_channel = State()
    setting_ai_profile = State()


async def _main_text_and_kb(user_id: int):
    user = await _db.get_or_create_user(user_id)
    active = bool(user["active"])
    keywords = json.loads(user["keywords"])
    channels = json.loads(user["channels"])

    status = "активен ✅" if active else "пауза ⏸"
    text = (
        f"<b>Jobbot</b> — {status}\n"
        f"Каналов: {len(channels)}  |  Фильтров: {len(keywords)}"
    )
    return text, main_menu(active)


@router.message(Command("start"))
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    await _db.get_or_create_user(msg.from_user.id)
    text, kb = await _main_text_and_kb(msg.from_user.id)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "screen:main")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await _main_text_and_kb(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "screen:filters")
async def cb_filters(cb: CallbackQuery):
    user = await _db.get_or_create_user(cb.from_user.id)
    keywords = json.loads(user["keywords"])
    text = "<b>Фильтры</b>\nПрисылаю вакансии где встречается хотя бы одно слово.\nЕсли фильтров нет — присылаю всё."
    await cb.message.edit_text(text, reply_markup=filters_menu(keywords), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "screen:channels")
async def cb_channels(cb: CallbackQuery):
    user = await _db.get_or_create_user(cb.from_user.id)
    channels = json.loads(user["channels"])
    text = "<b>Каналы</b>\nОтслеживаемые каналы с вакансиями."
    await cb.message.edit_text(text, reply_markup=channels_menu(channels), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "screen:status")
async def cb_status(cb: CallbackQuery):
    user = await _db.get_or_create_user(cb.from_user.id)
    keywords = json.loads(user["keywords"])
    channels = json.loads(user["channels"])
    active = bool(user["active"])

    lines = [
        f"<b>Статус:</b> {'активен ✅' if active else 'пауза ⏸'}",
        f"<b>Каналов:</b> {len(channels)}",
        f"<b>Фильтров:</b> {len(keywords)}",
    ]
    if channels:
        lines.append("\n" + "\n".join(f"📢 {c}" for c in channels))
    if keywords:
        lines.append("\n" + "\n".join(f"🔍 {k}" for k in keywords))

    await cb.message.edit_text("\n".join(lines), reply_markup=back_to_main(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "toggle:pause")
async def cb_pause(cb: CallbackQuery):
    await _db.set_active(cb.from_user.id, False)
    text, kb = await _main_text_and_kb(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer("Уведомления приостановлены")


@router.callback_query(F.data == "toggle:resume")
async def cb_resume(cb: CallbackQuery):
    await _db.set_active(cb.from_user.id, True)
    text, kb = await _main_text_and_kb(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer("Уведомления возобновлены")


@router.callback_query(F.data == "add:filter")
async def cb_add_filter(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.adding_filter)
    await cb.message.edit_text(
        "Введи ключевое слово (например: <code>python</code>, <code>remote</code>):",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(Form.adding_filter)
async def msg_adding_filter(msg: Message, state: FSMContext):
    kw = msg.text.strip().lower()
    if not kw:
        await msg.answer("Пустое слово, попробуй ещё раз:")
        return

    user = await _db.get_or_create_user(msg.from_user.id)
    keywords = json.loads(user["keywords"])
    if kw not in keywords:
        keywords.append(kw)
        await _db.set_keywords(msg.from_user.id, keywords)

    await state.clear()
    text = "<b>Фильтры</b>\nПрисылаю вакансии где встречается хотя бы одно слово.\nЕсли фильтров нет — присылаю всё."
    await msg.answer(text, reply_markup=filters_menu(keywords), parse_mode="HTML")


@router.callback_query(F.data.startswith("del:filter:"))
async def cb_del_filter(cb: CallbackQuery):
    kw = cb.data.removeprefix("del:filter:")
    user = await _db.get_or_create_user(cb.from_user.id)
    keywords = json.loads(user["keywords"])
    if kw in keywords:
        keywords.remove(kw)
        await _db.set_keywords(cb.from_user.id, keywords)

    text = "<b>Фильтры</b>\nПрисылаю вакансии где встречается хотя бы одно слово.\nЕсли фильтров нет — присылаю всё."
    await cb.message.edit_text(text, reply_markup=filters_menu(keywords), parse_mode="HTML")
    await cb.answer(f"Удалил «{kw}»")


@router.callback_query(F.data == "add:channel")
async def cb_add_channel(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.adding_channel)
    await cb.message.edit_text(
        "Введи username канала (например: <code>@python_jobs</code>):",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(Form.adding_channel)
async def msg_adding_channel(msg: Message, state: FSMContext):
    ch = msg.text.strip()
    if not ch.startswith("@"):
        ch = "@" + ch

    user = await _db.get_or_create_user(msg.from_user.id)
    channels = json.loads(user["channels"])
    if ch not in channels:
        channels.append(ch)
        await _db.set_channels(msg.from_user.id, channels)

    await state.clear()
    text = "<b>Каналы</b>\nОтслеживаемые каналы с вакансиями."
    await msg.answer(text, reply_markup=channels_menu(channels), parse_mode="HTML")


@router.callback_query(F.data.startswith("del:channel:"))
async def cb_del_channel(cb: CallbackQuery):
    ch = cb.data.removeprefix("del:channel:")
    user = await _db.get_or_create_user(cb.from_user.id)
    channels = json.loads(user["channels"])
    if ch in channels:
        channels.remove(ch)
        await _db.set_channels(cb.from_user.id, channels)

    text = "<b>Каналы</b>\nОтслеживаемые каналы с вакансиями."
    await cb.message.edit_text(text, reply_markup=channels_menu(channels), parse_mode="HTML")
    await cb.answer(f"Удалил {ch}")


@router.callback_query(F.data == "screen:ai")
async def cb_ai(cb: CallbackQuery, state: FSMContext):
    user = await _db.get_or_create_user(cb.from_user.id)
    profile = user.get("ai_profile", "") or ""
    if profile:
        text = f"<b>🤖 AI фильтр активен</b>\n\nТвой профиль:\n<i>{profile}</i>\n\nAI читает каждую вакансию и решает — подходит тебе или нет.\nОтправь новый профиль чтобы изменить, или нажми «Очистить»."
    else:
        text = (
            "<b>🤖 AI фильтр</b>\n\n"
            "Опиши что ищешь — AI будет читать каждую вакансию и фильтровать.\n\n"
            "Например:\n"
            "<i>Python backend разработчик, удалённо, от 150к рублей</i>\n\n"
            "Отправь описание чтобы включить:"
        )
    builder = InlineKeyboardBuilder()
    if profile:
        builder.row(InlineKeyboardButton(text="✏️ Изменить", callback_data="ai:edit"))
        builder.row(InlineKeyboardButton(text="🗑 Очистить", callback_data="ai:clear"))
    else:
        builder.row(InlineKeyboardButton(text="✏️ Задать профиль", callback_data="ai:edit"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    await cb.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await cb.answer()


@router.callback_query(F.data == "ai:edit")
async def cb_ai_edit(cb: CallbackQuery, state: FSMContext):
    await state.set_state(Form.setting_ai_profile)
    await cb.message.edit_text(
        "Опиши кого ищешь — стек, формат, зарплата:\n\n"
        "<i>Например: Python backend, удалённо, senior, от 200к</i>",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )
    await cb.answer()


@router.message(Form.setting_ai_profile)
async def msg_setting_ai_profile(msg: Message, state: FSMContext):
    profile = msg.text.strip()
    await _db.set_ai_profile(msg.from_user.id, profile)
    await state.clear()
    await msg.answer(
        f"✅ AI профиль сохранён:\n<i>{profile}</i>\n\nТеперь буду фильтровать вакансии через Gemini.",
        reply_markup=back_to_main(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "ai:clear")
async def cb_ai_clear(cb: CallbackQuery):
    await _db.set_ai_profile(cb.from_user.id, "")
    text, kb = await _main_text_and_kb(cb.from_user.id)
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await cb.answer("AI фильтр отключён")


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
