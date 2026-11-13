"""Gráficas de progreso: 1RM estimado, volumen semanal y equilibrio (Fase 11).

Solo series de trabajo (is_warmup = 0) de entrenos completados. Los calentamientos
no entran ni en el 1RM ni en el volumen. Los deload sí aparecen (marcados).
"""
from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta

from .progression import infer_measure_type

RANGE_DAYS = {"4w": 28, "12w": 84, "all": None}
DEFAULT_VOLUME_WEEKS = 12
MIN_VOLUME_WEEKS = 8
MAX_VOLUME_WEEKS = 12
REFERENCE_MIN_SETS = 10
REFERENCE_MAX_SETS = 20

# Etiqueta visible → músculo del mapa (Fase 9b) y cubo de equilibrio.
GROUP_META = {
    "Pecho": {"muscle_id": "chest", "bucket": "push", "side": "upper"},
    "Hombros": {"muscle_id": "front_deltoid", "bucket": "push", "side": "upper"},
    "Deltoides posterior": {"muscle_id": "rear_deltoid", "bucket": "pull", "side": "upper"},
    "Espalda": {"muscle_id": "lats", "bucket": "pull", "side": "upper"},
    "Trapecio": {"muscle_id": "trapezius", "bucket": "pull", "side": "upper"},
    "Bíceps": {"muscle_id": "biceps", "bucket": "pull", "side": "upper"},
    "Tríceps": {"muscle_id": "triceps", "bucket": "push", "side": "upper"},
    "Antebrazo": {"muscle_id": "forearm", "bucket": "pull", "side": "upper"},
    "Core": {"muscle_id": "abs", "bucket": None, "side": "upper"},
    "Cuádriceps": {"muscle_id": "quadriceps", "bucket": None, "side": "lower"},
    "Glúteos": {"muscle_id": "glutes", "bucket": None, "side": "lower"},
    "Isquios": {"muscle_id": "hamstrings", "bucket": None, "side": "lower"},
    "Aductores": {"muscle_id": "adductors", "bucket": None, "side": "lower"},
    "Gemelos": {"muscle_id": "calves", "bucket": None, "side": "lower"},
}

# Palabras clave (ya normalizadas, sin tildes) → grupo. El orden importa:
# se usa la primera coincidencia de cada trozo del texto.
_MUSCLE_NEEDLES = (
    ("deltoides posterior", "Deltoides posterior"),
    ("deltoides lateral", "Hombros"),
    ("deltoides", "Hombros"),
    ("hombro", "Hombros"),
    ("pectoral", "Pecho"),
    ("pecho", "Pecho"),
    ("dorsal", "Espalda"),
    ("espalda", "Espalda"),
    ("trapecio", "Trapecio"),
    ("triceps", "Tríceps"),
    ("biceps", "Bíceps"),
    ("braquial", "Bíceps"),
    ("antebrazo", "Antebrazo"),
    ("gluteo", "Glúteos"),
    ("isquio", "Isquios"),
    ("femoral", "Isquios"),
    ("cuadriceps", "Cuádriceps"),
    ("aductor", "Aductores"),
    ("gemelo", "Gemelos"),
    ("core", "Core"),
    ("abdominal", "Core"),
    ("oblicuo", "Core"),
    ("recto", "Core"),
    ("lumbar", "Espalda"),
)


