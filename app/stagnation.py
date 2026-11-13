"""Detección de estancamiento y aviso de deload (Fase 8).

Función pura (sin BD): usa ``next_target``, ``fail_streak`` y ``deload_weight``
de ``app.progression``. Un ejercicio está estancado si:

  * hay 3 o más sesiones seguidas sin subir peso ni repeticiones
    (ni segundos, en isométricos), o
  * la racha de fallos crece (``fail_streak >= 2``: ya toca deload).

La sugerencia es un deload del 10 % (redondeado al paso del ejercicio) o
cambiar el ejercicio (el frontend enlaza con el selector de la Fase 7).
"""
from __future__ import annotations

from .progression import (
    _evaluate,
    _resolve_range,
    deload_weight,
    fmt_num,
    infer_measure_type,
    next_target,
    resolve_increment,
    MEASURE_TYPES,
)

MIN_SESSIONS = 3
HISTORY_LIMIT = 8


def _session_score(evaluation: dict) -> tuple[float, int]:
    """Carga máxima de la sesión y las reps (o segundos) de la serie más floja a esa carga."""
    return float(evaluation["weight"]), int(min(evaluation["reps"]))


def _progressed(older: dict, newer: dict) -> bool:
    """True si la sesión más nueva mejoró peso o reps/tiempo respecto a la anterior."""
    old_w, old_r = _session_score(older)
    new_w, new_r = _session_score(newer)
    if new_w > old_w + 1e-6:
        return True
    if abs(new_w - old_w) < 1e-6 and new_r > old_r:
        return True
    return False


def _fail_streak(evaluated: list[dict], rep_min: int) -> int:
    """Sesiones recientes consecutivas por debajo del mínimo del rango."""
    streak = 0
    for ev in evaluated:
        if min(ev["reps"]) < rep_min:
            streak += 1
        else:
            break
    return streak


def detect_stagnation(ex: dict, sessions: list[list[dict]], min_sessions: int = MIN_SESSIONS) -> dict | None:
    """Analiza el historial (más reciente primero) y devuelve el aviso o None.

    ``ex`` es el mismo dict que recibe ``next_target``. ``sessions`` son series
    de entrenos completados (sin deload ni calentamientos).
    """
    evaluated = [e for e in (_evaluate(s) for s in (sessions or [])) if e]
    if not evaluated:
        return None

    measure = ex.get("measure_type") if ex.get("measure_type") in MEASURE_TYPES else None
    measure = measure or infer_measure_type(ex.get("name"), ex.get("equipment"))
    rep_min, _rep_max, _rir = _resolve_range(ex, measure)
    unit = "s" if measure == "time" else "reps"
    inc = resolve_increment(ex)
    target = next_target(ex, sessions)

    plateau = 1
    for i in range(len(evaluated) - 1):
        if _progressed(evaluated[i + 1], evaluated[i]):
            break
        plateau += 1

    fail_streak = _fail_streak(evaluated, rep_min)
    # La racha de next_target (como mucho 2) se expone tal cual; la nuestra
    # puede ser más larga porque miramos más de dos sesiones.
    reported_fail = max(int(target.get("fail_streak") or 0), fail_streak)

    stagnated = plateau >= min_sessions or fail_streak >= 2
    if not stagnated:
        return None

    last_w, last_r = _session_score(evaluated[0])
    loaded = last_w > 0
    suggested = None
    if target.get("kind") == "deload" and target.get("weight_kg") is not None:
        suggested = float(target["weight_kg"])
    elif loaded:
        lighter = deload_weight(last_w, inc)
        suggested = lighter if lighter < last_w else None

    if fail_streak >= 2:
        kind = "fail_streak"
        if measure == "time":
            reason = (
                f"Has fallado el mínimo ({rep_min} s) en {fail_streak} sesiones seguidas. "
                f"Baja a {rep_min} s y recupera la técnica, o cambia de ejercicio."
            )
        elif suggested is not None:
            reason = (
                f"Has fallado el mínimo ({rep_min} reps) en {fail_streak} sesiones seguidas. "
                f"Prueba un deload a {fmt_num(suggested)} kg (−10 %) o sustituye el ejercicio."
            )
        else:
            reason = (
                f"Has fallado el mínimo ({rep_min} reps) en {fail_streak} sesiones seguidas. "
                f"Haz {rep_min} reps limpias o usa una variante más fácil."
            )
    else:
        kind = "plateau"
        unit_txt = "s" if measure == "time" else " reps"
        if measure == "time":
            reason = (
                f"Llevas {plateau} sesiones seguidas sin aguantar más tiempo "
                f"(última: {last_r} s). Prueba una variante o cambia de ejercicio."
            )
        elif loaded and suggested is not None:
            reason = (
                f"Llevas {plateau} sesiones seguidas sin subir peso ni repeticiones "
                f"(última: {fmt_num(last_w)} kg × {last_r}{unit_txt}). "
                f"Prueba un deload a {fmt_num(suggested)} kg (−10 %) o sustituye el ejercicio."
            )
        else:
            reason = (
                f"Llevas {plateau} sesiones seguidas sin subir repeticiones "
                f"(última: {last_r}{unit_txt}). Prueba una variante más fácil o cambia de ejercicio."
            )

    return {
        "stagnated": True,
        "kind": kind,
        "sessions_without_progress": plateau,
        "fail_streak": reported_fail,
        "last_weight_kg": round(last_w, 2),
        "last_min_reps": last_r,
        "measure_type": measure,
        "unit": unit,
        "suggested_deload_kg": None if suggested is None else round(float(suggested), 2),
        "suggestion": "deload_or_swap" if suggested is not None else "swap",
        "reason": reason,
        "progression_kind": target.get("kind"),
    }


