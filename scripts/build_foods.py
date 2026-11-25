"""Build data/platepal_foods.xlsx from a short INDB + IFCT extract.

The full workbooks are read from the temp paths used while researching.
They are not copied into the repo. Re-run only if those files are present.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

import openpyxl
from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "platepal_foods.xlsx"
INDB = Path(os.environ.get("INDB_XLSX", Path(os.environ["TEMP"]) / "INDB.xlsx"))
IFCT = Path(os.environ.get("IFCT_CSV", Path(os.environ["TEMP"]) / "ifct.csv"))

# USDA FoodData Central, SR Legacy, per 100 g. IFCT 2017 has no vitamin B12 column.
B12 = {
    "egg": 1.11,
    "milk": 0.45,
    "curd": 0.37,
    "chicken": 0.31,
}


def indb_rows() -> dict[str, dict]:
    wb = openpyxl.load_workbook(INDB, read_only=True, data_only=True)
    ws = wb.active
    header = [c for c in next(ws.iter_rows(max_row=1, values_only=True))]
    idx = {name: i for i, name in enumerate(header)}
    found = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        code = row[idx["food_code"]]
        if not code:
            continue
        protein = float(row[idx["protein_g"]] or 0)
        unit_protein = row[idx["unit_serving_protein_g"]]
        serving_g = None
        if protein > 0 and unit_protein:
            serving_g = round(float(unit_protein) / protein * 100, 1)
        found[code] = {
            "name_src": row[idx["food_name"]],
            "serving_name": row[idx["servings_unit"]] or "serving",
            "serving_g": serving_g,
            "protein_g": round(protein, 2),
            "iron_mg": round(float(row[idx["iron_mg"]] or 0), 2),
            "calcium_mg": round(float(row[idx["calcium_mg"]] or 0), 1),
            "folate_ug": round(float(row[idx["folate_ug"]] or 0), 1),
        }
    wb.close()
    return found


def ifct_rows() -> dict[str, dict]:
    with IFCT.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    keys = list(rows[0].keys())

    def key_starting(prefix: str) -> str:
        for key in keys:
            if key.startswith(prefix):
                return key
        raise KeyError(prefix)

    name_key = key_starting("Food Name")
    protein_key = key_starting("Protein; protcnt")
    iron_key = key_starting("Iron")
    calcium_key = key_starting("Calcium")
    folate_key = key_starting("Folates")
    found = {}
    for row in rows:
        found[row[name_key]] = {
            "protein_g": round(float(row[protein_key] or 0), 2),
            "iron_mg": round(float(row[iron_key] or 0) * 1000, 2),
            "calcium_mg": round(float(row[calcium_key] or 0) * 1000, 1),
            "folate_ug": round(float(row[folate_key] or 0) * 1_000_000, 1),
        }
    return found


def meal(code: str, table: dict, **meta) -> dict:
    src = table[code]
    row = {
        "food_id": meta["food_id"],
        "name": meta["name"],
        "aliases": meta["aliases"],
        "serving_name": meta.get("serving_name") or src["serving_name"],
        "serving_g": meta.get("serving_g") or src["serving_g"],
        "protein_g": src["protein_g"],
        "iron_mg": src["iron_mg"],
        "calcium_mg": src["calcium_mg"],
        "folate_ug": src["folate_ug"],
        "b12_ug": meta.get("b12_ug", ""),
        "diet": meta["diet"],
        "price_inr": meta["price_inr"],
        "kind": meta["kind"],
        "b12_source": meta.get("b12_source", ""),
        "nutrient_source": meta["nutrient_source"],
    }
    return row


def ifct_food(table: dict, ifct_name: str, **meta) -> dict:
    src = table[ifct_name]
    return {
        "food_id": meta["food_id"],
        "name": meta["name"],
        "aliases": meta["aliases"],
        "serving_name": meta["serving_name"],
        "serving_g": meta["serving_g"],
        "protein_g": src["protein_g"],
        "iron_mg": src["iron_mg"],
        "calcium_mg": src["calcium_mg"],
        "folate_ug": src["folate_ug"],
        "b12_ug": meta.get("b12_ug", ""),
        "diet": meta["diet"],
        "price_inr": meta["price_inr"],
        "kind": meta["kind"],
        "b12_source": meta.get("b12_source", ""),
        "nutrient_source": f"IFCT 2017: {ifct_name}",
    }


def build() -> list[dict]:
    indb = indb_rows()
    ifct = ifct_rows()
    rice = indb["ASC113"]
    dal = indb["ASC151"]
    pongal = {
        "protein_g": round(rice["protein_g"] * 0.7 + dal["protein_g"] * 0.3, 2),
        "iron_mg": round(rice["iron_mg"] * 0.7 + dal["iron_mg"] * 0.3, 2),
        "calcium_mg": round(rice["calcium_mg"] * 0.7 + dal["calcium_mg"] * 0.3, 1),
        "folate_ug": round(rice["folate_ug"] * 0.7 + dal["folate_ug"] * 0.3, 1),
    }
    chicken = indb["ASC240"]
    chicken_b12 = round(B12["chicken"] * (chicken["protein_g"] / ifct["Chicken, poultry, leg, skinless"]["protein_g"]), 2)

    rows = [
        meal("ASC144", indb, food_id="idli", name="Idli", aliases="idli,idly,idlies", diet="veg", price_inr=10, kind="meal", nutrient_source="INDB ASC144"),
        meal("ASC146", indb, food_id="dosa", name="Masala dosa", aliases="dosa,dosai,masala dosa", diet="veg", price_inr=40, kind="meal", nutrient_source="INDB ASC146"),
        meal("ASC167", indb, food_id="sambar", name="Sambar", aliases="sambar,sambhar,kuzhambu", diet="veg", price_inr=15, kind="meal", nutrient_source="INDB ASC167"),
        meal("BFP176", indb, food_id="rasam", name="Rasam", aliases="rasam,puli rasam", diet="veg", price_inr=10, kind="meal", nutrient_source="INDB BFP176"),
        meal("ASC113", indb, food_id="rice", name="Boiled rice", aliases="rice,boiled rice,chawal,sadham", diet="veg", price_inr=15, kind="meal", nutrient_source="INDB ASC113"),
        meal("ASC126", indb, food_id="curd_rice", name="Curd rice", aliases="curd rice,thayir sadam,dahi chawal", diet="veg", price_inr=25, kind="meal", nutrient_source="INDB ASC126"),
        meal("ASC124", indb, food_id="lemon_rice", name="Lemon rice", aliases="lemon rice,pulihora,elumichai sadam", diet="veg", price_inr=25, kind="meal", nutrient_source="INDB ASC124"),
        meal("ASC096", indb, food_id="chapati", name="Chapati", aliases="chapati,roti,phulka", diet="veg", price_inr=8, kind="meal", nutrient_source="INDB ASC096"),
        meal("BFP436", indb, food_id="vada", name="Medu vada", aliases="vada,medu vada,ulundu vadai", diet="veg", price_inr=15, kind="meal", nutrient_source="INDB BFP436"),
        meal("BFP153", indb, food_id="appam", name="Appam", aliases="appam,aappam", diet="veg", price_inr=15, kind="meal", nutrient_source="INDB BFP153"),
        meal("BFP039", indb, food_id="upma", name="Rava upma", aliases="upma,rava upma,uppuma", diet="veg", price_inr=20, kind="meal", nutrient_source="INDB BFP039"),
        meal("OSR105", indb, food_id="puttu", name="Rice puttu", aliases="puttu,ari puttu", diet="veg", price_inr=20, kind="meal", nutrient_source="INDB OSR105"),
        meal("ASC151", indb, food_id="moong_dal", name="Moong dal", aliases="moong dal,dal,paruppu,kootu", diet="veg", price_inr=15, kind="meal", nutrient_source="INDB ASC151"),
        meal("ASC215", indb, food_id="palak_paneer", name="Palak paneer", aliases="palak paneer,spinach paneer", diet="veg", price_inr=40, kind="meal", nutrient_source="INDB ASC215"),
        meal("BFP257", indb, food_id="poriyal", name="Potato spinach poriyal", aliases="poriyal,keerai poriyal,palak aloo", diet="veg", price_inr=20, kind="meal", nutrient_source="INDB BFP257"),
        {
            "food_id": "pongal",
            "name": "Ven pongal",
            "aliases": "pongal,ven pongal",
            "serving_name": "bowl",
            "serving_g": 200,
            "protein_g": pongal["protein_g"],
            "iron_mg": pongal["iron_mg"],
            "calcium_mg": pongal["calcium_mg"],
            "folate_ug": pongal["folate_ug"],
            "b12_ug": "",
            "diet": "veg",
            "price_inr": 25,
            "kind": "meal",
            "b12_source": "",
            "nutrient_source": "Derived 70% INDB boiled rice ASC113 + 30% INDB moong dal ASC151",
        },
        meal(
            "ASC240",
            indb,
            food_id="chicken_curry",
            name="Chicken curry",
            aliases="chicken curry,chicken",
            diet="nonveg",
            price_inr=60,
            kind="meal",
            b12_ug=chicken_b12,
            b12_source="USDA chicken meat, scaled by protein share of this curry",
            nutrient_source="INDB ASC240",
        ),
        meal("ASC246", indb, food_id="fish_curry", name="Fish curry", aliases="fish curry,meen kuzhambu,fish", diet="nonveg", price_inr=60, kind="meal", b12_source="not in INDB or IFCT", nutrient_source="INDB ASC246"),
        meal("ASC061", indb, food_id="omelette", name="Omelette", aliases="omelette,omlet,egg omelette", diet="egg", price_inr=20, kind="meal", b12_ug=B12["egg"], b12_source="USDA hard-boiled egg, applied per 100 g", nutrient_source="INDB ASC061"),
        ifct_food(ifct, "Amaranth leaves, green", food_id="amaranth", name="Amaranth leaves", aliases="amaranth,keerai,thotakura,chaulai", serving_name="bunch", serving_g=100, diet="veg", price_inr=20, kind="filler"),
        ifct_food(ifct, "Spinach", food_id="spinach", name="Spinach", aliases="spinach,palak", serving_name="bunch", serving_g=100, diet="veg", price_inr=15, kind="filler"),
        ifct_food(ifct, "Lemon, juice", food_id="lemon", name="Lemon", aliases="lemon,nimbu,elumichai", serving_name="lemon", serving_g=20, diet="veg", price_inr=5, kind="filler"),
        ifct_food(ifct, "Bengal gram, whole", food_id="roasted_chana", name="Roasted chana", aliases="roasted chana,chana,sundal,bengal gram", serving_name="handful", serving_g=30, diet="veg", price_inr=10, kind="filler"),
        ifct_food(ifct, "Banana, ripe, robusta", food_id="banana", name="Banana", aliases="banana,vazhapazham", serving_name="banana", serving_g=100, diet="veg", price_inr=5, kind="filler"),
        ifct_food(ifct, "Gingelly seeds, white", food_id="sesame", name="Sesame seeds", aliases="sesame,til,ellu", serving_name="spoon", serving_g=10, diet="veg", price_inr=4, kind="filler"),
        ifct_food(ifct, "Milk, whole, Cow", food_id="milk", name="Cow milk", aliases="milk,doodh,paal", serving_name="glass", serving_g=200, diet="veg", price_inr=15, kind="filler", b12_ug=B12["milk"], b12_source="USDA whole milk per 100 g"),
        ifct_food(ifct, "Milk, whole, Cow", food_id="curd", name="Curd", aliases="curd,dahi,thayir,yogurt", serving_name="cup", serving_g=150, diet="veg", price_inr=12, kind="filler", b12_ug=B12["curd"], b12_source="USDA plain yogurt per 100 g; macros are IFCT cow milk"),
        ifct_food(ifct, "Egg, poultry, whole, boiled", food_id="boiled_egg", name="Boiled egg", aliases="boiled egg,egg,anda", serving_name="egg", serving_g=50, diet="egg", price_inr=8, kind="filler", b12_ug=B12["egg"], b12_source="USDA hard-boiled egg per 100 g"),
        ifct_food(ifct, "Mackerel", food_id="mackerel", name="Mackerel", aliases="mackerel,ayala", serving_name="piece", serving_g=80, diet="nonveg", price_inr=25, kind="filler", b12_source="not in IFCT"),
    ]
    overrides = {"puttu": 150}
    for row in rows:
        if row["food_id"] in overrides:
            row["serving_g"] = overrides[row["food_id"]]
            row["nutrient_source"] += "; serving grams set to a typical portion"
        if row["serving_g"] is None or row["serving_g"] < 10 or row["serving_g"] > 400:
            raise SystemExit(f"Bad serving for {row['food_id']}: {row['serving_g']}")
    return rows


def write(rows: list[dict]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()
    foods = wb.active
    foods.title = "foods"
    columns = [
        "food_id",
        "name",
        "aliases",
        "serving_name",
        "serving_g",
        "protein_g",
        "iron_mg",
        "calcium_mg",
        "folate_ug",
        "b12_ug",
        "diet",
        "price_inr",
        "kind",
        "b12_source",
        "nutrient_source",
    ]
    foods.append(columns)
    for row in rows:
        foods.append([row.get(col, "") for col in columns])

    targets = wb.create_sheet("targets")
    targets.append(
        [
            "sex",
            "protein_g_per_kg",
            "iron_mg",
            "calcium_mg",
            "folate_ug",
            "b12_ug",
            "ear_fraction",
            "reference_weight_kg",
        ]
    )
    targets.append(["man", 0.83, 19, 1000, 300, 2.2, 0.8, 65])
    targets.append(["woman", 0.83, 29, 1000, 220, 2.2, 0.8, 55])

    notes = wb.create_sheet("notes")
    notes.append(["note"])
    notes.append(
        [
            "Cooked dishes are a short extract of the Indian Nutrient Databank (Vijayakumar et al. 2024). "
            "Raw fillers are IFCT 2017 per 100 g. Vitamin B12 is absent from both tables and is filled only "
            "where b12_source names a USDA value. Prices are rough local estimates per serving. "
            "Pongal is 70% boiled rice and 30% moong dal from INDB, not a published pongal row."
        ]
    )
    wb.save(OUT)
    print(f"wrote {OUT} rows={len(rows)}")
    for row in rows:
        print(f"{row['food_id']:16} {row['serving_g']:7} g  Fe {row['iron_mg']}")


if __name__ == "__main__":
    write(build())