def _norm(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def _split_muscle_text(text) -> list[str]:
    raw = str(text or "")
    for sep in (" y ", " Y ", ",", "/", "+", "&"):
        raw = raw.replace(sep, "|")
    return [p.strip() for p in raw.split("|") if p.strip()]


def muscle_groups_from_text(text) -> list[str]:
    """Grupos (únicos, en orden) mencionados en un campo de músculo."""
    found: list[str] = []
    for part in _split_muscle_text(text) or [str(text or "")]:
        n = _norm(part)
        if not n:
            continue
        for needle, group in _MUSCLE_NEEDLES:
            if needle in n:
                if group not in found:
                    found.append(group)
                break
    return found


def parse_secondary(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        parts = [str(v) for v in value]
    else:
        text = str(value).strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                data = json.loads(text)
                if isinstance(data, list):
                    parts = [str(v) for v in data]
                else:
                    parts = [text]
            except (json.JSONDecodeError, TypeError):
                parts = _split_muscle_text(text)
        else:
            parts = _split_muscle_text(text)
    groups: list[str] = []
    for part in parts:
        for g in muscle_groups_from_text(part):
            if g not in groups:
                groups.append(g)
    return groups


def epley(weight: float, reps: int) -> float:
    if weight <= 0 or reps <= 0:
        return 0.0
    if reps == 1:
        return round(float(weight), 1)
    return round(float(weight) * (1 + int(reps) / 30), 1)


def parse_day(value) -> date | None:
    if not value:
        return None
    text = str(value).replace("Z", "")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").date()
        except ValueError:
            return None


def range_start(range_key: str, today: date | None = None) -> date | None:
    key = (range_key or "12w").lower()
    days = RANGE_DAYS.get(key, RANGE_DAYS["12w"])
    if days is None:
        return None
    return (today or date.today()) - timedelta(days=days)


def clamp_weeks(weeks) -> int:
    try:
        n = int(weeks)
    except (TypeError, ValueError):
        n = DEFAULT_VOLUME_WEEKS
    return max(MIN_VOLUME_WEEKS, min(MAX_VOLUME_WEEKS, n))


def week_start_of(day: date) -> date:
    return day - timedelta(days=day.weekday())  # lunes


def week_window(weeks: int, today: date | None = None) -> list[date]:
    today = today or date.today()
    current = week_start_of(today)
    starts = [current - timedelta(weeks=i) for i in range(weeks)]
    starts.reverse()
    return starts


def effective_contributions(target_muscle, secondary_muscles=None) -> list[tuple[str, float]]:
    """Series efectivas: 1,0 por grupo primario, 0,5 por secundario (si no es ya primario)."""
    primary = muscle_groups_from_text(target_muscle)
    secondary = [g for g in parse_secondary(secondary_muscles) if g not in primary]
    out = [(g, 1.0) for g in primary]
    out.extend((g, 0.5) for g in secondary)
    if not out:
        out = [("Otros", 1.0)]
    return out


def session_point(sets: list[dict], measure: str, is_deload: bool, workout_id, day: date) -> dict | None:
    """Resume una sesión (solo series de trabajo ya filtradas)."""
    work = []
    for s in sets or []:
        try:
            reps = int(s.get("reps") or 0)
        except (TypeError, ValueError):
            reps = 0
        if reps <= 0:
            continue
        try:
            weight = float(s.get("weight_kg") or 0)
        except (TypeError, ValueError):
            weight = 0.0
        work.append({"weight_kg": weight, "reps": reps})
    if not work:
        return None
    if measure == "time":
        best_time = max(s["reps"] for s in work)
        return {
            "date": day.isoformat(),
            "workout_id": workout_id,
            "measure_type": "time",
            "best_time_s": best_time,
            "e1rm": None,
            "top_weight_kg": None,
            "volume_kg": 0.0,
            "top_reps": None,
            "working_sets": len(work),
            "is_deload": bool(is_deload),
        }
    top_weight = max(s["weight_kg"] for s in work)
    volume = round(sum(s["weight_kg"] * s["reps"] for s in work), 1)
    best = 0.0
    top_reps = 0
    for s in work:
        est = epley(s["weight_kg"], s["reps"])
        if est > best:
            best = est
            top_reps = s["reps"]
        elif abs(s["weight_kg"] - top_weight) < 1e-6:
            top_reps = max(top_reps, s["reps"])
    return {
        "date": day.isoformat(),
        "workout_id": workout_id,
        "measure_type": measure,
        "best_time_s": None,
        "e1rm": best if best > 0 else None,
        "top_weight_kg": top_weight,
        "volume_kg": volume,
        "top_reps": top_reps,
        "working_sets": len(work),
        "is_deload": bool(is_deload),
    }


def exercise_history(conn, user_id: str, exercise_id: str, range_key: str = "12w", today: date | None = None) -> dict:
    today = today or date.today()
    start = range_start(range_key, today)
    cols = _exercise_columns(conn)
    select = ", ".join(
        c for c in ("id", "name", "target_muscle", "equipment", "exercise_type",
                    "measure_type", "weight_increment_kg", "secondary_muscles")
        if c in cols
    )
    ex = conn.execute(f"SELECT {select} FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if ex is None:
        return None

    exd = {k: ex[k] for k in ex.keys()}
    measure = exd.get("measure_type") or infer_measure_type(exd.get("name"), exd.get("equipment"))

    params: list = [user_id, exercise_id]
    date_filter = ""
    if start is not None:
        date_filter = "AND substr(wl.date, 1, 10) >= ?"
        params.append(start.isoformat())

    rows = conn.execute(
        f"""
        SELECT wl.id AS workout_id, wl.date, COALESCE(wl.is_deload, 0) AS is_deload,
               ws.weight_kg, ws.reps, COALESCE(ws.is_warmup, 0) AS is_warmup
        FROM workout_sets ws
        JOIN workout_logs wl ON wl.id = ws.workout_log_id
        WHERE wl.user_id = ?
          AND ws.exercise_id = ?
          AND wl.status = 'completed'
          {date_filter}
        ORDER BY datetime(wl.date) ASC, wl.id ASC, ws.set_number ASC
        """,
        params,
    ).fetchall()

    by_workout: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        if r["is_warmup"]:
            continue
        wid = r["workout_id"]
        if wid not in by_workout:
            day = parse_day(r["date"]) or today
            by_workout[wid] = {
                "date": day,
                "is_deload": bool(r["is_deload"]),
                "sets": [],
            }
            order.append(wid)
        by_workout[wid]["sets"].append({"weight_kg": r["weight_kg"], "reps": r["reps"]})

    points = []
    for wid in order:
        block = by_workout[wid]
        pt = session_point(block["sets"], measure, block["is_deload"], wid, block["date"])
        if pt:
            points.append(pt)

    return {
        "exercise_id": exercise_id,
        "name": exd.get("name"),
        "target_muscle": exd.get("target_muscle"),
        "equipment": exd.get("equipment"),
        "measure_type": measure,
        "range": range_key if range_key in RANGE_DAYS else "12w",
        "unit": "s" if measure == "time" else "kg",
        "sessions": points,
        "count": len(points),
    }


def _exercise_columns(conn) -> set[str]:
    return {r["name"] for r in conn.execute("PRAGMA table_info(exercises)")}


def weekly_volume(conn, user_id: str, weeks: int = DEFAULT_VOLUME_WEEKS, today: date | None = None) -> dict:
    today = today or date.today()
    weeks = clamp_weeks(weeks)
    starts = week_window(weeks, today)
    window_from = starts[0].isoformat()

    cols = _exercise_columns(conn)
    sec_sql = "e.secondary_muscles" if "secondary_muscles" in cols else "NULL AS secondary_muscles"
    measure_sql = "e.measure_type" if "measure_type" in cols else "NULL AS measure_type"

    rows = conn.execute(
        f"""
        SELECT substr(wl.date, 1, 10) AS day,
               e.target_muscle,
               {sec_sql},
               {measure_sql},
               e.name,
               COUNT(*) AS sets
        FROM workout_sets ws
        JOIN workout_logs wl ON wl.id = ws.workout_log_id
        JOIN exercises e ON e.id = ws.exercise_id
        WHERE wl.user_id = ?
          AND wl.status = 'completed'
          AND COALESCE(ws.is_warmup, 0) = 0
          AND COALESCE(ws.reps, 0) > 0
          AND substr(wl.date, 1, 10) >= ?
        GROUP BY substr(wl.date, 1, 10), e.id
        """,
        (user_id, window_from),
    ).fetchall()

    # week_start iso → group → sets
    buckets: dict[str, dict[str, float]] = {s.isoformat(): defaultdict(float) for s in starts}
    for r in rows:
        day = parse_day(r["day"])
        if day is None:
            continue
        ws = week_start_of(day).isoformat()
        if ws not in buckets:
            continue
        measure = r["measure_type"] or infer_measure_type(r["name"], None)
        # Los isométricos no aportan series de carga, pero sí cuentan como serie
        # efectiva de core (o del grupo que toque).
        for group, credit in effective_contributions(r["target_muscle"], r["secondary_muscles"]):
            buckets[ws][group] += credit * int(r["sets"] or 0)
            # measure unused except we still count time holds as sets.

    group_names: list[str] = []
    for week_data in buckets.values():
        for g in week_data:
            if g not in group_names:
                group_names.append(g)
    # Orden estable: los del catálogo primero, "Otros" al final.
    catalog = [g for g in GROUP_META if g in group_names]
    extra = [g for g in group_names if g not in GROUP_META]
    group_names = catalog + extra

    weeks_out = []
    totals = defaultdict(float)
    for start in starts:
        key = start.isoformat()
        groups = {g: round(buckets[key].get(g, 0.0), 2) for g in group_names}
        for g, v in groups.items():
            totals[g] += v
        weeks_out.append({
            "week_start": key,
            "week_label": f"{start.day:02d}/{start.month:02d}",
            "groups": groups,
            "total_sets": round(sum(groups.values()), 2),
        })

    averages = {g: round(totals[g] / weeks, 2) for g in group_names}

    def sum_bucket(pred) -> float:
        return round(sum(averages.get(g, 0.0) for g in group_names if pred(g)), 2)

    def meta(g):
        return GROUP_META.get(g, {"bucket": None, "side": None, "muscle_id": None})

    push = sum_bucket(lambda g: meta(g)["bucket"] == "push")
    pull = sum_bucket(lambda g: meta(g)["bucket"] == "pull")
    upper = sum_bucket(lambda g: meta(g)["side"] == "upper")
    lower = sum_bucket(lambda g: meta(g)["side"] == "lower")

    notes = []
    if push and pull:
        ratio = push / pull if pull else None
        if ratio and ratio >= 1.5:
            notes.append("Empujas bastante más de lo que tiras; conviene vigilar el volumen de espalda.")
        elif ratio and ratio <= (1 / 1.5):
            notes.append("Tiras bastante más de lo que empujas; el volumen de empuje va por detrás.")
    if upper and lower:
        ratio = upper / lower if lower else None
        if ratio and ratio >= 1.8:
            notes.append("El tren superior acumula bastante más series que el inferior.")
        elif ratio and ratio <= (1 / 1.8):
            notes.append("El tren inferior acumula bastante más series que el superior.")

    heat = {}
    for g, avg in averages.items():
        mid = meta(g).get("muscle_id")
        if not mid:
            continue
        # 0 en 0 series, 1 en el techo de la banda de referencia (20).
        heat[mid] = round(min(1.0, avg / REFERENCE_MAX_SETS), 3)

    return {
        "weeks": weeks,
        "week_start": starts[0].isoformat(),
        "week_end": (starts[-1] + timedelta(days=6)).isoformat(),
        "groups": group_names,
        "reference": {"min_sets": REFERENCE_MIN_SETS, "max_sets": REFERENCE_MAX_SETS},
        "items": weeks_out,
        "averages": averages,
        "balance": {
            "push": push,
            "pull": pull,
            "upper": upper,
            "lower": lower,
            "notes": notes,
        },
        "heat": heat,
    }
