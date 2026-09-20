"""Hechos de entrenamiento. Solo SQLite. No inventa."""
from __future__ import annotations
import re
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
        "SELECT id, name, day_order FROM routines WHERE user_id = ? AND is_active = 1 ORDER BY day_order",
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
        FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id
        WHERE re.routine_id = ? ORDER BY re."order"
        """,
        (routine_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def substitutions(conn, exercise_id: str, exclude_ids: set[str], limit: int = 2) -> list[dict]:
    rows = conn.execute(
        """
        SELECT es.alternative_exercise_id AS exercise_id, e.name
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


def _letter(name: str) -> str | None:
    n = (name or "").upper()
    m = re.search(r"\b([ABC])\b", n)
    if m:
        return m.group(1)
    m = re.search(r"D[IÍ]A\s*([123])", n)
    if m:
        return {"1": "A", "2": "B", "3": "C"}[m.group(1)]
    return None


def declared_session(text: str, routines: list[dict]) -> dict | None:
    t = (text or "").lower()
    said_done = any(w in t for w in (
        "hice", "hizo", "hecho", "entrené", "entrene", "entrenado",
        "ya hice", "ya la", "el viernes", "ayer", "no está reflejad", "no esta reflejad",
        "te acabo de decir", "ya hice la",
    ))
    if not said_done and not re.search(r"\b[abc]\b", t) and "día" not in t and "dia" not in t:
        # still try letters if user says "la B" with hice in same blob
        pass
    hit = None
    for r in routines:
        letter = _letter(r.get("name") or "")
        name = (r.get("name") or "").lower()
        order = str(r.get("day_order") or "")
        patterns = []
        if letter:
            patterns += [rf"\bla {letter.lower()}\b", rf"\bel {letter.lower()}\b", rf"\brutina {letter.lower()}\b", rf"\b{letter.lower()}\b"]
        if order:
            patterns += [rf"d[ií]a\s*{order}", rf"la {order}\b", rf"el {order}\b"]
        if name and len(name) >= 2:
            patterns.append(re.escape(name))
        if any(re.search(p, t) for p in patterns):
            if said_done or re.search(r"hice|hecho|entren", t):
                hit = {"routine_id": r["id"], "routine_name": r["name"], "day_order": r["day_order"], "source": "user_declaration", "letter": letter}
    return hit


def build_facts(conn, user_id: str, message: str = "", history_text: str = "") -> dict:
    last = last_completed_workout(conn, user_id)
    routines = active_routines(conn, user_id)
    blob = f"{history_text}\n{message}"
    declared = declared_session(blob, routines)
    relevant = declared or last
    if declared:
        dex = routine_exercises(conn, declared["routine_id"])
        relevant = {
            **declared,
            "exercise_ids": [x["exercise_id"] for x in dex],
            "exercises": [x["name"] for x in dex],
            "persisted": False,
        }
    nxt = next_routine(routines, relevant)
    nxt_ex = routine_exercises(conn, nxt["id"]) if nxt else []
    last_ids = set((relevant or {}).get("exercise_ids") or [])
    direct = [x for x in nxt_ex if x["exercise_id"] in last_ids]
    exclude = set(last_ids) | {x["exercise_id"] for x in nxt_ex}
    adapts = []
    for x in direct:
        alts = substitutions(conn, x["exercise_id"], exclude)
        adapts.append({"from": x["name"], "to": [a["name"] for a in alts]})
        exclude |= {a["exercise_id"] for a in alts}
    letters = [_letter(r["name"]) or r["name"] for r in routines]
    return {
        "today": date.today().isoformat(),
        "last_logged": last,
        "user_declared": declared,
        "relevant_previous": {"routine_name": (relevant or {}).get("routine_name"), "day_order": (relevant or {}).get("day_order")} if relevant else None,
        "next_routine": nxt,
        "available_routines": letters,
        "next_exercises": [x["name"] for x in nxt_ex],
        "direct_overlap": [x["name"] for x in direct],
        "has_direct_overlap": bool(direct),
        "adaptations": adapts,
        "order": "A → B → C → A",
        "rir_does_not_prove_recovery": True,
    }


def fallback_answer(facts: dict, message: str) -> str:
    last = facts.get("last_logged")
    nxt = facts.get("next_routine")
    overlap = facts.get("direct_overlap") or []
    lines = []
    if last:
        lines.append(f"En la app el último registrado es {last.get('routine_name')} el {last.get('date')}.")
    if facts.get("user_declared"):
        lines.append(f"Tú has dicho que ya hiciste {facts['user_declared'].get('routine_name')}. Eso no está guardado; lo uso solo en este chat.")
    if nxt:
        lines.append(f"Siguiente por orden A→B→C: {nxt.get('name')}.")
    names = facts.get("available_routines") or []
    if names:
        lines.append("Rutinas activas: " + ", ".join(str(x) for x in names) + ".")
    if overlap:
        lines.append("Solapamiento directo: " + ", ".join(overlap) + ".")
        for a in facts.get("adaptations") or []:
            lines.append(f"  {a['from']} → {', '.join(a['to']) or 'sin alternativa'}.")
    else:
        lines.append("No hay solapamiento directo por ejercicio con esa sesión.")
    lines.append("El RIR no demuestra recuperación.")
    return "\n".join(lines)
