"""Series de aproximación sugeridas a partir del peso de trabajo (Fase 11).

Reglas:
  - Compuestos con carga: 40 % × 8, 60 % × 5, 80 % × 3, redondeado al paso del
    equipo. En barra, nunca por debajo de 20 kg (barra olímpica).
  - Aislamientos, o cargas ligeras (< 40 kg): menos series (50 % × 8 y 70 % × 5).
  - Muy ligeros (< 10 kg), isométricos (tiempo) y peso corporal: ninguna.
  - Se omiten series cuyo peso redondeado queda a < 10 % del de trabajo o
    coincide con otra serie ya propuesta.

Estas series, si se registran, deben ir con is_warmup=1; progression.py ya las ignora.
"""
from __future__ import annotations

from .progression import (
    equipment_class,
    infer_measure_type,
    resolve_increment,
    round_to_step,
)

BAR_KG = 20.0
LIGHT_KG = 10.0
MODERATE_KG = 40.0

_ISOLATION_TYPES = frozenset({"aislamiento", "core"})
_COMPOUND_TYPES = frozenset({"compuesto", "unilateral"})
_ISOLATION_NAME_BITS = (
    "curl",
    "extension de triceps",
    "extension de tríceps",
    "elevacion lateral",
    "elevaciones laterales",
    "apertura",
    "pajaro",
    "pájaro",
    "face pull",
    "patada",
    "encogimiento",
    "gemelo",
    "elevacion de gemelo",
    "crunch",
    "abdominal",
)


def _norm(value) -> str:
    import unicodedata
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def is_isolation(ex: dict) -> bool:
    typ = _norm(ex.get("exercise_type"))
    if typ in _ISOLATION_TYPES:
        return True
    if typ in _COMPOUND_TYPES:
        return False
    name = _norm(ex.get("name"))
    if any(bit in name for bit in _ISOLATION_NAME_BITS):
        return True
    cat = _norm(ex.get("category"))
    if cat in ("brazos", "core"):
        return True
    return False


def suggest_warmup(ex: dict, working_weight) -> list[dict]:
    """Devuelve una lista de series de aproximación (puede estar vacía).

    Cada elemento: percent, weight_kg, reps, label.
    """
    measure = ex.get("measure_type") if ex.get("measure_type") in ("reps", "time", "bodyweight") else None
    measure = measure or infer_measure_type(ex.get("name"), ex.get("equipment"))
    if measure in ("time", "bodyweight"):
        return []
    try:
        weight = float(working_weight or 0)
    except (TypeError, ValueError):
        return []
    if weight < LIGHT_KG:
        return []

    inc = resolve_increment(ex)
    step = inc if inc and inc > 0 else 2.5
    cls = equipment_class(ex.get("equipment"))
    isolation = is_isolation(ex)

    if isolation or weight < MODERATE_KG:
        plan = ((50, 8), (70, 5))
    else:
        plan = ((40, 8), (60, 5), (80, 3))

    out: list[dict] = []
    for percent, reps in plan:
        raw = weight * (percent / 100.0)
        if cls == "barbell":
            raw = max(raw, BAR_KG)
        rounded = round_to_step(raw, step)
        if cls == "barbell" and rounded < BAR_KG:
            rounded = BAR_KG
        if rounded <= 0:
            continue
        if rounded >= weight * 0.9 or rounded >= weight:
            continue
        if out and abs(out[-1]["weight_kg"] - rounded) < 1e-6:
            continue
        if cls == "barbell" and abs(rounded - BAR_KG) < 1e-6:
            label = f"Barra vacía × {reps}"
        else:
            label = f"{percent} % × {reps}"
        out.append({
            "percent": percent,
            "weight_kg": rounded,
            "reps": reps,
            "label": label,
        })
    return out
