from __future__ import annotations

import json
import os

from engine.foods import Food, NUTRIENTS

ALLOWED = {
    "veg": {"veg"},
    "egg": {"veg", "egg"},
    "nonveg": {"veg", "egg", "nonveg"},
}
BUDGET = 30


def candidate_packet(foods: tuple[Food, ...] | list[Food], diet: str) -> list[dict]:
    allowed = ALLOWED[diet]
    packet = []
    for food in foods:
        if food.kind != "filler" or food.diet not in allowed:
            continue
        serving = food.per_serving()
        packet.append(
            {
                "food_id": food.food_id,
                "name": food.name,
                "price_inr": food.price_inr,
                "serving_name": food.serving_name,
                "serving_g": food.serving_g,
                **serving,
            }
        )
    return packet


def fallback_ids(packet: list[dict], worst_key: str) -> list[str]:
    ranked = sorted(
        packet,
        key=lambda row: (row[worst_key] / row["price_inr"]) if row["price_inr"] else 0,
        reverse=True,
    )
    picked = []
    total = 0.0
    for row in ranked:
        if len(picked) >= 3:
            break
        if total + row["price_inr"] > BUDGET:
            continue
        picked.append(row["food_id"])
        total += row["price_inr"]
    return picked


def validate_choices(packet: list[dict], choices: list[dict]) -> tuple[list[dict], float]:
    by_id = {row["food_id"]: row for row in packet}
    kept = []
    total = 0.0
    seen = set()
    for choice in choices:
        food_id = str(choice.get("food_id") or "")
        row = by_id.get(food_id)
        if row is None or food_id in seen:
            continue
        if total + row["price_inr"] > BUDGET or len(kept) >= 3:
            continue
        seen.add(food_id)
        kept.append(
            {
                "food_id": row["food_id"],
                "name": row["name"],
                "price_inr": row["price_inr"],
                "reason": str(choice.get("reason") or "").strip()[:180],
            }
        )
        total += row["price_inr"]
    return kept, round(total, 2)


def _ask_model(packet: list[dict], gaps: list[dict], worst_key: str) -> list[dict]:
    from groq import Groq

    brief_gaps = [
        {"nutrient": row["label"], "percent_of_need": row["percent"], "likely_low": row["likely_low"]}
        for row in gaps
    ]
    brief_packet = [
        {
            "food_id": row["food_id"],
            "name": row["name"],
            "price_inr": row["price_inr"],
            **{key: row[key] for key in NUTRIENTS},
        }
        for row in packet
    ]
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    completion = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
        temperature=0.2,
        max_completion_tokens=500,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": (
                    "Choose foods that fill the weakest nutrient. "
                    'Reply with JSON only: {"choices":[{"food_id":"","reason":""}]}. '
                    "Use only food_id values from the packet. At most 3. "
                    "The sum of price_inr must be 30 or less. "
                    "reason is one short line about cost or pairing. "
                    "Do not invent foods or nutrient numbers."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"worst": worst_key, "gaps": brief_gaps, "packet": brief_packet}),
            },
        ],
    )
    payload = json.loads(completion.choices[0].message.content or "{}")
    return list(payload.get("choices") or [])


def choose(foods: tuple[Food, ...] | list[Food], diet: str, gaps: list[dict], worst_key: str) -> tuple[list[dict], float, str]:
    packet = candidate_packet(foods, diet)
    if not packet:
        return [], 0, "fallback"
    if os.environ.get("GROQ_API_KEY"):
        try:
            kept, total = validate_choices(packet, _ask_model(packet, gaps, worst_key))
            if kept:
                return kept, total, "groq"
        except Exception:
            pass
    by_id = {row["food_id"]: row for row in packet}
    kept = [
        {
            "food_id": food_id,
            "name": by_id[food_id]["name"],
            "price_inr": by_id[food_id]["price_inr"],
            "reason": "Highest amount of the weakest nutrient per rupee in the sheet.",
        }
        for food_id in fallback_ids(packet, worst_key)
    ]
    total = round(sum(item["price_inr"] for item in kept), 2)
    return kept, total, "fallback"
