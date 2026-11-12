"""Doble progresión ÚNICA (Fase 6).

``apply_progression`` (al completar/recalcular un entreno), ``/api/routines/{id}/recommendations``
y ``/api/progress/home`` usan SOLO ``next_target``: una función pura, sin acceso a BD.

Regla (ejercicios con carga):
  1. Todas las series >= máximo del rango y RIR >= objetivo  -> sube el peso un incremento
     y vuelve al mínimo de reps.
  2. Alguna serie < mínimo                                    -> mantiene la carga.
     Si ya falló también la sesión anterior                   -> deload (-10 %) o mantiene.
  3. En medio                                                 -> +1 rep por serie hasta el máximo.
  4. Máximo alcanzado pero RIR por debajo del objetivo        -> mantiene.
Por tiempo (isométricos): igual con segundos (+5 s por sesión) y, al llegar al máximo, lastre
si el ejercicio tiene incremento (o "añade una serie / variante más difícil").
Peso corporal (peso 0): reps hasta el máximo y entonces el primer lastre.

measure_type: 'reps' (carga externa + reps), 'bodyweight' (peso corporal), 'time' (segundos).
weight_increment_kg: paso de carga en kg (0 = no se carga: solo reps/tiempo).
"""
from __future__ import annotations

import re
import unicodedata

TIME_STEP_SECONDS = 5
DEFAULT_REP_RANGE = (8, 12)
DEFAULT_TIME_RANGE = (30, 60)
DEFAULT_RIR = 2
DELOAD_FACTOR = 0.9
MEASURE_TYPES = ("reps", "time", "bodyweight")

_TIME_KEYWORDS = (
    "plancha", "isometric", "wall sit", "sentadilla en pared", "dead hang", "colgado estatic",
    "hollow hold", "l-sit", "mantenid",
)


