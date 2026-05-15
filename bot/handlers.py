import json
import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from bot.keyboards import back_to_main, channels_menu, filters_menu, main_menu, start_keyboard
from filters import ai as ai_filter
from filters.match import matches
from storage.db import DB

logger = logging.getLogger(__name__)
router = Router()
_db: DB | None = None
_parser = None

FETCH_BATCH = 5


def setup(db: DB, parser=None):
    global _db, _parser
    _db = db
    _parser = parser


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
    # показываем постоянную кнопку внизу чата
    await msg.answer("👋", reply_markup=start_keyboard())
    text, kb = await _main_text_and_kb(msg.from_user.id)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.message(F.text == "🚀 Меню")
async def msg_menu_button(msg: Message, state: FSMContext):
    await state.clear()
    text, kb = await _main_text_and_kb(msg.from_user.id)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "fetch:jobs")
async def cb_fetch_jobs(cb: CallbackQuery):
    user = await _db.get_or_create_user(cb.from_user.id)
    channels = json.loads(user["channels"])
    keywords = json.loads(user["keywords"])
    ai_profile = user.get("ai_profile", "") or ""

    if not channels:
        await cb.answer("Сначала добавь каналы", show_alert=True)
        return

    await cb.answer("Ищу вакансии…")

    total_fetched = 0
    if _parser:
        for ch in channels:
            posts = await _parser.fetch(ch, limit=30)
            logger.info("fetched %d posts from %s", len(posts), ch)
            total_fetched += len(posts)
            for p in posts:
                await _db.save_post(p["channel"], p["message_id"], p["text"], p["posted_at"])

    logger.info("total fetched: %d, checking unsent for user %d", total_fetched, cb.from_user.id)
    unsent = await _db.get_unsent_posts(cb.from_user.id, channels, limit=FETCH_BATCH * 5)
    logger.info("unsent posts found: %d", len(unsent))

    sent = 0
    for post in unsent:
        if sent >= FETCH_BATCH:
            break

        text = post["text"] or ""
        ch = post["channel"].lstrip("@")
        link = f"https://t.me/{ch}/{post['message_id']}"

        if ai_profile:
            if not await ai_filter.is_relevant(text, ai_profile):
                await _db.mark_sent(cb.from_user.id, post["id"])
                continue
        elif keywords and not matches(text, keywords):
            await _db.mark_sent(cb.from_user.id, post["id"])
            continue

        try:
            await cb.message.answer(
                f"{text[:800]}\n\n{link}",
                disable_web_page_preview=True,
            )
            await _db.mark_sent(cb.from_user.id, post["id"])
            sent += 1
        except Exception as e:
            logger.warning("send error: %s", e)

    if sent == 0:
        await cb.message.answer("Новых подходящих вакансий нет")
    else:
        await cb.message.answer(f"Показал {sent} вакансий 👆")


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


def _normalize_channel(raw: str) -> str:
    raw = raw.strip()
    # https://t.me/username or t.me/username
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.split("/")[0].split("?")[0]
    if not raw.startswith("@"):
        raw = "@" + raw
    return raw


@router.message(Form.adding_channel)
async def msg_adding_channel(msg: Message, state: FSMContext):
    ch = _normalize_channel(msg.text)

    user = await _db.get_or_create_user(msg.from_user.id)
    channels = json.loads(user["channels"])
    if ch not in channels:
        channels.append(ch)
        await _db.set_channels(msg.from_user.id, channels)

        # запомнить текущий последний пост — чтобы не спамить историей
        if _parser:
            latest = await _parser.latest_id(ch)
            if latest:
                await _db.set_cursor(ch, latest)

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
