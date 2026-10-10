"""Progresión, solape, racha y estadísticas. Cálculo determinista."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import get_authenticated_user, resolve_target_user
from .database import get_connection

router = APIRouter(prefix="/api/progress", tags=["progress"])


def init_progress_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS exercise_progress (
            user_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            next_weight_kg REAL,
            reason TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, exercise_id)
        );
        CREATE TABLE IF NOT EXISTS exercise_flags (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            zone TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        );
        """
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(workout_logs)")}
    if "is_deload" not in cols:
        conn.execute("ALTER TABLE workout_logs ADD COLUMN is_deload INTEGER NOT NULL DEFAULT 0")
    conn.commit()
    conn.close()


def _epley(weight: float, reps: int) -> float:
    if weight <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30), 1)


def apply_progression(conn, user_id: str, workout_id: str) -> None:
    sets = conn.execute(
        """
        SELECT ws.exercise_id, ws.weight_kg, ws.reps, ws.rir, ws.is_warmup, e.name
        FROM workout_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE ws.workout_log_id = ?
        """,
        (workout_id,),
    ).fetchall()
    by_ex: dict[str, list] = {}
    for s in sets:
        by_ex.setdefault(s["exercise_id"], []).append(s)
    now = datetime.utcnow().isoformat(timespec="seconds")
    for eid, rows in by_ex.items():
        name = (rows[0]["name"] or "").strip().lower()
        work = [r for r in rows if not r["is_warmup"]]
        if not work or name == "plancha":
            continue
        routine = conn.execute(
            """
            SELECT re.target_rep_min, re.target_rep_max, re.target_rir, e.weight_increment_kg
            FROM workout_logs wl
            JOIN routine_exercises re ON re.routine_id = wl.routine_id AND re.exercise_id = ?
            JOIN exercises e ON e.id = re.exercise_id
            WHERE wl.id = ?
            """,
            (eid, workout_id),
        ).fetchone()
        last_w = max(r["weight_kg"] or 0 for r in work)
        inc = 2.5
        rep_min, rep_max, rir_target = 8, 12, 2
        if routine:
            rep_min = routine["target_rep_min"] or 8
            rep_max = routine["target_rep_max"] or 12
            rir_target = routine["target_rir"] if routine["target_rir"] is not None else 2
            inc = routine["weight_increment_kg"] or 2.5
        ok = all(
            (r["reps"] or 0) >= rep_min and (r["rir"] is None or r["rir"] >= rir_target)
            for r in work
        )
        if ok:
            nxt = round(last_w + inc, 2)
            reason = f"Cumpliste {rep_min}-{rep_max} a RIR {rir_target} → +{inc:g} kg"
        else:
            nxt = last_w
            reason = "No se cumplió el objetivo → misma carga"
        conn.execute(
            """
            INSERT INTO exercise_progress (user_id, exercise_id, next_weight_kg, reason, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, exercise_id) DO UPDATE SET
                next_weight_kg=excluded.next_weight_kg,
                reason=excluded.reason,
                updated_at=excluded.updated_at
            """,
            (user_id, eid, nxt, reason, now),
        )


def _overlap(conn, last_routine_id: str | None, next_routine_id: str | None) -> list[str]:
    if not last_routine_id or not next_routine_id:
        return []
    rows = conn.execute(
        """
        SELECT e.name
        FROM routine_exercises a
        JOIN routine_exercises b ON b.exercise_id = a.exercise_id
        JOIN exercises e ON e.id = a.exercise_id
        WHERE a.routine_id = ? AND b.routine_id = ?
        """,
        (last_routine_id, next_routine_id),
    ).fetchall()
    return [r["name"] for r in rows]


