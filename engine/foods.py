from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
XLSX = Path(os.environ.get("PLATEPAL_XLSX", ROOT / "data" / "platepal_foods.xlsx"))

NUTRIENTS = ("protein_g", "iron_mg", "calcium_mg", "folate_ug", "b12_ug")
LABELS = {
    "protein_g": "protein",
    "iron_mg": "iron",
    "calcium_mg": "calcium",
    "folate_ug": "folate",
    "b12_ug": "B12",
}


@dataclass(frozen=True)
class Food:
    food_id: str
    name: str
    aliases: tuple[str, ...]
    serving_name: str
    serving_g: float
    protein_g: float
    iron_mg: float
    calcium_mg: float
    folate_ug: float
    b12_ug: float | None
    diet: str
    price_inr: float
    kind: str
    b12_source: str
    nutrient_source: str

    def per_serving(self) -> dict[str, float]:
        factor = self.serving_g / 100
        return {
            "protein_g": round(self.protein_g * factor, 2),
            "iron_mg": round(self.iron_mg * factor, 2),
            "calcium_mg": round(self.calcium_mg * factor, 1),
            "folate_ug": round(self.folate_ug * factor, 1),
            "b12_ug": round((self.b12_ug or 0) * factor, 2),
        }


@dataclass(frozen=True)
class Target:
    sex: str
    protein_g_per_kg: float
    iron_mg: float
    calcium_mg: float
    folate_ug: float
    b12_ug: float
    ear_fraction: float
    reference_weight_kg: float


def _blank_number(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


@lru_cache(maxsize=1)
def load() -> tuple[tuple[Food, ...], dict[str, Target]]:
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    foods_sheet = wb["foods"]
    rows = foods_sheet.iter_rows(values_only=True)
    header = [str(cell) for cell in next(rows)]
    index = {name: i for i, name in enumerate(header)}
    foods = []
    for row in rows:
        if not row[index["food_id"]]:
            continue
        alias_text = row[index["aliases"]] or ""
        foods.append(
            Food(
                food_id=str(row[index["food_id"]]),
                name=str(row[index["name"]]),
                aliases=tuple(part.strip() for part in str(alias_text).split(",") if part.strip()),
                serving_name=str(row[index["serving_name"]]),
                serving_g=float(row[index["serving_g"]]),
                protein_g=float(row[index["protein_g"]]),
                iron_mg=float(row[index["iron_mg"]]),
                calcium_mg=float(row[index["calcium_mg"]]),
                folate_ug=float(row[index["folate_ug"]]),
                b12_ug=_blank_number(row[index["b12_ug"]]),
                diet=str(row[index["diet"]]),
                price_inr=float(row[index["price_inr"]]),
                kind=str(row[index["kind"]]),
                b12_source=str(row[index["b12_source"]] or ""),
                nutrient_source=str(row[index["nutrient_source"]] or ""),
            )
        )
    targets = {}
    target_rows = wb["targets"].iter_rows(values_only=True)
    target_header = [str(cell) for cell in next(target_rows)]
    target_index = {name: i for i, name in enumerate(target_header)}
    for row in target_rows:
        if not row[target_index["sex"]]:
            continue
        sex = str(row[target_index["sex"]])
        targets[sex] = Target(
            sex=sex,
            protein_g_per_kg=float(row[target_index["protein_g_per_kg"]]),
            iron_mg=float(row[target_index["iron_mg"]]),
            calcium_mg=float(row[target_index["calcium_mg"]]),
            folate_ug=float(row[target_index["folate_ug"]]),
            b12_ug=float(row[target_index["b12_ug"]]),
            ear_fraction=float(row[target_index["ear_fraction"]]),
            reference_weight_kg=float(row[target_index["reference_weight_kg"]]),
        )
    wb.close()
    return tuple(foods), targets


def foods_by_id() -> dict[str, Food]:
    foods, _ = load()
    return {food.food_id: food for food in foods}
