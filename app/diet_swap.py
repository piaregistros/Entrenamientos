"""Cambia un plato del plan por otra receta del mismo hueco."""
from __future__ import annotations
from .diet_catalog import recipes_for
from .diet_engine import _as_meal, _scale_grams


def swap_meal(week: dict, day_date: str, slot: str) -> dict:
    day = next((d for d in week["days"] if d["date"] == day_date), None)
    if not day:
        raise ValueError("Día no encontrado")
    meals = day["meals"]
    idx = next((i for i, m in enumerate(meals) if m["slot"] == slot), None)
    if idx is None:
        raise ValueError("Toma no encontrada")
    current = meals[idx]["recipe_id"]
    used = {m["recipe_id"] for d in week["days"] for m in d["meals"]}
    pool = recipes_for(slot)
    unused = [x for x in pool if x["id"] not in used]
    others = unused or [x for x in pool if x["id"] != current]
    if not others:
        raise ValueError("No hay alternativa")
    ids = [x["id"] for x in others]
    nxt = others[0]
    if current in ids:
        nxt = others[(ids.index(current) + 1) % len(others)]
    elif current:
        # start after current in full pool order
        full = [x["id"] for x in pool]
        if current in full:
            for cand in pool[full.index(current) + 1 :] + pool[: full.index(current)]:
                if cand["id"] != current:
                    nxt = cand
                    if unused:
                        nxt = unused[0]
                    break
    meal = _as_meal(nxt)
    factor = float(day.get("portion_factor") or 1.0)
    for key in ("kcal", "protein", "carbs", "fat"):
        meal[key] = int(round(meal[key] * factor))
    meal["ingredients"] = [_scale_grams(x, factor) for x in meal["ingredients"]]
    meals[idx] = meal
    day["planned"] = {
        "kcal": sum(m["kcal"] for m in meals),
        "protein": sum(m["protein"] for m in meals),
        "carbs": sum(m["carbs"] for m in meals),
        "fat": sum(m["fat"] for m in meals),
    }
    return week