@router.get("/home")
def home(user_id: str, current_user=Depends(get_authenticated_user)):
    init_progress_db()
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    last = conn.execute(
        """
        SELECT id, routine_id, date, routine_id
        FROM workout_logs
        WHERE user_id = ? AND status = 'completed'
        ORDER BY date DESC LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    routines = conn.execute(
        "SELECT id, name FROM routines WHERE is_active = 1 AND user_id = ? ORDER BY name",
        (user_id,),
    ).fetchall()
    next_r = None
    if routines:
        if not last or not last["routine_id"]:
            next_r = routines[0]
        else:
            ids = [r["id"] for r in routines]
            try:
                i = ids.index(last["routine_id"])
                next_r = routines[(i + 1) % len(routines)]
            except ValueError:
                next_r = routines[0]
    overlap = _overlap(conn, last["routine_id"] if last else None, next_r["id"] if next_r else None)
    last_deload = conn.execute(
        """
        SELECT date FROM workout_logs
        WHERE user_id = ? AND status = 'completed' AND is_deload = 1
        ORDER BY date DESC LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    first = conn.execute(
        """
        SELECT date FROM workout_logs
        WHERE user_id = ? AND status = 'completed'
        ORDER BY date ASC LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    deload_due = False
    if first and first["date"]:
        try:
            start = datetime.fromisoformat(str(first["date"]).replace("Z", "")).date()
        except ValueError:
            start = date.today()
        trained_long_enough = (date.today() - start).days >= 42
        if trained_long_enough:
            if not last_deload or not last_deload["date"]:
                deload_due = True
            else:
                try:
                    d = datetime.fromisoformat(str(last_deload["date"]).replace("Z", "")).date()
                except ValueError:
                    d = date.today()
                deload_due = (date.today() - d).days >= 42
    since7 = (date.today() - timedelta(days=7)).isoformat()
    since28 = (date.today() - timedelta(days=28)).isoformat()
    try:
        streak7 = len({
            (r["d"] or "")[:10]
            for r in conn.execute(
                """
                SELECT date AS d FROM workout_logs
                WHERE user_id=? AND status='completed' AND substr(date,1,10)>=?
                UNION
                SELECT date AS d FROM activity_logs
                WHERE user_id=? AND substr(date,1,10)>=?
                """,
                (user_id, since7, user_id, since7),
            )
        })
        streak28 = len({
            (r["d"] or "")[:10]
            for r in conn.execute(
                """
                SELECT date AS d FROM workout_logs
                WHERE user_id=? AND status='completed' AND substr(date,1,10)>=?
                UNION
                SELECT date AS d FROM activity_logs
                WHERE user_id=? AND substr(date,1,10)>=?
                """,
                (user_id, since28, user_id, since28),
            )
        })
    except Exception:
        streak7 = len({
            (r["d"] or "")[:10]
            for r in conn.execute(
                "SELECT date AS d FROM workout_logs WHERE user_id=? AND status='completed' AND substr(date,1,10)>=?",
                (user_id, since7),
            )
        })
        streak28 = len({
            (r["d"] or "")[:10]
            for r in conn.execute(
                "SELECT date AS d FROM workout_logs WHERE user_id=? AND status='completed' AND substr(date,1,10)>=?",
                (user_id, since28),
            )
        })
    loads = {
        r["exercise_id"]: {"next_weight_kg": r["next_weight_kg"], "reason": r["reason"]}
        for r in conn.execute(
            "SELECT exercise_id, next_weight_kg, reason FROM exercise_progress WHERE user_id=?",
            (user_id,),
        )
    }
    flags = [
        dict(r)
        for r in conn.execute(
            "SELECT exercise_id, zone, note FROM exercise_flags WHERE user_id=? AND active=1",
            (user_id,),
        )
    ]
    conn.close()
    return {
        "last_workout_id": last["id"] if last else None,
        "next_routine_id": next_r["id"] if next_r else None,
        "next_routine_name": next_r["name"] if next_r else None,
        "overlap": overlap,
        "tomorrow": (
            f"Mañana: {next_r['name']}. Solapa: {', '.join(overlap)}."
            if next_r and overlap
            else f"Mañana: {next_r['name']}. Sin solape directo."
            if next_r
            else "Sin rutina activa."
        ),
        "deload_due": deload_due,
        "streak_7": streak7,
        "streak_28": streak28,
        "loads": loads,
        "flags": flags,
    }


@router.get("/stats")
def stats(user_id: str, current_user=Depends(get_authenticated_user)):
    init_progress_db()
    user_id = resolve_target_user(current_user, user_id)
    since = (date.today() - timedelta(days=7)).isoformat()
    conn = get_connection()
    volume = conn.execute(
        """
        SELECT e.target_muscle AS muscle, COUNT(*) AS sets
        FROM workout_sets ws
        JOIN workout_logs wl ON wl.id = ws.workout_log_id
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE wl.user_id = ? AND wl.status = 'completed'
          AND substr(wl.date,1,10) >= ? AND ws.is_warmup = 0
          AND lower(e.name) != 'plancha'
        GROUP BY e.target_muscle
        ORDER BY sets DESC
        """,
        (user_id, since),
    ).fetchall()
    best: dict[str, dict] = {}
    rows = conn.execute(
        """
        SELECT e.id, e.name, ws.weight_kg, ws.reps
        FROM workout_sets ws
        JOIN workout_logs wl ON wl.id = ws.workout_log_id
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE wl.user_id = ? AND wl.status = 'completed' AND ws.is_warmup = 0
          AND lower(e.name) != 'plancha' AND ws.weight_kg > 0
        """,
        (user_id,),
    ).fetchall()
    for r in rows:
        est = _epley(r["weight_kg"], r["reps"])
        cur = best.get(r["id"])
        if not cur or est > cur["e1rm"]:
            best[r["id"]] = {"exercise_id": r["id"], "name": r["name"], "e1rm": est}
    conn.close()
    return {
        "volume_7d": [dict(v) for v in volume],
        "e1rm": sorted(best.values(), key=lambda x: x["e1rm"], reverse=True)[:12],
    }


class FlagIn(BaseModel):
    exercise_id: str
    zone: str
    note: str | None = None


@router.post("/flag")
def add_flag(body: FlagIn, user_id: str, current_user=Depends(get_authenticated_user)):
    init_progress_db()
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    conn.execute(
        "INSERT INTO exercise_flags (id, user_id, exercise_id, zone, note, created_at, active) VALUES (?, ?, ?, ?, ?, ?, 1)",
        (str(uuid4()), user_id, body.exercise_id, body.zone.strip() or "otro", body.note, datetime.utcnow().isoformat(timespec="seconds")),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@router.post("/flag/clear")
def clear_flag(body: FlagIn, user_id: str, current_user=Depends(get_authenticated_user)):
    init_progress_db()
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    conn.execute(
        "UPDATE exercise_flags SET active=0 WHERE user_id=? AND exercise_id=?",
        (user_id, body.exercise_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}
