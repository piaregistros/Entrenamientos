from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user
from .database import get_connection
from .diet_catalog import GOALS, RECIPES, recipe_by_id
from .diet_engine import build_week, shopping_list

router = APIRouter(prefix="/api/diet", tags=["diet"])


def init_diet_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS diet_profiles (
            user_id TEXT PRIMARY KEY,
            goal TEXT NOT NULL DEFAULT 'recomp',
            meals_per_day INTEGER NOT NULL DEFAULT 4,
            weight_kg REAL,
            notes TEXT,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS diet_week_plans (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            week_start TEXT NOT NULL,
            payload TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE (user_id, week_start)
        );
        CREATE TABLE IF NOT EXISTS diet_meal_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            recipe_id TEXT,
            slot TEXT,
            eaten INTEGER NOT NULL DEFAULT 1,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_diet_logs_user_date ON diet_meal_logs(user_id, date);
        """
    )
    conn.commit()
    conn.close()


class DietProfileIn(BaseModel):
    goal: str = "recomp"
    meals_per_day: int = Field(default=4, ge=3, le=5)
    weight_kg: float | None = Field(default=None, ge=40, le=180)
    notes: str | None = None


class MealLogIn(BaseModel):
    date: str
    recipe_id: str | None = None
    slot: str | None = None
    eaten: bool = True
    notes: str | None = None


def _monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _latest_weight(conn, user_id: str):
    row = conn.execute("SELECT weight_kg FROM body_metrics WHERE user_id=? ORDER BY date DESC LIMIT 1", (user_id,)).fetchone()
    return float(row["weight_kg"]) if row and row["weight_kg"] else None


def _routines(conn, user_id: str):
    rows = conn.execute("SELECT id, name, day_order, is_active FROM routines WHERE user_id=? AND is_active=1 ORDER BY day_order", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def _profile_row(conn, user_id: str) -> dict:
    row = conn.execute("SELECT * FROM diet_profiles WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "goal": "recomp", "meals_per_day": 4, "weight_kg": _latest_weight(conn, user_id), "notes": None}
    data = dict(row)
    if data.get("weight_kg") is None:
        data["weight_kg"] = _latest_weight(conn, user_id)
    return data


def _generate_and_store(conn, user_id: str, week_start: date, profile: dict) -> dict:
    week = build_week(
        week_start=week_start,
        goal_id=profile.get("goal") or "recomp",
        weight_kg=float(profile.get("weight_kg") or 75.0),
        routines=_routines(conn, user_id),
        meals_per_day=int(profile.get("meals_per_day") or 4),
    )
    conn.execute(
        """INSERT INTO diet_week_plans(id, user_id, week_start, payload) VALUES(?,?,?,?)
           ON CONFLICT(user_id, week_start) DO UPDATE SET payload=excluded.payload""",
        (str(uuid4()), user_id, week_start.isoformat(), json.dumps(week, ensure_ascii=False)),
    )
    conn.commit()
    return week


@router.get("/goals")
def list_goals(current_user=Depends(get_authenticated_user)):
    init_diet_db()
    return {"goals": list(GOALS.values()), "forbidden": ["cerdo", "marisco", "pescado"]}


@router.get("/recipes")
def list_recipes(slot: str | None = None, current_user=Depends(get_authenticated_user)):
    items = RECIPES if not slot else [r for r in RECIPES if r["slot"] == slot]
    return {"recipes": items}


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: str, current_user=Depends(get_authenticated_user)):
    item = recipe_by_id(recipe_id)
    if not item:
        raise HTTPException(404, "Receta no encontrada")
    return item


@router.get("/profile")
def get_profile(current_user=Depends(get_authenticated_user)):
    init_diet_db()
    conn = get_connection()
    try:
        return _profile_row(conn, current_user["id"])
    finally:
        conn.close()


@router.put("/profile")
def put_profile(body: DietProfileIn, current_user=Depends(get_authenticated_user)):
    init_diet_db()
    if body.goal not in GOALS:
        raise HTTPException(400, "Objetivo no valido")
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO diet_profiles(user_id, goal, meals_per_day, weight_kg, notes, updated_at)
               VALUES(?,?,?,?,?,CURRENT_TIMESTAMP)
               ON CONFLICT(user_id) DO UPDATE SET goal=excluded.goal, meals_per_day=excluded.meals_per_day,
               weight_kg=excluded.weight_kg, notes=excluded.notes, updated_at=CURRENT_TIMESTAMP""",
            (current_user["id"], body.goal, body.meals_per_day, body.weight_kg, body.notes),
        )
        conn.commit()
        return _profile_row(conn, current_user["id"])
    finally:
        conn.close()


@router.get("/week")
def get_week(start: str | None = None, current_user=Depends(get_authenticated_user)):
    init_diet_db()
    week_start = _monday(date.fromisoformat(start) if start else date.today())
    conn = get_connection()
    try:
        row = conn.execute("SELECT payload FROM diet_week_plans WHERE user_id=? AND week_start=?", (current_user["id"], week_start.isoformat())).fetchone()
        if row:
            return json.loads(row["payload"])
        return _generate_and_store(conn, current_user["id"], week_start, _profile_row(conn, current_user["id"]))
    finally:
        conn.close()


@router.post("/week/generate")
def regenerate_week(start: str | None = None, current_user=Depends(get_authenticated_user)):
    init_diet_db()
    week_start = _monday(date.fromisoformat(start) if start else date.today())
    conn = get_connection()
    try:
        return _generate_and_store(conn, current_user["id"], week_start, _profile_row(conn, current_user["id"]))
    finally:
        conn.close()


@router.get("/today")
def get_today(current_user=Depends(get_authenticated_user)):
    week = get_week(date.today().isoformat(), current_user)
    today = date.today().isoformat()
    day = next((d for d in week["days"] if d["date"] == today), week["days"][0])
    return {"week_start": week["week_start"], "goal": week["goal"], "day": day}


@router.get("/shopping-list")
def get_shopping(start: str | None = None, current_user=Depends(get_authenticated_user)):
    week = get_week(start, current_user)
    return {"week_start": week["week_start"], "items": shopping_list(week)}


@router.post("/log")
def log_meal(body: MealLogIn, current_user=Depends(get_authenticated_user)):
    init_diet_db()
    try:
        date.fromisoformat(body.date)
    except ValueError:
        raise HTTPException(400, "Fecha invalida")
    conn = get_connection()
    try:
        log_id = str(uuid4())
        conn.execute(
            "INSERT INTO diet_meal_logs(id, user_id, date, recipe_id, slot, eaten, notes) VALUES(?,?,?,?,?,?,?)",
            (log_id, current_user["id"], body.date, body.recipe_id, body.slot, 1 if body.eaten else 0, body.notes),
        )
        conn.commit()
        return {"id": log_id, "ok": True}
    finally:
        conn.close()


@router.get("/log")
def list_logs(day: str | None = None, current_user=Depends(get_authenticated_user)):
    init_diet_db()
    conn = get_connection()
    try:
        if day:
            rows = conn.execute("SELECT * FROM diet_meal_logs WHERE user_id=? AND date=? ORDER BY created_at", (current_user["id"], day)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM diet_meal_logs WHERE user_id=? ORDER BY date DESC LIMIT 40", (current_user["id"],)).fetchall()
        return {"logs": [dict(r) for r in rows]}
    finally:
        conn.close()
