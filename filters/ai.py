import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_client: genai.Client | None = None

PROMPT = """Ты фильтр вакансий. Пользователь ищет: {profile}

Текст вакансии:
{text}

Ответь одним словом — YES если вакансия подходит, NO если не подходит."""


def init(api_key: str):
    global _client
    _client = genai.Client(api_key=api_key)


async def is_relevant(text: str, profile: str) -> bool:
    if _client is None or not profile.strip():
        return True

    try:
        prompt = PROMPT.format(profile=profile, text=text[:2000])
        response = await _client.aio.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=10,
                temperature=0.1,
            ),
        )
        answer = response.text.strip().upper()
        return answer.startswith("YES")
    except Exception as e:
        logger.warning("gemini error: %s", e)
        return True
