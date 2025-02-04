import re


def score(text: str, keywords: list[str]) -> int:
    if not keywords:
        return 1

    low = text.lower()
    hits = 0
    for kw in keywords:
        pattern = re.compile(re.escape(kw.lower()))
        if pattern.search(low):
            hits += 1
    return hits


def matches(text: str, keywords: list[str]) -> bool:
    return score(text, keywords) > 0
