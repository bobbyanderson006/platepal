from engine.foods import foods_by_id, load
from engine.gaps import compare, scale
from engine.match import match_name
from engine.parse import fallback_parse
from engine.suggest import candidate_packet, fallback_ids, validate_choices


def test_idli_alias_and_two_servings():
    foods, _targets = load()
    found = match_name("idly", foods)
    assert found["status"] == "ok"
    assert found["food"].food_id == "idli"
    one = found["food"].per_serving()
    two = scale(one, 2)
    assert two["protein_g"] == round(one["protein_g"] * 2, 2)
    assert two["iron_mg"] > 0


def test_egg_matches_boiled_egg_not_omelette():
    foods, _targets = load()
    found = match_name("egg", foods)
    assert found["food"].food_id == "boiled_egg"


def test_unknown_food_is_rejected():
    foods, _targets = load()
    found = match_name("xylophone", foods)
    assert found["status"] == "none"


def test_woman_iron_below_average_requirement_is_likely_low():
    _foods, targets = load()
    woman = targets["woman"]
    consumed = {"protein_g": 40, "iron_mg": 1, "calcium_mg": 800, "folate_ug": 200, "b12_ug": 2}
    rda = {
        "protein_g": woman.protein_g_per_kg * woman.reference_weight_kg,
        "iron_mg": woman.iron_mg,
        "calcium_mg": woman.calcium_mg,
        "folate_ug": woman.folate_ug,
        "b12_ug": woman.b12_ug,
    }
    rows, _worst = compare(consumed, rda, woman.ear_fraction)
    iron = next(row for row in rows if row["nutrient"] == "iron_mg")
    assert iron["rda"] == 29
    assert iron["likely_low"] is True
    assert iron["percent"] < 80


def test_veg_packet_skips_egg_and_fish():
    foods, _targets = load()
    packet = candidate_packet(foods, "veg")
    ids = {row["food_id"] for row in packet}
    assert "amaranth" in ids
    assert "boiled_egg" not in ids
    assert "mackerel" not in ids


def test_fallback_stays_within_budget_and_ranks_iron():
    foods, _targets = load()
    packet = candidate_packet(foods, "veg")
    picked = fallback_ids(packet, "iron_mg")
    by_id = {row["food_id"]: row for row in packet}
    assert picked[0] == "sesame"
    assert sum(by_id[food_id]["price_inr"] for food_id in picked) <= 30
    assert len(picked) <= 3


def test_validate_drops_unknown_foods():
    packet = [
        {"food_id": "lemon", "name": "Lemon", "price_inr": 5},
        {"food_id": "amaranth", "name": "Amaranth leaves", "price_inr": 20},
    ]
    kept, total = validate_choices(
        packet,
        [
            {"food_id": "not-real", "reason": "no"},
            {"food_id": "lemon", "reason": "vitamin C with iron"},
            {"food_id": "amaranth", "reason": "iron"},
        ],
    )
    assert [item["food_id"] for item in kept] == ["lemon", "amaranth"]
    assert total == 25


def test_fallback_parse_splits_a_typed_meal():
    items = fallback_parse("2 idli and sambar")
    assert items == [{"name": "idli", "count": 2.0}, {"name": "sambar", "count": 1.0}]


def test_sheet_has_targets_and_fillers():
    foods, targets = load()
    assert set(targets) == {"man", "woman"}
    assert targets["man"].iron_mg == 19
    assert targets["woman"].iron_mg == 29
    assert len(foods_by_id()) >= 29
