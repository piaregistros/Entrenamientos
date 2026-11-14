"""Acceso a BD de la doble progresión (Fase 6).

Una sola entrada para todos los consumidores:
    compute_exercise_target(conn, user_id, exercise_id, routine_id=..., workout_id=...)
Lee configuración + historial y delega en ``progression.next_target`` (función pura).
"""
from __future__ import annotations

import math

from .progression import (
    MEASURE_TYPES,
    default_increment,
    infer_measure_type,
    next_target,
)

PROGRESS_EXTRA_COLUMNS = (
    ("next_reps", "INTEGER"),
    ("kind", "TEXT"),
    ("fail_streak", "INTEGER NOT NULL DEFAULT 0"),
    ("measure_type", "TEXT"),
    ("source_workout_id", "TEXT"),
)


def _table_exists(conn, name: str) -> bool:
    return bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone())


def _columns(conn, table: str) -> set[str]:
    return {r["name"] if hasattr(r, "keys") else r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def ensure_progress_extra_columns(conn) -> None:
    """Columnas de exercise_progress que guardan el objetivo completo (reps, tipo, racha de fallos)."""
    if not _table_exists(conn, "exercise_progress"):
        return
    cols = _columns(conn, "exercise_progress")
    for name, ddl in PROGRESS_EXTRA_COLUMNS:
        if name not in cols:
            conn.execute(f"ALTER TABLE exercise_progress ADD COLUMN {name} {ddl}")


def ensure_progression_schema(conn) -> dict:
    """Idempotente. Añade exercises.measure_type, rellena measure_type/weight_increment_kg que falten
    (nunca pisa un valor ya presente) y amplía exercise_progress. Hace commit."""
    cols = _columns(conn, "exercises")
    if "measure_type" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN measure_type TEXT")
    if "weight_increment_kg" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN weight_increment_kg DECIMAL")
    ensure_progress_extra_columns(conn)

    filled_measure = filled_increment = 0
    cols = _columns(conn, "exercises")
    select = ["id", "name"] + [c if c in cols else f"NULL AS {c}" for c in ("equipment", "exercise_type")]
    select += ["measure_type", "weight_increment_kg"]
    rows = conn.execute(f"SELECT {', '.join(select)} FROM exercises").fetchall()
    for r in rows:
        measure = r["measure_type"] if r["measure_type"] in MEASURE_TYPES else None
        if measure is None:
            measure = infer_measure_type(r["name"], r["equipment"])
            conn.execute("UPDATE exercises SET measure_type=? WHERE id=?", (measure, r["id"]))
            filled_measure += 1
        if r["weight_increment_kg"] is None:
            inc = default_increment(r["equipment"], r["exercise_type"], measure)
            conn.execute("UPDATE exercises SET weight_increment_kg=? WHERE id=?", (inc, r["id"]))
            filled_increment += 1
    conn.commit()
    return {"measure_type": filled_measure, "weight_increment_kg": filled_increment}


def load_exercise(conn, exercise_id: str) -> dict:
    cols = _columns(conn, "exercises")
    select = ["id", "name"]
    for column in ("equipment", "exercise_type", "weight_increment_kg", "measure_type"):
        select.append(column if column in cols else f"NULL AS {column}")
    row = conn.execute(f"SELECT {', '.join(select)} FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if not row:
        return {"id": exercise_id, "name": "", "equipment": "", "exercise_type": None,
                "weight_increment_kg": None, "measure_type": None}
    return dict(row)


def _range_from_routine(conn, routine_id, exercise_id):
    if not routine_id:
        return None
    return conn.execute(
        "SELECT target_rep_min, target_rep_max, target_rir FROM routine_exercises WHERE routine_id=? AND exercise_id=?",
        (routine_id, exercise_id),
    ).fetchone()


def _range_from_extra(conn, workout_id, exercise_id):
    if not workout_id or not _table_exists(conn, "workout_extra_exercises"):
        return None
    return conn.execute(
        "SELECT target_rep_min, target_rep_max, target_rir FROM workout_extra_exercises "
        "WHERE workout_log_id=? AND exercise_id=?",
        (workout_id, exercise_id),
    ).fetchone()


def _range_from_substitution(conn, workout_id, exercise_id):
    """Fase 7: si en este entreno el ejercicio está haciendo de SUSTITUTO, hereda el rango objetivo
    (series, reps, RIR) del hueco de la rutina que ocupa; la carga sigue siendo la suya."""
    if not workout_id or not _table_exists(conn, "workout_exercise_substitutions"):
        return None
    return conn.execute(
        """
        SELECT re.target_rep_min, re.target_rep_max, re.target_rir
        FROM workout_exercise_substitutions s
        JOIN workout_logs wl ON wl.id = s.workout_log_id
        JOIN routine_exercises re ON re.routine_id = wl.routine_id AND re.exercise_id = s.original_exercise_id
        WHERE s.workout_log_id = ? AND s.substitute_exercise_id = ?
        LIMIT 1
        """,
        (workout_id, exercise_id),
    ).fetchone()


def _range_from_user_substitutions(conn, user_id, exercise_id):
    """Fase 7: sin entreno concreto (recálculo/rebuild), el rango del último hueco que ocupó como sustituto."""
    if not user_id or not _table_exists(conn, "workout_exercise_substitutions"):
        return None
    return conn.execute(
        """
        SELECT re.target_rep_min, re.target_rep_max, re.target_rir
        FROM workout_exercise_substitutions s
        JOIN workout_logs wl ON wl.id = s.workout_log_id
        JOIN routine_exercises re ON re.routine_id = wl.routine_id AND re.exercise_id = s.original_exercise_id
        WHERE wl.user_id = ? AND s.substitute_exercise_id = ?
        ORDER BY datetime(wl.date) DESC, wl.id DESC LIMIT 1
        """,
        (user_id, exercise_id),
    ).fetchone()


def _range_from_user_routines(conn, user_id, exercise_id):
    if not user_id:
        return None
    return conn.execute(
        """
        SELECT re.target_rep_min, re.target_rep_max, re.target_rir
        FROM routine_exercises re
        JOIN routines r ON r.id = re.routine_id
        WHERE r.user_id = ? AND r.is_active = 1 AND re.exercise_id = ?
        ORDER BY r.day_order LIMIT 1
        """,
        (user_id, exercise_id),
    ).fetchone()



def _attach_casa_progression(conn, ex: dict, user_id=None, routine_id=None) -> dict:
    """Kettlebells: lista de pesos del usuario. Mancuernas en rutina de casa: incremento 2,5 kg."""
    if not user_id:
        return ex
    try:
        from .casa import load_home_settings, routine_location
        from .progression import equipment_class
    except ImportError:
        return ex
    settings = load_home_settings(conn, user_id)
    cls = equipment_class(ex.get("equipment"))
    if cls == "kettlebell":
        ex["weight_steps"] = settings.get("kettlebell_weights") or []
    if routine_location(conn, routine_id) == "casa" and cls == "dumbbell":
        inc = settings.get("dumbbell_increment_kg")
        if inc and inc > 0:
            ex["weight_increment_kg"] = inc
    return ex


def build_exercise_config(conn, exercise_id: str, routine_id=None, workout_id=None, user_id=None) -> dict:
    """Ejercicio + rango objetivo.

    Orden: rutina del entreno > extra del entreno > rutina activa del usuario que lo contiene >
    valores por defecto (8-12 reps, 30-60 s en isométricos, RIR 2).
    """
    ex = load_exercise(conn, exercise_id)
    if workout_id and not routine_id:
        wl = conn.execute("SELECT routine_id FROM workout_logs WHERE id=?", (workout_id,)).fetchone()
        routine_id = wl["routine_id"] if wl else None
    target = (
        _range_from_routine(conn, routine_id, exercise_id)
        or _range_from_substitution(conn, workout_id, exercise_id)
        or _range_from_extra(conn, workout_id, exercise_id)
        or _range_from_user_routines(conn, user_id, exercise_id)
        or _range_from_user_substitutions(conn, user_id, exercise_id)
    )
    ex["rep_min"] = target["target_rep_min"] if target else None
    ex["rep_max"] = target["target_rep_max"] if target else None
    ex["rir_target"] = target["target_rir"] if target else None
    return _attach_casa_progression(conn, ex, user_id=user_id, routine_id=routine_id)


def load_recent_sessions(conn, user_id: str, exercise_id: str, until_workout_id=None, limit: int = 2,
                         with_meta: bool = False):
    """Series de trabajo de las últimas sesiones COMPLETADAS (más reciente primero).

    Excluye entrenos de deload y calentamientos. Con ``until_workout_id`` solo cuenta lo anterior o
    igual a ese entreno (así apply_progression y el recálculo ven la misma historia que el usuario).
    """
    params: list = [user_id, exercise_id]
    until_sql = ""
    if until_workout_id:
        target = conn.execute(
            "SELECT date, datetime(date) AS parsed FROM workout_logs WHERE id=?", (until_workout_id,)
        ).fetchone()
        # Si SQLite no sabe interpretar la fecha (formato raro), no se filtra por fecha: mejor ver
        # todo el historial que perder la progresión en silencio.
        if target and target["parsed"] is not None:
            until_sql = (
                " AND (datetime(wl.date) < datetime(?) OR (datetime(wl.date) = datetime(?) AND wl.id <= ?))"
            )
            params += [target["date"], target["date"], until_workout_id]
    deload_sql = " AND COALESCE(wl.is_deload, 0) = 0" if "is_deload" in _columns(conn, "workout_logs") else ""
    workouts = conn.execute(
        f"""
        SELECT wl.id, wl.date FROM workout_logs wl
        WHERE wl.user_id = ? AND wl.status = 'completed'{deload_sql}
          AND EXISTS (SELECT 1 FROM workout_sets ws
                      WHERE ws.workout_log_id = wl.id AND ws.exercise_id = ?
                        AND COALESCE(ws.is_warmup, 0) = 0 AND COALESCE(ws.reps, 0) > 0)
          {until_sql}
        ORDER BY datetime(wl.date) DESC, wl.id DESC
        LIMIT ?
        """,
        params + [limit],
    ).fetchall()
    sessions = []
    for w in workouts:
        rows = conn.execute(
            """
            SELECT weight_kg, reps, rir, is_warmup FROM workout_sets
            WHERE workout_log_id = ? AND exercise_id = ? AND COALESCE(is_warmup, 0) = 0
            ORDER BY set_number, rowid
            """,
            (w["id"], exercise_id),
        ).fetchall()
        sessions.append([dict(r) for r in rows])
    if with_meta:
        return sessions, [{"workout_id": w["id"], "date": w["date"]} for w in workouts]
    return sessions


def _last_session_summary(sessions):
    if not sessions or not sessions[0]:
        return None
    sets = [s for s in sessions[0] if (s.get("reps") or 0) > 0]
    if not sets:
        return None
    top = max(float(s.get("weight_kg") or 0) for s in sets)
    return {
        "weight_kg": top,
        "reps": [int(s["reps"]) for s in sets if abs(float(s.get("weight_kg") or 0) - top) < 1e-6],
    }


def _apply_gym_link_start(conn, user_id, ex, result, until_workout_id=None) -> None:
    """Fase 12c: ejercicio de casa SIN historial que sustituye a uno de gimnasio CON historial →
    peso de partida orientativo (factor × última carga de trabajo del gimnasio, redondeado hacia abajo
    al incremento). Solo para ejercicios con factor definido en CASA_GYM_LINKS; no toca nada guardado."""
    if result.get("kind") != "start" or result.get("measure_type") not in (None, "reps"):
        return
    try:
        from .casa_catalog import CASA_GYM_LINKS
    except ImportError:
        return
    link = CASA_GYM_LINKS.get(ex.get("name"))
    if not link or not link[1]:
        return
    gym_name, factor = link
    row = conn.execute("SELECT id FROM exercises WHERE name = ?", (gym_name,)).fetchone()
    if not row:
        return
    gym_sessions = load_recent_sessions(conn, user_id, row["id"], until_workout_id=until_workout_id, limit=1)
    last = _last_session_summary(gym_sessions)
    if not last or not last["weight_kg"] or last["weight_kg"] <= 0:
        return
    inc = result.get("increment_kg") or 2.5
    weight = math.floor(last["weight_kg"] * factor / inc + 1e-9) * inc
    if weight <= 0:
        return
    result["weight_kg"] = round(float(weight), 2)
    result["gym_link"] = {"exercise": gym_name, "weight_kg": last["weight_kg"], "factor": factor}
    result["reason"] = (
        f"Sin historial en casa. Punto de partida orientativo: {factor:g} × los {last['weight_kg']:g} kg "
        f"de «{gym_name}» = {weight:g} kg. Ajústalo a cómo se sienta con {result.get('reps')} reps."
    )


def compute_exercise_target(conn, user_id: str, exercise_id: str, routine_id=None, workout_id=None,
                            until_workout_id=None):
    """Objetivo siguiente de un ejercicio (única fuente de verdad). Devuelve (resultado, config)."""
    ex = build_exercise_config(conn, exercise_id, routine_id=routine_id, workout_id=workout_id, user_id=user_id)
    sessions, metas = load_recent_sessions(conn, user_id, exercise_id, until_workout_id=until_workout_id,
                                           with_meta=True)
    result = next_target(ex, sessions)
    result["has_history"] = bool(sessions)
    result["last_workout"] = metas[0] if metas else None
    result["last_session"] = _last_session_summary(sessions)
    if not sessions:
        _apply_gym_link_start(conn, user_id, ex, result, until_workout_id)
    return result, ex
