"""Progresión, solape, racha y estadísticas. Cálculo determinista."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import get_authenticated_user, resolve_target_user
from .database import get_connection
from .progression_db import compute_exercise_target, ensure_progress_extra_columns
from .stagnation import list_stagnated_exercises
from .charts import exercise_history, weekly_volume, RANGE_DAYS, clamp_weeks
from .warmup import suggest_warmup

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
    ensure_progress_extra_columns(conn)
    conn.commit()
    conn.close()


def _epley(weight: float, reps: int) -> float:
    if weight <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return weight
    return round(weight * (1 + reps / 30), 1)


def apply_progression(conn, user_id: str, workout_id: str, only: set | None = None) -> None:
    """Guarda en exercise_progress el siguiente objetivo de cada ejercicio del entreno.

    Fase 6: usa la MISMA doble progresión que /recommendations (app/progression.py).
    Los entrenos de deload no mueven la progresión.
    """
    wl = conn.execute("SELECT status, is_deload FROM workout_logs WHERE id = ?", (workout_id,)).fetchone()
    if wl and wl["is_deload"]:
        return
    exercise_ids = [
        r["exercise_id"]
        for r in conn.execute(
            """
            SELECT DISTINCT ws.exercise_id
            FROM workout_sets ws
            WHERE ws.workout_log_id = ? AND COALESCE(ws.is_warmup, 0) = 0
            """,
            (workout_id,),
        )
    ]
    now = datetime.utcnow().isoformat(timespec="seconds")
    ensure_progress_extra_columns(conn)
    for eid in exercise_ids:
        if only is not None and eid not in only:
            continue
        result, _cfg = compute_exercise_target(
            conn, user_id, eid, workout_id=workout_id, until_workout_id=workout_id
        )
        if result["kind"] == "start":
            continue  # sin series de trabajo válidas: nada que guardar
        conn.execute(
            """
            INSERT INTO exercise_progress
                (user_id, exercise_id, next_weight_kg, reason, updated_at,
                 next_reps, kind, fail_streak, measure_type, source_workout_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, exercise_id) DO UPDATE SET
                next_weight_kg=excluded.next_weight_kg,
                reason=excluded.reason,
                updated_at=excluded.updated_at,
                next_reps=excluded.next_reps,
                kind=excluded.kind,
                fail_streak=excluded.fail_streak,
                measure_type=excluded.measure_type,
                source_workout_id=excluded.source_workout_id
            """,
            (
                user_id, eid, result["weight_kg"], result["reason"], now,
                result["reps"], result["kind"], result["fail_streak"], result["measure_type"], workout_id,
            ),
        )


def _ensure_progress_tables(conn) -> None:
    """Crea exercise_progress sobre la MISMA conexión si aún no existe.

    Se usa desde rutas de escritura (borrar/editar entrenos) para no abrir una
    segunda conexión mientras hay una transacción pendiente.
    """
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='exercise_progress'"
    ).fetchone()
    if not exists:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exercise_progress (
                user_id TEXT NOT NULL,
                exercise_id TEXT NOT NULL,
                next_weight_kg REAL,
                reason TEXT,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (user_id, exercise_id)
            )
            """
        )
    ensure_progress_extra_columns(conn)


def recompute_exercise_progress(conn, user_id: str, exercise_ids) -> None:
    """Recalcula exercise_progress de esos ejercicios desde el historial real.

    Para cada ejercicio: se borra su fila y, si todavía existe algún entreno
    COMPLETADO con series de trabajo de ese ejercicio, se vuelve a derivar de
    el más reciente. Si no queda ninguno, el ejercicio vuelve a "sin historial".
    No hace commit: lo hace quien llama (misma transacción que el borrado).
    """
    ids = {e for e in (exercise_ids or []) if e}
    if not ids:
        return
    _ensure_progress_tables(conn)
    for eid in ids:
        conn.execute(
            "DELETE FROM exercise_progress WHERE user_id = ? AND exercise_id = ?",
            (user_id, eid),
        )
        latest = conn.execute(
            """
            SELECT wl.id
            FROM workout_logs wl
            JOIN workout_sets ws ON ws.workout_log_id = wl.id
            WHERE wl.user_id = ?
              AND wl.status = 'completed'
              AND ws.exercise_id = ?
              AND ws.is_warmup = 0
              AND COALESCE(wl.is_deload, 0) = 0
            ORDER BY datetime(wl.date) DESC, wl.id DESC
            LIMIT 1
            """,
            (user_id, eid),
        ).fetchone()
        if latest:
            apply_progression(conn, user_id, latest["id"], only={eid})


