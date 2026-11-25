from __future__ import annotations

from rapidfuzz import fuzz

from engine.foods import Food

ACCEPT = 85
UNCERTAIN = 70


def match_name(name: str, foods: tuple[Food, ...] | list[Food]) -> dict:
    query = " ".join(name.lower().split())
    best_food = None
    best_score = 0
    best_exact = 0
    for food in foods:
        labels = tuple(label.lower() for label in (food.name, *food.aliases))
        exact = 1 if query in labels else 0
        score = max(max(fuzz.token_set_ratio(query, label), fuzz.ratio(query, label)) for label in labels)
        if (exact, score) > (best_exact, best_score):
            best_exact = exact
            best_score = score
            best_food = food
    if best_food is None or best_score < UNCERTAIN:
        return {"status": "none", "score": best_score, "food": None}
    status = "ok" if best_score >= ACCEPT else "uncertain"
    return {"status": status, "score": best_score, "food": best_food}
