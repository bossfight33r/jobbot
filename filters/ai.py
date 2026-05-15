import asyncio
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


def _call_gemini(prompt: str) -> str:
    response = _client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=64,
            temperature=0.1,
        ),
    )
    if response.text:
        return response.text.strip().upper()
    # fallback: try candidates
    for candidate in (response.candidates or []):
        for part in (candidate.content.parts or []):
            if part.text:
                return part.text.strip().upper()
    return "NO"


async def is_relevant(text: str, profile: str) -> bool:
    if _client is None or not profile.strip():
        return True

    try:
        prompt = PROMPT.format(profile=profile, text=text[:2000])
        answer = await asyncio.to_thread(_call_gemini, prompt)
        return answer.startswith("YES")
    except Exception as e:
        logger.warning("gemini error: %s", e)
        return True