def rebuild_all_progress(conn, user_id: str | None = None) -> dict:
    """Reconstruye TODA la tabla exercise_progress desde el historial.

    Sirve para limpiar estados obsoletos que dejaron borrados anteriores.
    Devuelve {"antes": n, "despues": m, "cambios": [...]} (sin commit).
    """
    _ensure_progress_tables(conn)
    where = "WHERE user_id = ?" if user_id else ""
    params = (user_id,) if user_id else ()
    before = {
        (r["user_id"], r["exercise_id"]): (r["next_weight_kg"], r["reason"])
        for r in conn.execute(f"SELECT * FROM exercise_progress {where}", params)
    }
    users = [user_id] if user_id else [
        r[0] for r in conn.execute(
            "SELECT DISTINCT user_id FROM workout_logs UNION SELECT DISTINCT user_id FROM exercise_progress"
        )
    ]
    for uid in users:
        exercise_ids = {k[1] for k in before if k[0] == uid} | {
            r[0] for r in conn.execute(
                """
                SELECT DISTINCT ws.exercise_id FROM workout_sets ws
                JOIN workout_logs wl ON wl.id = ws.workout_log_id
                WHERE wl.user_id = ? AND wl.status = 'completed'
                """,
                (uid,),
            )
        }
        recompute_exercise_progress(conn, uid, exercise_ids)
    after = {
        (r["user_id"], r["exercise_id"]): (r["next_weight_kg"], r["reason"])
        for r in conn.execute(f"SELECT * FROM exercise_progress {where}", params)
    }
    changes = []
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            changes.append({"user_id": key[0], "exercise_id": key[1], "antes": before.get(key), "despues": after.get(key)})
    return {"antes": len(before), "despues": len(after), "cambios": changes}


def refresh_progress_after_set_edit(conn, user_id: str, workout_id: str, exercise_id: str) -> None:
    """Si se añade/edita/borra una serie de un entreno YA completado, recalcula."""
    row = conn.execute(
        "SELECT status FROM workout_logs WHERE id = ? AND user_id = ?",
        (workout_id, user_id),
    ).fetchone()
    if row and row["status"] == "completed":
        recompute_exercise_progress(conn, user_id, {exercise_id})


def _ensure_session_label(conn) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(routines)")}
    if "session_label" not in cols:
        conn.execute("ALTER TABLE routines ADD COLUMN session_label TEXT")
        conn.commit()


def _shown(row) -> str:
    label = row["session_label"] if row and "session_label" in row.keys() else None
    if row and label:
        return f"{row['name']} · {label}"
    return row["name"] if row else ""


def _overlap(conn, last_workout_id: str | None, next_routine_id: str | None) -> list[str]:
    if not last_workout_id or not next_routine_id:
        return []
    rows = conn.execute(
        """
        SELECT DISTINCT e.name
        FROM workout_sets ws
        JOIN routine_exercises re
          ON re.exercise_id = ws.exercise_id
         AND re.routine_id = ?
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE ws.workout_log_id = ?
          AND ws.is_warmup = 0
        ORDER BY e.name
        """,
        (next_routine_id, last_workout_id),
    ).fetchall()
    return [r["name"] for r in rows]