def enrich_item(ex: dict, result: dict) -> dict:
    """Añade identificadores y metadatos al aviso (para la API)."""
    item = dict(result)
    item["exercise_id"] = ex.get("id")
    item["name"] = ex.get("name")
    item["equipment"] = ex.get("equipment")
    item["exercise_type"] = ex.get("exercise_type")
    item["target_muscle"] = ex.get("target_muscle")
    return item


def list_stagnated_exercises(conn, user_id: str, min_sessions: int = MIN_SESSIONS,
                             history_limit: int = HISTORY_LIMIT) -> list[dict]:
    """Avisos de estancamiento del usuario, ordenados del más grave al más leve.

    Solo lee; no hace DDL. Usa el historial real (entrenos completados, sin deload).
    """
    from .progression_db import build_exercise_config, load_recent_sessions

    rows = conn.execute(
        """
        SELECT DISTINCT ws.exercise_id
        FROM workout_sets ws
        JOIN workout_logs wl ON wl.id = ws.workout_log_id
        WHERE wl.user_id = ?
          AND wl.status = 'completed'
          AND COALESCE(wl.is_deload, 0) = 0
          AND COALESCE(ws.is_warmup, 0) = 0
          AND COALESCE(ws.reps, 0) > 0
        """,
        (user_id,),
    ).fetchall()
    items = []
    for row in rows:
        eid = row[0] if not hasattr(row, "keys") else row["exercise_id"]
        ex = build_exercise_config(conn, eid, user_id=user_id)
        meta = conn.execute(
            "SELECT name, equipment, exercise_type, target_muscle FROM exercises WHERE id = ?",
            (eid,),
        ).fetchone()
        if meta:
            ex.setdefault("name", meta["name"])
            ex.setdefault("equipment", meta["equipment"])
            ex.setdefault("exercise_type", meta["exercise_type"])
            ex["target_muscle"] = meta["target_muscle"]
        sessions = load_recent_sessions(conn, user_id, eid, limit=history_limit)
        result = detect_stagnation(ex, sessions, min_sessions=min_sessions)
        if result:
            items.append(enrich_item(ex, result))
    items.sort(
        key=lambda x: (
            0 if x["kind"] == "fail_streak" else 1,
            -int(x["sessions_without_progress"]),
            -int(x["fail_streak"] or 0),
            str(x.get("name") or ""),
        )
    )
    return items
