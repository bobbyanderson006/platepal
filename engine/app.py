from __future__ import annotations

import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from engine.foods import foods_by_id, load
from engine.gaps import add, compare, empty, rda_for, scale
from engine.match import match_name
from engine.parse import parse_meal
from engine.store import get_profile, init_db, pop_pending, save_meal, save_pending, save_profile, today_nutrients
from engine.suggest import choose

load_dotenv()


class ProfileIn(BaseModel):
    telegram_user_id: str
    sex: str = Field(pattern="^(man|woman)$")
    diet: str = Field(pattern="^(veg|egg|nonveg)$")
    weight_kg: float | None = Field(default=None, ge=30, le=200)


class MealTextIn(BaseModel):
    telegram_user_id: str
    text: str = Field(min_length=1, max_length=500)


class ConfirmIn(BaseModel):
    telegram_user_id: str
    pending_id: str


def _check_key(x_api_key: str | None) -> None:
    expected = os.environ.get("ENGINE_KEY")
    if not expected or x_api_key != expected:
        raise HTTPException(status_code=401, detail="Missing or wrong API key")


def _profile_or_404(telegram_user_id: str) -> dict:
    profile = get_profile(telegram_user_id)
    if profile is None:
        raise HTTPException(status_code=409, detail="Set a profile before logging a meal")
    return profile


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    load()
    yield


app = FastAPI(title="PlatePal", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/profile")
def profile(body: ProfileIn, x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    save_profile(body.telegram_user_id, body.sex, body.weight_kg, body.diet)
    return {"ok": True}


@app.post("/meals/text")
def meals_text(body: MealTextIn, x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    _profile_or_404(body.telegram_user_id)
    foods, _targets = load()
    by_id = foods_by_id()
    parsed, parser = parse_meal(body.text)
    items = []
    unmatched = []
    uncertain = False
    for piece in parsed:
        found = match_name(piece["name"], foods)
        if found["food"] is None:
            unmatched.append(piece["name"])
            continue
        food = by_id[found["food"].food_id]
        count = float(piece["count"])
        nutrients = scale(food.per_serving(), count)
        uncertain = uncertain or found["status"] != "ok"
        items.append(
            {
                "food_id": food.food_id,
                "name": food.name,
                "count": count,
                "serving_name": food.serving_name,
                "score": found["score"],
                "status": found["status"],
                "nutrients": nutrients,
            }
        )
    if not items:
        raise HTTPException(status_code=422, detail={"unmatched": unmatched or [body.text]})
    pending_id = save_pending(
        body.telegram_user_id,
        {"items": items, "unmatched": unmatched, "parser": parser},
    )
    return {
        "pending_id": pending_id,
        "items": items,
        "unmatched": unmatched,
        "uncertain": uncertain,
        "parser": parser,
    }


@app.post("/meals/confirm")
def meals_confirm(body: ConfirmIn, x_api_key: str | None = Header(default=None)):
    _check_key(x_api_key)
    profile = _profile_or_404(body.telegram_user_id)
    pending = pop_pending(body.telegram_user_id, body.pending_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="That meal is no longer waiting")
    meal_total = empty()
    for item in pending["items"]:
        meal_total = add(meal_total, item["nutrients"])
    day_total = add(today_nutrients(body.telegram_user_id), meal_total)
    foods, targets = load()
    rda, ear_fraction = rda_for(profile["sex"], profile["weight_kg"], targets)
    gaps, worst = compare(day_total, rda, ear_fraction)
    suggestions, total_price, suggester = choose(foods, profile["diet"], gaps, worst)
    save_meal(body.telegram_user_id, pending["items"], meal_total)
    return {
        "gaps": gaps,
        "worst": worst,
        "suggestions": suggestions,
        "total_price": total_price,
        "suggester": suggester,
        "note": "Estimate from a food table, not a diagnosis.",
    }
