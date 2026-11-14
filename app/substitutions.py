"""Fase 7: sustituciones de ejercicios.

* Puntuación por parecido: mismo patrón de movimiento > mismos músculos > equipo alternativo.
* Tabla ``exercise_substitutions`` ampliada (columnas aditivas ``score`` y ``source``) con las
  parejas curadas (``substitutions_data``) y alternativas automáticas para todo el catálogo.
* Preferencias por usuario (``user_substitution_prefs``) y equipo no disponible (``user_equipment``).
* Al sustituir, la progresión y el peso sugerido salen del HISTORIAL DEL SUSTITUTO.

Nombres: la tabla pedida como (exercise_id, substitute_id, score, reason) ya existía con la columna
``alternative_exercise_id``; se conserva ese nombre (renombrarla rompería el despliegue actual).
"""
from __future__ import annotations

import logging
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from .auth import get_authenticated_user, resolve_target_user
from .database import get_connection
from .progression_db import compute_exercise_target

logger = logging.getLogger(__name__)
router = APIRouter()

# ------------------------------------------------------------------ utilidades
PATTERN_LABELS = {
    "abduccion_cadera": "abducción de cadera", "abduccion_hombro": "elevación lateral",
    "abduccion_horizontal": "apertura posterior", "aduccion_hombro": "apertura de pecho",
    "anti_extension": "core anti-extensión", "anti_rotacion": "core anti-rotación",
    "bisagra_cadera": "bisagra de cadera", "empuje_horizontal": "empuje horizontal",
    "empuje_vertical": "empuje vertical", "extension_cadera": "extensión de cadera",
    "extension_codo": "extensión de codo", "extension_hombro": "extensión de hombro",
    "extension_rodilla": "extensión de rodilla", "flexion_cadera": "flexión de cadera",
    "flexion_codo": "flexión de codo", "flexion_columna": "flexión de columna",
    "flexion_plantar": "elevación de talones", "flexion_rodilla": "flexión de rodilla",
    "sentadilla": "sentadilla", "traccion_horizontal": "tracción horizontal",
    "traccion_vertical": "tracción vertical", "zancada": "zancada",
}
# Patrones distintos pero parecidos (puntúan algo menos que el mismo patrón).
RELATED_PATTERNS = [
    {"sentadilla", "zancada", "extension_rodilla"},
    {"traccion_horizontal", "traccion_vertical", "extension_hombro", "abduccion_horizontal"},
    {"extension_cadera", "bisagra_cadera"},
    {"empuje_horizontal", "aduccion_hombro"},
    {"flexion_columna", "flexion_cadera", "anti_extension", "anti_rotacion"},
    {"extension_codo"},
]

SCORE_PATTERN = 50
SCORE_PATTERN_RELATED = 20
SCORE_MUSCLE_FINE = 25
SCORE_MUSCLE_COARSE = 12
SCORE_SECONDARY = 3
SCORE_EQUIP_ALT = 8
SCORE_EQUIP_SAME = 4
SCORE_TYPE = 3
SCORE_LATERALITY = 2
AUTO_MAX_PER_EXERCISE = 8
AUTO_MIN_PER_EXERCISE = 3
HABITUAL_BONUS = 10_000


