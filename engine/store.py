from __future__ import annotations

import json
import os
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

from engine.foods import NUTRIENTS, ROOT

DB_PATH = Path(os.environ.get("PLATEPAL_DB", ROOT / "data" / "platepal.db"))


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                telegram_user_id TEXT PRIMARY KEY,
                sex TEXT NOT NULL,
                weight_kg REAL,
                diet TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS pending (
                id TEXT PRIMARY KEY,
                telegram_user_id TEXT NOT NULL,
                payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id TEXT NOT NULL,
                eaten_on TEXT NOT NULL,
                items TEXT NOT NULL,
                nutrients TEXT NOT NULL
            );
            """
        )


def save_profile(telegram_user_id: str, sex: str, weight_kg: float | None, diet: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO profiles (telegram_user_id, sex, weight_kg, diet)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                sex=excluded.sex, weight_kg=excluded.weight_kg, diet=excluded.diet
            """,
            (telegram_user_id, sex, weight_kg, diet),
        )


def get_profile(telegram_user_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT telegram_user_id, sex, weight_kg, diet FROM profiles WHERE telegram_user_id = ?",
            (telegram_user_id,),
        ).fetchone()
    if row is None:
        return None
    return dict(row)


def save_pending(telegram_user_id: str, payload: dict) -> str:
    pending_id = uuid4().hex[:8]
    with connect() as conn:
        conn.execute(
            "INSERT INTO pending (id, telegram_user_id, payload) VALUES (?, ?, ?)",
            (pending_id, telegram_user_id, json.dumps(payload)),
        )
    return pending_id


def pop_pending(telegram_user_id: str, pending_id: str) -> dict | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT payload FROM pending WHERE id = ? AND telegram_user_id = ?",
            (pending_id, telegram_user_id),
        ).fetchone()
        if row is None:
            return None
        conn.execute("DELETE FROM pending WHERE id = ?", (pending_id,))
    return json.loads(row["payload"])


def today_nutrients(telegram_user_id: str, eaten_on: str | None = None) -> dict[str, float]:
    eaten_on = eaten_on or date.today().isoformat()
    total = {key: 0.0 for key in NUTRIENTS}
    with connect() as conn:
        rows = conn.execute(
            "SELECT nutrients FROM meals WHERE telegram_user_id = ? AND eaten_on = ?",
            (telegram_user_id, eaten_on),
        ).fetchall()
    for row in rows:
        nutrients = json.loads(row["nutrients"])
        for key in NUTRIENTS:
            total[key] = round(total[key] + float(nutrients.get(key) or 0), 2)
    return total


def save_meal(telegram_user_id: str, items: list[dict], nutrients: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meals (telegram_user_id, eaten_on, items, nutrients) VALUES (?, ?, ?, ?)",
            (telegram_user_id, date.today().isoformat(), json.dumps(items), json.dumps(nutrients)),
        )
