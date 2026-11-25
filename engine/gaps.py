from __future__ import annotations

from engine.foods import LABELS, NUTRIENTS, Target


def rda_for(sex: str, weight_kg: float | None, targets: dict[str, Target]) -> tuple[dict[str, float], float]:
    target = targets[sex]
    weight = weight_kg or target.reference_weight_kg
    rda = {
        "protein_g": round(target.protein_g_per_kg * weight, 2),
        "iron_mg": target.iron_mg,
        "calcium_mg": target.calcium_mg,
        "folate_ug": target.folate_ug,
        "b12_ug": target.b12_ug,
    }
    return rda, target.ear_fraction


def scale(nutrients: dict[str, float], count: float) -> dict[str, float]:
    return {key: round(float(nutrients.get(key) or 0) * count, 2) for key in NUTRIENTS}


def add(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {key: round(float(left.get(key) or 0) + float(right.get(key) or 0), 2) for key in NUTRIENTS}


def empty() -> dict[str, float]:
    return {key: 0.0 for key in NUTRIENTS}


def compare(consumed: dict[str, float], rda: dict[str, float], ear_fraction: float) -> tuple[list[dict], str]:
    rows = []
    for key in NUTRIENTS:
        target = float(rda[key])
        have = float(consumed.get(key) or 0)
        percent = round(100 * have / target, 1) if target else 0
        rows.append(
            {
                "nutrient": key,
                "label": LABELS[key],
                "consumed": round(have, 2),
                "rda": target,
                "percent": percent,
                "likely_low": have < target * ear_fraction,
            }
        )
    worst = min(rows, key=lambda row: row["percent"])["nutrient"]
    return rows, worst