@router.get("/home")
def home(user_id: str, current_user=Depends(get_authenticated_user)):
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
        "SELECT id, name, session_label FROM routines WHERE is_active = 1 AND user_id = ? ORDER BY day_order",
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
    overlap = _overlap(conn, last["id"] if last else None, next_r["id"] if next_r else None)
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
    # Solo lectura (sin DDL en GET): las columnas nuevas las crea el arranque (init_progress_db).
    loads = {}
    for r in conn.execute("SELECT * FROM exercise_progress WHERE user_id=?", (user_id,)):
        row = dict(r)
        loads[row["exercise_id"]] = {
            "next_weight_kg": row["next_weight_kg"],
            "reason": row["reason"],
            "next_reps": row.get("next_reps"),
            "kind": row.get("kind"),
            "measure_type": row.get("measure_type"),
            "fail_streak": row.get("fail_streak") or 0,
        }
    flags = [
        dict(r)
        for r in conn.execute(
            "SELECT exercise_id, zone, note FROM exercise_flags WHERE user_id=? AND active=1",
            (user_id,),
        )
    ]
    stagnation = list_stagnated_exercises(conn, user_id)
    conn.close()
    return {
        "last_workout_id": last["id"] if last else None,
        "next_routine_id": next_r["id"] if next_r else None,
        "next_routine_name": _shown(next_r) if next_r else None,
        "overlap": overlap,
        "tomorrow": (
            f"Siguiente: {_shown(next_r)}."
            if next_r
            else "Sin rutina activa."
        ),
        "deload_due": deload_due,
        "streak_7": streak7,
        "streak_28": streak28,
        "loads": loads,
        "flags": flags,
        "stagnation": stagnation,
    }


@router.get("/stagnation")
def stagnation_alerts(user_id: str, current_user=Depends(get_authenticated_user)):
    """Ejercicios del usuario con 3+ sesiones sin progreso o racha de fallos creciente."""
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        items = list_stagnated_exercises(conn, user_id)
    finally:
        conn.close()
    return {"items": items, "count": len(items)}


@router.get("/stats")
def stats(user_id: str, current_user=Depends(get_authenticated_user)):
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



@router.get("/exercise/{exercise_id}")
def exercise_chart(exercise_id: str, user_id: str, range: str = "12w", current_user=Depends(get_authenticated_user)):
    """Historial de 1RM estimado (Epley), peso máximo y volumen por sesión."""
    user_id = resolve_target_user(current_user, user_id)
    range_key = range if range in RANGE_DAYS else "12w"
    conn = get_connection()
    try:
        data = exercise_history(conn, user_id, exercise_id, range_key)
    finally:
        conn.close()
    if data is None:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    return data


@router.get("/volume")
def volume_chart(user_id: str, weeks: int = 12, current_user=Depends(get_authenticated_user)):
    """Volumen semanal por grupo muscular (series efectivas) y equilibrio."""
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        data = weekly_volume(conn, user_id, clamp_weeks(weeks))
    finally:
        conn.close()
    return data


@router.get("/warmup")
def warmup_preview(
    user_id: str,
    exercise_id: str,
    weight_kg: float,
    current_user=Depends(get_authenticated_user),
):
    """Series de aproximación sugeridas para un peso de trabajo (el usuario autenticado)."""
    resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(exercises)")}
        select = ", ".join(
            c for c in ("id", "name", "equipment", "exercise_type", "measure_type",
                        "weight_increment_kg", "category", "target_muscle")
            if c in cols
        )
        ex = conn.execute(f"SELECT {select} FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    finally:
        conn.close()
    if ex is None:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    exd = {k: ex[k] for k in ex.keys()}
    sets = suggest_warmup(exd, weight_kg)
    return {
        "exercise_id": exercise_id,
        "name": exd.get("name"),
        "working_weight_kg": weight_kg,
        "sets": sets,
        "count": len(sets),
    }


class FlagIn(BaseModel):
    exercise_id: str
    zone: str
    note: str | None = None


@router.post("/flag")
def add_flag(body: FlagIn, user_id: str, current_user=Depends(get_authenticated_user)):
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
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    conn.execute(
        "UPDATE exercise_flags SET active=0 WHERE user_id=? AND exercise_id=?",
        (user_id, body.exercise_id),
    )
    conn.commit()
    conn.close()
    return {"ok": True}
