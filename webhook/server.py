import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone

from aiohttp import web

from filters import ai as ai_filter
from filters.match import matches
from storage.db import DB

logger = logging.getLogger(__name__)

OBSIDIAN_REPO = "/root/obsidian-main"
OBSIDIAN_DIR = "Вакансии"


def _safe_filename(title: str) -> str:
    name = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    return name[:80] or "vacancy"


async def _save_to_obsidian(title: str, salary: str, company: str, area: str, link: str, text: str):
    if not os.path.isdir(OBSIDIAN_REPO):
        return
    try:
        date = datetime.now().strftime("%Y-%m-%d")
        time = datetime.now().strftime("%H:%M")
        filename = f"{date} {_safe_filename(title)}.md"
        filepath = os.path.join(OBSIDIAN_REPO, OBSIDIAN_DIR, filename)

        lines = ["---", f"date: {date}", f"source: hh.ru", "status: новая", "---", ""]
        lines.append(f"# {title}")
        lines.append("")
        if salary:
            lines.append(f"**Зарплата:** {salary}")
        if company:
            lines.append(f"**Компания:** {company}")
        if area:
            lines.append(f"**Регион:** {area}")
        lines.append(f"**Ссылка:** {link}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(text[:2000])

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        await asyncio.to_thread(_git_push, filename)
    except Exception as e:
        logger.warning("obsidian save error: %s", e)


def _git_push(filename: str):
    os.system(f'cd {OBSIDIAN_REPO} && git add "{OBSIDIAN_DIR}/{filename}" && git commit -m "vacancy: {filename}" && git push')


async def handle_vacancy(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    bot = request.app["bot"]

    try:
        data = await request.json()
    except Exception:
        return web.Response(status=400, text="invalid json")

    vacancy_id = data.get("vacancy_id")
    title = data.get("title", "")
    text = data.get("text", "")
    salary = data.get("salary", "")
    company = data.get("company", "")
    area = data.get("area", "")
    link = data.get("link", "")

    if not vacancy_id or not text:
        return web.Response(status=400, text="vacancy_id and text required")

    parts = [title]
    if salary:
        parts.append(salary)
    if company:
        parts.append(company)
    if area:
        parts.append(area)
    parts.append(text)
    full_text = "\n".join(parts)

    posted_at = datetime.now(timezone.utc).isoformat()
    post_id = await db.save_post("hh.ru", int(vacancy_id), full_text, posted_at)
    if post_id is None:
        return web.Response(status=200, text="duplicate")

    asyncio.create_task(_save_to_obsidian(title, salary, company, area, link, text))

    users = await db.active_users()
    for user in users:
        # HH вакансии только тем у кого настроен hh_query
        if not user.get("hh_query", ""):
            continue

        ai_profile = user.get("ai_profile", "") or ""
        keywords = json.loads(user["keywords"])

        if ai_profile:
            if not await ai_filter.is_relevant(full_text, ai_profile):
                continue
        elif keywords and not matches(full_text, keywords):
            continue

        if await db.already_sent(user["user_id"], post_id):
            continue

        try:
            msg = title
            if salary:
                msg += f"\n{salary}"
            if company:
                msg += f" · {company}"
            if area:
                msg += f" · {area}"
            msg += f"\n\n{link}"

            await bot.send_message(user["user_id"], msg, disable_web_page_preview=True)
            await db.mark_sent(user["user_id"], post_id)
        except Exception as e:
            logger.warning("failed to send to %s: %s", user["user_id"], e)

    return web.Response(status=200, text="ok")


async def handle_hh_queries(request: web.Request) -> web.Response:
    db: DB = request.app["db"]
    queries = await db.get_hh_queries()
    return web.json_response(queries)


def create_app(db: DB, bot) -> web.Application:
    app = web.Application()
    app["db"] = db
    app["bot"] = bot
    app.router.add_post("/vacancy", handle_vacancy)
    app.router.add_get("/hh-queries", handle_hh_queries)
    return app
