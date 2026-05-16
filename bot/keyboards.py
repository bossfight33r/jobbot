from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


def main_menu(active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📨 Найти вакансии", callback_data="fetch:jobs"),
    )
    builder.row(
        InlineKeyboardButton(text="📋 Фильтры", callback_data="screen:filters"),
        InlineKeyboardButton(text="📺 Каналы", callback_data="screen:channels"),
    )
    builder.row(
        InlineKeyboardButton(text="🤖 AI профиль", callback_data="screen:ai"),
        InlineKeyboardButton(text="🔎 HH.ru", callback_data="screen:hh"),
    )
    toggle = "⏸ Пауза" if active else "▶️ Возобновить"
    toggle_cb = "toggle:pause" if active else "toggle:resume"
    builder.row(
        InlineKeyboardButton(text=toggle, callback_data=toggle_cb),
        InlineKeyboardButton(text="📊 Статус", callback_data="screen:status"),
    )
    builder.row(
        InlineKeyboardButton(text="📈 Статистика", callback_data="screen:stats"),
    )
    return builder.as_markup()


def filters_menu(keywords: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for kw in keywords:
        builder.row(
            InlineKeyboardButton(text=f"🔍 {kw}", callback_data="noop"),
            InlineKeyboardButton(text="❌", callback_data=f"del:filter:{kw}"),
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить фильтр", callback_data="add:filter"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    return builder.as_markup()


def channels_menu(channels: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(
            InlineKeyboardButton(text=f"📢 {ch}", callback_data="noop"),
            InlineKeyboardButton(text="❌", callback_data=f"del:channel:{ch}"),
        )
    builder.row(InlineKeyboardButton(text="➕ Добавить канал", callback_data="add:channel"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    return builder.as_markup()


def start_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🚀 Меню"))
    return builder.as_markup(resize_keyboard=True, persistent=True)


def hh_menu(query: str, area_name: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if query:
        builder.row(InlineKeyboardButton(text=f"🔍 {query}", callback_data="noop"))
        builder.row(InlineKeyboardButton(text=f"📍 {area_name}", callback_data="noop"))
        builder.row(InlineKeyboardButton(text="✏️ Изменить запрос", callback_data="hh:edit:query"))
        builder.row(InlineKeyboardButton(text="📍 Изменить регион", callback_data="hh:edit:area"))
        builder.row(InlineKeyboardButton(text="🗑 Отключить", callback_data="hh:clear"))
    else:
        builder.row(InlineKeyboardButton(text="✏️ Настроить поиск", callback_data="hh:edit:query"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    return builder.as_markup()


def hh_area_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    areas = [
        ("🇷🇺 Вся Россия", "113"),
        ("🏙 Москва", "1"),
        ("🌆 Санкт-Петербург", "2"),
        ("🌐 Удалённо", "remote"),
    ]
    for name, code in areas:
        builder.row(InlineKeyboardButton(text=name, callback_data=f"hh:area:{code}"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:hh"))
    return builder.as_markup()


AREA_NAMES = {
    "113": "Вся Россия",
    "1": "Москва",
    "2": "Санкт-Петербург",
    "remote": "Удалённо",
}


def back_to_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    return builder.as_markup()
