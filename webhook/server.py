import json
import logging
from datetime import datetime, timezone

from aiohttp import web

from filters import ai as ai_filter
from filters.match import matches
from storage.db import DB

logger = logging.getLogger(__name__)


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