def norm(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


# (subcadena, músculo fino, grupo grueso)
_MUSCLE_RULES = [
    ("pectoral", "pectoral", "pecho"),
    ("dorsal", "dorsal", "espalda"),
    ("espalda", "espalda media", "espalda"),
    ("romboides", "espalda media", "espalda"),
    ("trapecio", "espalda media", "espalda"),
    ("deltoides lateral", "deltoides lateral", "hombro"),
    ("deltoides posterior", "deltoides posterior", "hombro"),
    ("deltoides", "deltoides", "hombro"),
    ("triceps", "triceps", "extensores del codo"),
    ("biceps", "biceps", "flexores del codo"),
    ("braquial", "biceps", "flexores del codo"),
    ("gluteo", "gluteos", "cadera"),
    ("isquio", "isquiosurales", "cadera"),
    ("cuadriceps", "cuadriceps", "muslo"),
    ("gemelo", "gemelos", "gemelos"),
    ("soleo", "gemelos", "gemelos"),
    ("recto abdominal", "core", "core"),
    ("core", "core", "core"),
    ("oblicuo", "core", "core"),
    ("abdominal", "core", "core"),
]


def muscle_tokens(text) -> tuple[set[str], set[str]]:
    """(músculos finos, grupos gruesos) de un texto tipo «Cuádriceps y glúteos»."""
    fine: set[str] = set()
    coarse: set[str] = set()
    for chunk in norm(text).replace(",", " y ").split(" y "):
        chunk = chunk.strip()
        for needle, f, c in _MUSCLE_RULES:
            if needle in chunk:
                fine.add(f)
                coarse.add(c)
                break
    return fine, coarse


# Familias de equipo. «Barra o máquina» → {barra, maquina}.
_EQUIP_KEYS = [
    ("mancuerna", "mancuernas"), ("maquina", "maquina"), ("polea", "polea"),
    ("barra", "barra"), ("peso corporal", "peso corporal"), ("banco", "banco"),
    ("kettlebell", "kettlebells"), ("pesa rusa", "kettlebells"),
    ("landmine", "landmine"), ("trap bar", "trap_bar"), ("trx", "trx"),
    ("goma", "gomas"), ("banda", "gomas"),
]
EQUIPMENT_FAMILIES = ["mancuernas", "maquina", "polea", "barra", "peso corporal"]
HOME_FIT_BONUS = 12


def equipment_families(value) -> set[str]:
    text = norm(value)
    return {fam for key, fam in _EQUIP_KEYS if key in text} or ({"otro"} if text else set())


def _related(a, b) -> bool:
    return any(a in grp and b in grp for grp in RELATED_PATTERNS)


def score_pair(orig: dict, cand: dict) -> tuple[int, str, str]:
    """(puntuación 0-100, nivel, motivo). nivel: pattern | muscle | related | other."""
    parts: list[str] = []
    score = 0
    level = "other"
    p1, p2 = orig.get("movement_pattern"), cand.get("movement_pattern")
    if p1 and p2 and p1 == p2:
        score += SCORE_PATTERN
        level = "pattern"
        parts.append(f"mismo patrón ({PATTERN_LABELS.get(p1, p1)})")
    elif p1 and p2 and _related(p1, p2):
        score += SCORE_PATTERN_RELATED
        level = "related"
        parts.append(f"patrón parecido ({PATTERN_LABELS.get(p2, p2)})")

    f1, c1 = muscle_tokens(orig.get("target_muscle"))
    f2, c2 = muscle_tokens(cand.get("target_muscle"))
    if f1 & f2:
        score += SCORE_MUSCLE_FINE
        if level != "pattern":
            level = "muscle"
        parts.append("mismo músculo (" + (cand.get("target_muscle") or "").lower() + ")")
    elif c1 & c2:
        score += SCORE_MUSCLE_COARSE
        if level == "other":
            level = "related"
        parts.append("mismo grupo muscular")
    sec1 = muscle_tokens(orig.get("secondary_muscles"))[0] | f1
    sec2 = muscle_tokens(cand.get("secondary_muscles"))[0] | f2
    if (sec1 & sec2) and not (f1 & f2):
        score += SCORE_SECONDARY

    if score > 0:
        e1, e2 = equipment_families(orig.get("equipment")), equipment_families(cand.get("equipment"))
        if e1 and e2 and not (e1 & e2):
            score += SCORE_EQUIP_ALT
            parts.append(f"cambia {_eq_label(e1)} por {_eq_label(e2)}")
        elif e1 and e2:
            score += SCORE_EQUIP_SAME
        if orig.get("exercise_type") and orig.get("exercise_type") == cand.get("exercise_type"):
            score += SCORE_TYPE
        if orig.get("laterality") and orig.get("laterality") == cand.get("laterality"):
            score += SCORE_LATERALITY
    reason = (parts[0][0].upper() + parts[0][1:] + (("; " + "; ".join(parts[1:])) if len(parts) > 1 else "") + ".") if parts else ""
    return min(score, 100), level, reason


def _eq_label(fams: set[str]) -> str:
    return " / ".join(sorted(f.replace("maquina", "máquina") for f in fams))


# ------------------------------------------------------------------ esquema
def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def ensure_substitution_schema(conn: sqlite3.Connection) -> None:
    """Aditivo e idempotente."""
    cols = _columns(conn, "exercise_substitutions")
    if "score" not in cols:
        conn.execute("ALTER TABLE exercise_substitutions ADD COLUMN score REAL")
    if "source" not in cols:
        conn.execute("ALTER TABLE exercise_substitutions ADD COLUMN source TEXT NOT NULL DEFAULT 'curated'")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_substitution_prefs (
            user_id TEXT NOT NULL,
            original_exercise_id TEXT NOT NULL,
            substitute_exercise_id TEXT NOT NULL,
            routine_id TEXT NOT NULL DEFAULT '',
            times_used INTEGER NOT NULL DEFAULT 1,
            last_used_at TEXT,
            always_use INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (user_id, original_exercise_id, substitute_exercise_id, routine_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (original_exercise_id) REFERENCES exercises(id),
            FOREIGN KEY (substitute_exercise_id) REFERENCES exercises(id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_sub_prefs ON user_substitution_prefs(user_id, original_exercise_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_equipment (
            user_id TEXT NOT NULL,
            equipment TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT,
            PRIMARY KEY (user_id, equipment),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()


def _exercise_meta(conn) -> list[dict]:
    cols = _columns(conn, "exercises")
    want = ["id", "name", "target_muscle", "category", "equipment", "is_active", "movement_pattern",
            "secondary_muscles", "exercise_type", "laterality"]
    select = ", ".join(c if c in cols else f"NULL AS {c}" for c in want)
    return [dict(r) for r in conn.execute(f"SELECT {select} FROM exercises")]


def seed_substitutions(conn: sqlite3.Connection) -> dict:
    """Parejas curadas + alternativas automáticas de todo el catálogo. Nunca borra ni pisa nada."""
    from .seed_exercises_v2 import EXERCISES as CATALOG
    from .substitutions_data import CURATED_PAIRS

    rows = _exercise_meta(conn)
    by_name = {norm(r["name"]): r for r in rows if r.get("is_active", 1)}
    catalog_names = {norm(e["name"]) for e in CATALOG}
    report = {"curated": 0, "auto": 0, "missing": []}

    def insert(a, b, score, reason, source, same_pattern, same_muscle):
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO exercise_substitutions
                (id, exercise_id, alternative_exercise_id, priority, reason,
                 same_muscle, same_movement_pattern, is_active, score, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (str(uuid.uuid4()), a["id"], b["id"], 1 if score >= 85 else 2 if score >= 65 else 3,
             reason, int(same_muscle), int(same_pattern), score, source),
        )
        return cur.rowcount

    for name_a, name_b, score, reason in CURATED_PAIRS:
        a, b = by_name.get(norm(name_a)), by_name.get(norm(name_b))
        if not a or not b:
            report["missing"].append((name_a, name_b))
            continue
        for x, y in ((a, b), (b, a)):
            _s, level, _r = score_pair(x, y)
            report["curated"] += insert(x, y, score, reason, "curated", level == "pattern", level in ("pattern", "muscle"))

    for name in sorted(catalog_names):
        a = by_name.get(name)
        if not a:
            continue
        have = {r[0] for r in conn.execute(
            "SELECT alternative_exercise_id FROM exercise_substitutions WHERE exercise_id = ?", (a["id"],))}
        ranked, loose = [], []
        for b in rows:
            if b["id"] == a["id"] or not b.get("is_active", 1) or norm(b["name"]) not in catalog_names:
                continue
            score, level, reason = score_pair(a, b)
            if score > 0 and level in ("pattern", "muscle"):
                ranked.append((score, b, level, reason))
            elif score > 0:
                loose.append((score, b, level, reason))
        ranked.sort(key=lambda t: (-t[0], t[1]["name"]))
        loose.sort(key=lambda t: (-t[0], t[1]["name"]))
        picked = ranked[:AUTO_MAX_PER_EXERCISE]
        # Ejercicios casi únicos en su patrón/músculo: se completan hasta 3 con los de grupo parecido.
        covered = have | {t[1]["id"] for t in picked}
        for t in loose:
            if len(covered) >= AUTO_MIN_PER_EXERCISE:
                break
            if t[1]["id"] not in covered:
                picked.append(t)
                covered.add(t[1]["id"])
        for score, b, level, reason in picked:
            if b["id"] in have:
                continue
            report["auto"] += insert(a, b, score, reason, "auto", level == "pattern", level in ("pattern", "muscle"))

    # Parejas heredadas (21 curadas a mano antes de la Fase 7): rellenar su puntuación.
    conn.execute(
        """
        UPDATE exercise_substitutions
        SET score = CASE priority WHEN 1 THEN 90 WHEN 2 THEN 75 ELSE 60 END
        WHERE score IS NULL
        """
    )
    conn.commit()
    return report


def backfill_prefs_from_history(conn: sqlite3.Connection) -> int:
    """Convierte las sustituciones ya hechas en preferencias (solo las que falten)."""
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO user_substitution_prefs
            (user_id, original_exercise_id, substitute_exercise_id, routine_id, times_used, last_used_at, always_use)
        SELECT wl.user_id, s.original_exercise_id, s.substitute_exercise_id, '',
               COUNT(*), MAX(COALESCE(s.created_at, wl.date)), 0
        FROM workout_exercise_substitutions s
        JOIN workout_logs wl ON wl.id = s.workout_log_id
        GROUP BY wl.user_id, s.original_exercise_id, s.substitute_exercise_id
        """
    )
    conn.commit()
    return cur.rowcount


def ensure_substitutions(conn: sqlite3.Connection) -> dict:
    ensure_substitution_schema(conn)
    report = seed_substitutions(conn)
    report["prefs_backfilled"] = backfill_prefs_from_history(conn)
    return report


# ------------------------------------------------------------------ preferencias / equipo
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def record_substitution_pref(conn, user_id, original_id, substitute_id, routine_id=None, always=None) -> None:
    """Suma un uso a la preferencia global (routine_id='') y, si procede, fija «usar siempre» en la rutina."""
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO user_substitution_prefs
            (user_id, original_exercise_id, substitute_exercise_id, routine_id, times_used, last_used_at, always_use)
        VALUES (?, ?, ?, '', 1, ?, 0)
        ON CONFLICT(user_id, original_exercise_id, substitute_exercise_id, routine_id) DO UPDATE SET
            times_used = times_used + 1, last_used_at = excluded.last_used_at
        """,
        (user_id, original_id, substitute_id, ts),
    )
    if always is True and routine_id:
        # Solo una sustitución fija por hueco de rutina.
        conn.execute(
            "DELETE FROM user_substitution_prefs WHERE user_id=? AND original_exercise_id=? AND routine_id=?",
            (user_id, original_id, routine_id),
        )
        conn.execute(
            """
            INSERT INTO user_substitution_prefs
                (user_id, original_exercise_id, substitute_exercise_id, routine_id, times_used, last_used_at, always_use)
            VALUES (?, ?, ?, ?, 1, ?, 1)
            """,
            (user_id, original_id, substitute_id, routine_id, ts),
        )
    elif always is False and routine_id:
        conn.execute(
            "DELETE FROM user_substitution_prefs WHERE user_id=? AND original_exercise_id=? AND routine_id=?",
            (user_id, original_id, routine_id),
        )


def load_prefs(conn, user_id, original_id) -> dict[str, dict]:
    """substitute_id -> {times_used, last_used_at} agregando todos los ámbitos."""
    out: dict[str, dict] = {}
    for r in conn.execute(
        """
        SELECT substitute_exercise_id AS sid, SUM(times_used) AS n, MAX(last_used_at) AS last_at
        FROM user_substitution_prefs
        WHERE user_id = ? AND original_exercise_id = ?
        GROUP BY substitute_exercise_id
        """,
        (user_id, original_id),
    ):
        out[r["sid"]] = {"times_used": int(r["n"] or 0), "last_used_at": r["last_at"]}
    return out


def unavailable_equipment(conn, user_id) -> set[str]:
    return {r["equipment"] for r in conn.execute(
        "SELECT equipment FROM user_equipment WHERE user_id = ? AND available = 0", (user_id,))}


def is_unavailable(equipment, unavailable: set[str]) -> bool:
    fams = equipment_families(equipment)
    return bool(fams) and fams <= unavailable


def apply_always_substitutions(conn, workout_id: str, user_id: str, routine_id: str | None) -> int:
    """Al empezar un entreno NUEVO: aplica las sustituciones marcadas «usar siempre» en esa rutina."""
    if not routine_id:
        return 0
    n = 0
    for p in conn.execute(
        """
        SELECT p.original_exercise_id, p.substitute_exercise_id
        FROM user_substitution_prefs p
        JOIN routine_exercises re ON re.routine_id = p.routine_id AND re.exercise_id = p.original_exercise_id
        JOIN exercises e ON e.id = p.substitute_exercise_id AND e.is_active = 1
        WHERE p.user_id = ? AND p.routine_id = ? AND p.always_use = 1
          AND NOT EXISTS (SELECT 1 FROM routine_exercises r2
                          WHERE r2.routine_id = p.routine_id AND r2.exercise_id = p.substitute_exercise_id)
        """,
        (user_id, routine_id),
    ).fetchall():
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO workout_exercise_substitutions
                (id, workout_log_id, original_exercise_id, substitute_exercise_id, reason)
            VALUES (?, ?, ?, ?, 'Sustitución habitual de esta rutina')
            """,
            (str(uuid.uuid4()), workout_id, p["original_exercise_id"], p["substitute_exercise_id"]),
        )
        n += cur.rowcount
    return n


# ------------------------------------------------------------------ ranking
def rank_substitutes(conn, user_id, exercise_id, workout_id=None, routine_id=None, q=None,
                     include_all=False, limit=None) -> dict:
    meta = {r["id"]: r for r in _exercise_meta(conn)}
    orig = meta.get(exercise_id)
    if not orig or not orig.get("is_active"):
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")

    if workout_id and not routine_id:
        wl = conn.execute("SELECT routine_id FROM workout_logs WHERE id = ?", (workout_id,)).fetchone()
        routine_id = wl["routine_id"] if wl else None
    in_session: set[str] = set()
    if routine_id:
        in_session |= {r[0] for r in conn.execute(
            "SELECT exercise_id FROM routine_exercises WHERE routine_id = ?", (routine_id,))}
    if workout_id:
        in_session |= {r[0] for r in conn.execute(
            "SELECT exercise_id FROM workout_extra_exercises WHERE workout_log_id = ?", (workout_id,))}
        in_session |= {r[0] for r in conn.execute(
            "SELECT substitute_exercise_id FROM workout_exercise_substitutions WHERE workout_log_id = ?",
            (workout_id,))}
    in_session.discard(exercise_id)

    table = {r["alternative_exercise_id"]: r for r in conn.execute(
        """SELECT alternative_exercise_id, score, reason, source, same_muscle, same_movement_pattern
           FROM exercise_substitutions WHERE exercise_id = ? AND is_active = 1""", (exercise_id,))}
    prefs = load_prefs(conn, user_id, exercise_id)
    habitual = None
    if prefs:
        habitual = max(prefs, key=lambda s: (prefs[s]["times_used"], prefs[s]["last_used_at"] or ""))
    always_row = conn.execute(
        """SELECT substitute_exercise_id FROM user_substitution_prefs
           WHERE user_id = ? AND original_exercise_id = ? AND routine_id = ? AND always_use = 1""",
        (user_id, exercise_id, routine_id or "__none__"),
    ).fetchone()
    always_id = always_row["substitute_exercise_id"] if always_row else None
    unavailable = unavailable_equipment(conn, user_id)
    location = "gimnasio"
    home_avail = set()
    try:
        from .casa import routine_location, load_home_available
        location = routine_location(conn, routine_id) if routine_id else "gimnasio"
        if location == "casa":
            home_avail = load_home_available(conn, user_id)
    except Exception:
        location, home_avail = "gimnasio", set()
    progress = {}
    try:
        for r in conn.execute("SELECT exercise_id, next_weight_kg, next_reps FROM exercise_progress WHERE user_id = ?",
                              (user_id,)):
            progress[r["exercise_id"]] = (r["next_weight_kg"], r["next_reps"])
    except sqlite3.OperationalError:
        pass

    needle = norm(q) if q else ""
    items = []
    for cid, cand in meta.items():
        if cid == exercise_id or not cand.get("is_active") or cid in in_session:
            continue
        if needle and needle not in norm(cand["name"]) and needle not in norm(cand.get("equipment")) \
                and needle not in norm(cand.get("target_muscle")):
            continue
        score, level, reason = score_pair(orig, cand)
        row = table.get(cid)
        if row is not None:
            if (row["score"] or 0) > score:
                score = int(row["score"])
            if row["reason"]:
                reason = row["reason"]
            if row["same_movement_pattern"] and level not in ("pattern",):
                level = "pattern"
            elif row["same_muscle"] and level in ("related", "other"):
                level = "muscle"
        pref = prefs.get(cid)
        home_doable = True
        if location == "casa":
            from .casa import is_home_doable
            home_doable = is_home_doable(cand.get("name"), cand.get("equipment"), home_avail)
            if home_doable:
                score += HOME_FIT_BONUS
        suggested = level != "other" or row is not None or pref is not None
        if not suggested and not (include_all or needle):
            continue
        w, reps = progress.get(cid, (None, None))
        gym_unavail = is_unavailable(cand.get("equipment"), unavailable)
        items.append({
            "exercise_id": cid,
            "name": cand["name"],
            "target_muscle": cand.get("target_muscle"),
            "category": cand.get("category"),
            "equipment": cand.get("equipment"),
            "movement_pattern": cand.get("movement_pattern"),
            "score": score,
            "match_level": level,
            "reason": reason or "Otro ejercicio del catálogo.",
            "same_muscle": level in ("pattern", "muscle"),
            "same_movement_pattern": level == "pattern",
            "suggested": suggested,
            "curated": bool(row is not None and row["source"] != "auto"),
            "is_habitual": cid == habitual,
            "previously_used": pref is not None,
            "times_used": pref["times_used"] if pref else 0,
            "always_in_routine": cid == always_id,
            "unavailable_equipment": gym_unavail or (location == "casa" and not home_doable),
            "home_doable": home_doable if location == "casa" else None,
            "suggested_weight_kg": w,
            "suggested_reps": reps,
            "priority": 1 if score >= 85 else 2 if score >= 65 else 3,
        })

    def key(it):
        rank = HABITUAL_BONUS if it["is_habitual"] else (HABITUAL_BONUS / 10 if it["previously_used"] else 0)
        return (it["unavailable_equipment"], -(it["score"] + rank), it["name"])

    items.sort(key=key)
    if limit:
        items = items[:limit]
    orig_unavailable = is_unavailable(orig.get("equipment"), unavailable)
    if location == "casa":
        from .casa import is_home_doable as _ihd
        orig_unavailable = orig_unavailable or (not _ihd(orig.get("name"), orig.get("equipment"), home_avail))
    proposed = next((i["exercise_id"] for i in items if i["suggested"] and not i["unavailable_equipment"]), None)
    return {
        "exercise_id": orig["id"],
        "exercise_name": orig["name"],
        "equipment": orig.get("equipment"),
        "original_unavailable": orig_unavailable,
        "proposed_exercise_id": proposed if orig_unavailable else None,
        "unavailable_equipment": sorted(unavailable),
        "substitutions": items,
    }


# ------------------------------------------------------------------ recomendación del hueco
def recommendation_item(conn, user_id, routine_id, workout_id, slot, exercise) -> dict:
    """Elemento de /recommendations para ``exercise`` ocupando el hueco ``slot`` de la rutina.

    ``slot`` aporta orden y objetivo (series, reps, RIR); ``exercise`` es el ejercicio que de verdad se
    hace (el original o su sustituto): carga, incremento e historial salen de ÉL.
    """
    result, _cfg = compute_exercise_target(conn, user_id, exercise["id"], routine_id=routine_id, workout_id=workout_id)
    item = {
        "exercise_id": exercise["id"],
        "exercise_name": exercise["name"],
        "order": slot["order"],
        "target_sets": slot["target_sets"],
        "target_rep_min": slot["target_rep_min"],
        "target_rep_max": slot["target_rep_max"],
        "target_rir": slot["target_rir"],
        "weight_increment_kg": exercise["weight_increment_kg"],
        "progression_type": exercise["progression_type"],
        "rep_progression_enabled": bool(exercise["rep_progression_enabled"]),
        "measure_type": result["measure_type"],
        "unit": result["unit"],
        "increment_kg": result["increment_kg"],
        "weight_steps": result.get("weight_steps", []),
        "fail_streak": result["fail_streak"],
    }
    last_performance = None
    if result["last_workout"]:
        last_sets = conn.execute(
            """SELECT set_number, weight_kg, reps, rir FROM workout_sets
               WHERE workout_log_id = ? AND exercise_id = ? AND is_warmup = 0 ORDER BY set_number""",
            (result["last_workout"]["workout_id"], exercise["id"]),
        ).fetchall()
        last_performance = {
            "workout_id": result["last_workout"]["workout_id"],
            "date": result["last_workout"]["date"],
            "sets": [{"set_number": int(r["set_number"]), "weight_kg": float(r["weight_kg"] or 0),
                      "reps": int(r["reps"] or 0), "rir": r["rir"]} for r in last_sets],
        }
    item.update({
        "recommendation": "add_reps" if result["kind"] == "add_time" else result["kind"],
        "recommended_weight_kg": result["weight_kg"],
        "recommended_rep_target": result["reps"],
        "reason": result["reason"],
        "last_performance": last_performance,
    })
    return item


EXERCISE_REC_COLUMNS = "e.id, e.name, e.weight_increment_kg, e.progression_type, e.rep_progression_enabled"


def slot_for(conn, routine_id, original_id):
    return conn.execute(
        """SELECT re."order" AS "order", re.target_sets, re.target_rep_min, re.target_rep_max,
                  re.target_rir, re.rest_seconds, re.is_optional
           FROM routine_exercises re WHERE re.routine_id = ? AND re.exercise_id = ?""",
        (routine_id, original_id),
    ).fetchone()


def enrich_substitutions(conn, user_id, workout_id, substitutions: list[dict]) -> list[dict]:
    """Añade a cada sustitución del entreno el historial y la recomendación DEL SUSTITUTO."""
    wl = conn.execute("SELECT routine_id FROM workout_logs WHERE id = ?", (workout_id,)).fetchone()
    routine_id = wl["routine_id"] if wl else None
    for sub in substitutions:
        slot = slot_for(conn, routine_id, sub["original_exercise_id"]) if routine_id else None
        ex = conn.execute(f"SELECT {EXERCISE_REC_COLUMNS} FROM exercises e WHERE e.id = ?",
                          (sub["substitute_exercise_id"],)).fetchone()
        if slot is None or ex is None:
            sub["recommendation"] = None
            sub["last_performance"] = None
            continue
        rec = recommendation_item(conn, user_id, routine_id, workout_id, slot, ex)
        rec["original_exercise_id"] = sub["original_exercise_id"]
        rec["substituted"] = True
        sub["recommendation"] = rec
        sub["last_performance"] = rec["last_performance"]
        sub["target"] = {"sets": slot["target_sets"], "rep_min": slot["target_rep_min"],
                         "rep_max": slot["target_rep_max"], "rir": slot["target_rir"],
                         "rest_seconds": slot["rest_seconds"], "is_optional": bool(slot["is_optional"])}
    return substitutions


# ------------------------------------------------------------------ rutas
@router.get("/api/exercises/{exercise_id}/substitutions")
def get_exercise_substitutions(
    exercise_id: str,
    user_id: str | None = None,
    workout_id: str | None = None,
    routine_id: str | None = None,
    q: str | None = None,
    all: bool = False,
    limit: int | None = Query(default=None, ge=1, le=200),
    current_user=Depends(get_authenticated_user),
):
    """Alternativas ordenadas por parecido. ``q`` busca en TODO el catálogo; ``all=1`` lo devuelve entero."""
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM users WHERE id = ?", (user_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        if workout_id:
            wl = conn.execute("SELECT user_id FROM workout_logs WHERE id = ?", (workout_id,)).fetchone()
            if not wl or wl["user_id"] != user_id:
                raise HTTPException(status_code=404, detail="Entrenamiento no encontrado")
        return rank_substitutes(conn, user_id, exercise_id, workout_id=workout_id, routine_id=routine_id,
                                q=q, include_all=all, limit=limit)
    finally:
        conn.close()


class EquipmentIn(BaseModel):
    unavailable: list[str]


@router.get("/api/user-equipment")
def get_user_equipment(user_id: str | None = None, current_user=Depends(get_authenticated_user)):
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        return {"families": EQUIPMENT_FAMILIES, "unavailable": sorted(unavailable_equipment(conn, user_id))}
    finally:
        conn.close()


@router.put("/api/user-equipment")
def put_user_equipment(body: EquipmentIn, user_id: str | None = None, current_user=Depends(get_authenticated_user)):
    user_id = resolve_target_user(current_user, user_id)
    wanted = {norm(x) for x in body.unavailable}
    unknown = wanted - set(EQUIPMENT_FAMILIES)
    if unknown:
        raise HTTPException(status_code=400, detail="Equipo desconocido: " + ", ".join(sorted(unknown)))
    conn = get_connection()
    try:
        ts = now_iso()
        for fam in EQUIPMENT_FAMILIES:
            conn.execute(
                """INSERT INTO user_equipment (user_id, equipment, available, updated_at) VALUES (?, ?, ?, ?)
                   ON CONFLICT(user_id, equipment) DO UPDATE SET available = excluded.available, updated_at = excluded.updated_at""",
                (user_id, fam, 0 if fam in wanted else 1, ts),
            )
        conn.commit()
        return {"families": EQUIPMENT_FAMILIES, "unavailable": sorted(wanted)}
    finally:
        conn.close()


@router.delete("/api/routines/{routine_id}/always-substitution/{original_exercise_id}")
def delete_always_substitution(routine_id: str, original_exercise_id: str, user_id: str | None = None,
                               current_user=Depends(get_authenticated_user)):
    """Quita el «usar siempre esta sustitución en esta rutina» (no toca los entrenos ya hechos)."""
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM user_substitution_prefs WHERE user_id=? AND original_exercise_id=? AND routine_id=? AND always_use=1",
            (user_id, original_exercise_id, routine_id),
        )
        conn.commit()
        return {"ok": True, "removed": cur.rowcount}
    finally:
        conn.close()
