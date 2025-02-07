from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu(active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📋 Фильтры", callback_data="screen:filters"),
        InlineKeyboardButton(text="📺 Каналы", callback_data="screen:channels"),
    )
    toggle = "⏸ Пауза" if active else "▶️ Возобновить"
    toggle_cb = "toggle:pause" if active else "toggle:resume"
    builder.row(
        InlineKeyboardButton(text=toggle, callback_data=toggle_cb),
        InlineKeyboardButton(text="📊 Статус", callback_data="screen:status"),
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


def back_to_main() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="screen:main"))
    return builder.as_markup()
