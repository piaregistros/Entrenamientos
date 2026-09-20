"""Hechos de entrenamiento. Solo SQLite. No inventa."""
from __future__ import annotations
from datetime import date


def last_completed_workout(conn, user_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT wl.id, wl.date, wl.routine_id, r.name AS routine_name, r.day_order
        FROM workout_logs wl
        LEFT JOIN routines r ON r.id = wl.routine_id
        WHERE wl.user_id = ? AND wl.status = 'completed'
        ORDER BY wl.date DESC, wl.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()
    if not row:
        return None
    sets = conn.execute(
        """
        SELECT ws.exercise_id, e.name, e.target_muscle, ws.reps, ws.rir, ws.weight_kg, ws.is_warmup
        FROM workout_sets ws
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE ws.workout_log_id = ?
        """,
        (row["id"],),
    ).fetchall()
    work = [dict(s) for s in sets if not s["is_warmup"]]
    rirs = [s["rir"] for s in work if s["rir"] is not None]
    return {
        "id": row["id"],
        "date": row["date"],
        "routine_id": row["routine_id"],
        "routine_name": row["routine_name"] or "?",
        "day_order": row["day_order"],
        "exercise_ids": sorted({s["exercise_id"] for s in work}),
        "exercises": sorted({s["name"] for s in work}),
        "muscles": sorted({s["target_muscle"] for s in work if s["target_muscle"]}),
        "total_reps": sum(int(s["reps"] or 0) for s in work),
        "avg_rir": round(sum(rirs) / len(rirs), 1) if rirs else None,
        "rir_is_not_recovery": True,
    }


def active_routines(conn, user_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, name, day_order FROM routines
        WHERE user_id = ? AND is_active = 1
        ORDER BY day_order
        """,
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def next_routine(routines: list[dict], last: dict | None) -> dict | None:
    if not routines:
        return None
    if not last or last.get("day_order") is None:
        return routines[0]
    nxt = [r for r in routines if (r.get("day_order") or 0) > (last.get("day_order") or 0)]
    return nxt[0] if nxt else routines[0]


def routine_exercises(conn, routine_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT re.exercise_id, e.name, e.target_muscle
        FROM routine_exercises re
        JOIN exercises e ON e.id = re.exercise_id
        WHERE re.routine_id = ?
        ORDER BY re."order"
        """,
        (routine_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def substitutions(conn, exercise_id: str, exclude_ids: set[str], limit: int = 2) -> list[dict]:
    rows = conn.execute(
        """
        SELECT es.alternative_exercise_id AS exercise_id, e.name, e.target_muscle,
               es.reason, es.same_muscle, es.same_movement_pattern
        FROM exercise_substitutions es
        JOIN exercises e ON e.id = es.alternative_exercise_id
        WHERE es.exercise_id = ? AND es.is_active = 1 AND e.is_active = 1
        ORDER BY es.same_muscle DESC, es.priority ASC
        """,
        (exercise_id,),
    ).fetchall()
    out = []
    for r in rows:
        if r["exercise_id"] in exclude_ids:
            continue
        out.append(dict(r))
        if len(out) >= limit:
            break
    return out


def declared_session(text: str, routines: list[dict]) -> dict | None:
    t = (text or "").lower()
    if not any(w in t for w in ("hice", "hice ayer", "entrené", "entrene", "no está reflejad", "no esta reflejad")):
        return None
    for r in routines:
        name = (r.get("name") or "").lower()
        if name and name in t:
            return {"routine_id": r["id"], "routine_name": r["name"], "day_order": r["day_order"], "source": "user_declaration"}
    return None


def build_facts(conn, user_id: str, message: str = "") -> dict:
    last = last_completed_workout(conn, user_id)
    routines = active_routines(conn, user_id)
    declared = declared_session(message, routines)
    relevant = declared or last
    nxt = next_routine(routines, relevant)
    nxt_ex = routine_exercises(conn, nxt["id"]) if nxt else []
    last_ids = set((relevant or {}).get("exercise_ids") or [])
    if declared and last and declared["routine_id"] != last.get("routine_id"):
        # declaración no persistida: solape contra ejercicios de esa rutina, no de A
        declared_ex = routine_exercises(conn, declared["routine_id"])
        last_ids = {x["exercise_id"] for x in declared_ex}
        relevant = {
            **declared,
            "exercise_ids": sorted(last_ids),
            "exercises": [x["name"] for x in declared_ex],
            "persisted": False,
            "date": None,
        }
    direct = [x for x in nxt_ex if x["exercise_id"] in last_ids]
    exclude = set(last_ids) | {x["exercise_id"] for x in nxt_ex}
    adapts = []
    for x in direct:
        alts = substitutions(conn, x["exercise_id"], exclude)
        adapts.append({"from": x["name"], "to": [a["name"] for a in alts]})
        exclude |= {a["exercise_id"] for a in alts}
    return {
        "today": date.today().isoformat(),
        "last_logged": last,
        "user_declared": declared,
        "relevant_previous": relevant,
        "next_routine": nxt,
        "next_exercises": [x["name"] for x in nxt_ex],
        "direct_overlap": [x["name"] for x in direct],
        "has_direct_overlap": bool(direct),
        "adaptations": adapts,
        "rir_does_not_prove_recovery": True,
        "do_not_invent": True,
    }


def fallback_answer(facts: dict, message: str) -> str:
    last = facts.get("last_logged")
    rel = facts.get("relevant_previous") or last
    nxt = facts.get("next_routine")
    overlap = facts.get("direct_overlap") or []
    lines = []
    if last:
        lines.append(f"Último entrenamiento registrado: {last.get('routine_name')} el {last.get('date')} ({last.get('total_reps')} reps).")
    else:
        lines.append("No hay entrenamientos registrados.")
    if facts.get("user_declared"):
        lines.append(f"Para esta conversación usamos tu declaración: {facts['user_declared'].get('routine_name')} (no está en la base).")
    if nxt:
        lines.append(f"Siguiente rutina por orden: {nxt.get('name')}.")
    if overlap:
        lines.append("Solapamiento directo: " + ", ".join(overlap) + ".")
        for a in facts.get("adaptations") or []:
            if a["to"]:
                lines.append(f"  {a['from']} → {', '.join(a['to'])}.")
            else:
                lines.append(f"  {a['from']}: sin alternativa en el catálogo.")
        lines.append("No es un sí/no médico. Si entrenas hoy, cambia los solapados.")
    else:
        lines.append("No hay solapamiento directo por exercise_id con la sesión relevante.")
    lines.append("El RIR no demuestra recuperación fisiológica.")
    return "\n".join(lines)
