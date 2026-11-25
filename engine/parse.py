from __future__ import annotations

import json
import os
import re

_SPLIT = re.compile(r"\s*(?:,|;|\band\b|\bwith\b)\s*", re.I)
_COUNT = re.compile(r"^(\d+(?:\.\d+)?)\s+(.+)$")


def fallback_parse(text: str) -> list[dict]:
    items = []
    for part in _SPLIT.split(text.strip()):
        part = part.strip(" .")
        if not part:
            continue
        counted = _COUNT.match(part)
        if counted:
            items.append({"name": counted.group(2).strip(), "count": float(counted.group(1))})
        else:
            items.append({"name": part, "count": 1})
    return items


def parse_meal(text: str) -> tuple[list[dict], str]:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return fallback_parse(text), "fallback"
    try:
        from groq import Groq

        client = Groq(api_key=api_key)
        completion = client.chat.completions.create(
            model=os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
            temperature=0,
            max_completion_tokens=400,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Split a meal description into foods. "
                        'Reply with JSON only: {"items":[{"name":"","count":1}]}. '
                        "count is a number. Do not add foods that were not mentioned. "
                        "Do not include nutrient numbers."
                    ),
                },
                {"role": "user", "content": text},
            ],
        )
        payload = json.loads(completion.choices[0].message.content or "{}")
        items = []
        for item in payload.get("items") or []:
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            count = float(item.get("count") or 1)
            if count <= 0:
                count = 1
            items.append({"name": name, "count": count})
        if not items:
            return fallback_parse(text), "fallback"
        return items, "groq"
    except Exception:
        return fallback_parse(text), "fallback"