def _norm(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def equipment_class(equipment) -> str:
    """barbell | dumbbell | machine | cable | bodyweight | other (por el primer equipo citado)."""
    first = re.split(r"\s+o\s+|/|,|\+", _norm(equipment))[0].strip()
    if not first:
        return "other"
    if first.startswith("peso corporal") or first.startswith("bodyweight") or first.startswith("calistenia"):
        return "bodyweight"
    if first.startswith("mancuerna") or first.startswith("kettlebell") or first.startswith("pesa rusa"):
        return "dumbbell"
    if first.startswith("barra") or first.startswith("smith") or first.startswith("multipower"):
        return "barbell"
    if first.startswith("polea") or first.startswith("cable"):
        return "cable"
    if first.startswith("maquina"):
        return "machine"
    return "other"


def infer_measure_type(name, equipment=None) -> str:
    n = _norm(name)
    if any(k in n for k in _TIME_KEYWORDS):
        return "time"
    if equipment_class(equipment) == "bodyweight":
        return "bodyweight"
    return "reps"


def default_increment(equipment, exercise_type=None, measure_type=None) -> float:
    """Incremento de carga por defecto (kg) cuando el ejercicio no tiene weight_increment_kg."""
    measure = measure_type or "reps"
    if measure == "time":
        return 0.0
    cls = equipment_class(equipment)
    isolation = _norm(exercise_type) in ("aislamiento", "core")
    if measure == "bodyweight" or cls == "bodyweight":
        return 0.0 if _norm(exercise_type) == "core" else 2.5   # lastre (dominadas, fondos...)
    if cls == "barbell":
        return 2.5
    if cls == "dumbbell":
        return 1.0 if isolation else 2.0           # peso por mancuerna
    if cls in ("machine", "cable"):
        return 2.5 if isolation else 5.0           # paso de la placa
    return 2.5


def resolve_increment(ex: dict) -> float:
    """Incremento efectivo: el del ejercicio si es > 0; si no, el del tipo de equipo."""
    measure = ex.get("measure_type") or infer_measure_type(ex.get("name"), ex.get("equipment"))
    stored = ex.get("weight_increment_kg")
    try:
        stored = float(stored) if stored is not None else None
    except (TypeError, ValueError):
        stored = None
    if stored is not None and stored > 0:
        return stored
    if stored == 0 and measure in ("time", "bodyweight"):
        return 0.0     # 0 explícito: este ejercicio no se carga
    return default_increment(ex.get("equipment"), ex.get("exercise_type"), measure)


def fmt_num(value) -> str:
    """12.5 -> '12,5'; 12.0 -> '12' (formato español)."""
    text = f"{float(value):.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",")


def round_to_step(value: float, step: float) -> float:
    if step and step > 0:
        return round(round(value / step) * step, 2)
    return round(value, 2)


def deload_weight(weight: float, increment: float) -> float:
    """-10 % redondeado al paso de carga, siempre al menos un paso por debajo."""
    step = increment if increment and increment > 0 else 2.5
    lighter = round_to_step(weight * DELOAD_FACTOR, step)
    if lighter >= weight:
        lighter = round(weight - step, 2)
    return max(0.0, lighter)


def _clean_sets(sets) -> list[dict]:
    out = []
    for s in sets or []:
        if s.get("is_warmup"):
            continue
        reps = int(s.get("reps") or 0)
        if reps <= 0:
            continue
        out.append({"weight_kg": float(s.get("weight_kg") or 0), "reps": reps, "rir": s.get("rir")})
    return out


def _evaluate(sets: list[dict]) -> dict | None:
    """Series de trabajo a la carga máxima de la sesión (las más ligeras = back-off, se ignoran)."""
    work = _clean_sets(sets)
    if not work:
        return None
    top = max(s["weight_kg"] for s in work)
    top_sets = [s for s in work if abs(s["weight_kg"] - top) < 1e-6]
    rirs = [int(s["rir"]) for s in top_sets if s["rir"] is not None]
    return {
        "weight": top,
        "reps": [s["reps"] for s in top_sets],
        "rirs": rirs,
        "all_weights": [s["weight_kg"] for s in work],
    }


def _resolve_range(ex: dict, measure: str) -> tuple[int, int, int]:
    rep_min = ex.get("rep_min")
    rep_max = ex.get("rep_max")
    rir = ex.get("rir_target")
    if measure == "time":
        if not rep_min or not rep_max or rep_max < 20:       # rango de reps heredado: no son segundos
            rep_min, rep_max = DEFAULT_TIME_RANGE
    else:
        if not rep_min or not rep_max:
            rep_min, rep_max = DEFAULT_REP_RANGE
    rep_min, rep_max = int(rep_min), int(max(rep_max, rep_min))
    return rep_min, rep_max, int(rir) if rir is not None else DEFAULT_RIR


def _result(kind, weight, reps, reason, measure, unit, increment, fail_streak=0, **extra):
    data = {
        "kind": kind,
        "weight_kg": None if weight is None else round(float(weight), 2),
        "reps": reps,
        "reason": reason,
        "measure_type": measure,
        "unit": unit,
        "increment_kg": increment,
        "fail_streak": fail_streak,
    }
    data.update(extra)
    return data


def next_target(ex: dict, sessions: list[list[dict]]) -> dict:
    """Calcula el siguiente objetivo.

    ex: name, equipment, exercise_type, measure_type, weight_increment_kg, rep_min, rep_max, rir_target.
    sessions: series de las últimas sesiones COMPLETADAS (la más reciente primero); cada sesión es una
              lista de dicts {weight_kg, reps, rir, is_warmup}. Se usan como mucho las dos primeras.
    Devuelve dict(kind, weight_kg, reps, reason, measure_type, unit, increment_kg, fail_streak).
    kind: start | add_reps | add_time | increase_weight | maintain_weight | deload
    """
    measure = ex.get("measure_type") if ex.get("measure_type") in MEASURE_TYPES else None
    measure = measure or infer_measure_type(ex.get("name"), ex.get("equipment"))
    unit = "s" if measure == "time" else "reps"
    unit_txt = "s" if measure == "time" else " reps"
    rep_min, rep_max, rir_target = _resolve_range(ex, measure)
    inc = resolve_increment(ex)

    evaluated = [e for e in (_evaluate(s) for s in (sessions or [])[:2]) if e]
    if not evaluated:
        if measure == "time":
            reason = f"Sin historial: empieza con {rep_min} s por serie."
        elif measure == "bodyweight":
            reason = f"Sin historial: haz {rep_min}-{rep_max} reps con tu peso corporal dejando {rir_target} RIR."
        else:
            reason = f"Sin historial: elige un peso con el que hagas {rep_min}-{rep_max} reps dejando {rir_target} RIR."
        return _result("start", None, rep_min, reason, measure, unit, inc)

    last = evaluated[0]
    w = last["weight"]
    min_reps = min(last["reps"])
    rir_low = any(r < rir_target for r in last["rirs"])       # RIR ausente no bloquea
    failed = min_reps < rep_min
    prev_failed = len(evaluated) > 1 and min(evaluated[1]["reps"]) < rep_min
    fail_streak = (1 + (1 if prev_failed else 0)) if failed else 0
    loaded = w > 0
    kg = f"{fmt_num(w)} kg"

    # ---- Fallo: mantener; dos seguidos -> deload
    if failed:
        if fail_streak >= 2:
            if measure == "time":
                return _result("deload", w, rep_min,
                               f"Fallaste 2 sesiones seguidas (menos de {rep_min} s): baja a {rep_min} s y recupera la técnica.",
                               measure, unit, inc, fail_streak)
            if loaded:
                lighter = deload_weight(w, inc)
                if lighter < w:
                    return _result("deload", lighter, rep_min,
                                   f"Fallaste 2 sesiones seguidas con {kg} → baja a {fmt_num(lighter)} kg (deload) y vuelve a {rep_min} reps.",
                                   measure, unit, inc, fail_streak)
            return _result("deload", w, rep_min,
                           f"Fallaste 2 sesiones seguidas: haz {rep_min} reps limpias o usa una variante más fácil.",
                           measure, unit, inc, fail_streak)
        if measure == "time":
            reason = f"No llegaste a {rep_min} s en todas las series. Repite e intenta aguantar {rep_min} s."
        elif loaded:
            reason = f"No llegaste a {rep_min} reps en todas las series. Mantén {kg} e intenta {rep_min} reps."
        else:
            reason = f"No llegaste a {rep_min} reps en todas las series. Repite e intenta {rep_min} reps."
        return _result("maintain_weight", w,
                       rep_min, reason, measure, unit, inc, fail_streak)

    # ---- Máximo del rango alcanzado en todas las series
    if min_reps >= rep_max:
        if rir_low:
            if measure == "time":
                reason = f"Llegaste a {rep_max} s, pero el esfuerzo fue demasiado alto. Repite antes de avanzar."
            else:
                reason = (f"Llegaste a {rep_max} reps, pero alguna serie quedó por debajo de {rir_target} RIR. "
                          f"Mantén {kg if loaded else 'tu peso corporal'} hasta dejar {rir_target} RIR.")
            return _result("maintain_weight", w, rep_max, reason, measure, unit, inc)
        if inc > 0:
            new_w = round(w + inc, 2)
            if loaded:
                reason = (f"Llegaste a {rep_max}{unit_txt} en todas las series → +{fmt_num(inc)} kg. "
                          f"Vuelve a {rep_min}{unit_txt}.")
            else:
                reason = (f"Llegaste a {rep_max}{unit_txt} en todas las series → añade {fmt_num(inc)} kg de lastre. "
                          f"Vuelve a {rep_min}{unit_txt}.")
            return _result("increase_weight", new_w, rep_min, reason, measure, unit, inc)
        if measure == "time":
            reason = f"Llegaste a {rep_max} s en todas las series: añade una serie o una variante más difícil."
        else:
            reason = f"Llegaste a {rep_max} reps en todas las series: añade una serie, más pausa o una variante más difícil."
        return _result("maintain_weight", w, rep_max, reason, measure, unit, inc)

    # ---- Dentro del rango: sube reps / tiempo
    if measure == "time":
        target = min(min_reps + TIME_STEP_SECONDS, rep_max)
        reason = f"Intenta aguantar {target} s por serie (+{target - min_reps} s)."
        return _result("add_time", w, target, reason, measure, unit, inc)
    target = min(min_reps + 1, rep_max)
    where = f"con {kg}" if loaded else "con tu peso corporal"
    reason = f"Intenta 1 rep más por serie ({target} reps) {where}. Objetivo: {rep_max} reps."
    if rir_low:
        reason += f" Deja {rir_target} RIR."
    return _result("add_reps", w, target, reason, measure, unit, inc)
