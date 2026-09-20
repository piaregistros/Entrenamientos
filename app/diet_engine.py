"""Cálculos deterministas de dieta. No inventa alimentos ni macros."""
from __future__ import annotations
from datetime import date, timedelta
from .diet_catalog import GOALS, RECIPES, recipe_by_id, recipes_for

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def _macros_for(weight_kg: float, goal_id: str, day_kind: str) -> dict:
    spec = GOALS[goal_id]
    kcal = int(round(weight_kg * spec["kcal_per_kg"][day_kind]))
    protein = int(round(weight_kg * spec["protein_g_per_kg"]))
    fat = int(round(weight_kg * spec["fat_g_per_kg"]))
    carbs = max(0, int(round((kcal - protein * 4 - fat * 9) / 4)))
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "day_kind": day_kind, "goal": goal_id}

def _as_meal(chosen: dict) -> dict:
    return {
        "recipe_id": chosen["id"], "name": chosen["name"], "slot": chosen["slot"],
        "minutes": chosen["minutes"], "kcal": chosen["kcal"], "protein": chosen["protein"],
        "carbs": chosen["carbs"], "fat": chosen["fat"],
        "ingredients": list(chosen["ingredients"]), "steps": list(chosen["steps"]),
    }

def pick_recipe(slot, goal, day_kind, seed, used_ids, used_names_slot):
    tagged = recipes_for(slot, goal, day_kind)
    pool = tagged or [x for x in RECIPES if x["slot"] == slot]
    unused = [x for x in pool if x["id"] not in used_ids and x["name"] not in used_names_slot]
    if not unused:
        unused = [x for x in pool if x["id"] not in used_ids]
    choices = unused or pool
    return _as_meal(choices[seed % len(choices)])

def map_training_days(routines, week_start):
    active = sorted([r for r in routines if r.get("is_active", 1)], key=lambda r: r.get("day_order") or 0)
    mapping = {}
    for idx, weekday_offset in enumerate([0, 2, 4]):
        day = week_start + timedelta(days=weekday_offset)
        routine = active[idx] if idx < len(active) else None
        mapping[day.isoformat()] = {
            "kind": "train",
            "routine_name": (routine or {}).get("name") or ["A", "B", "C"][idx],
            "day_order": (routine or {}).get("day_order") or idx + 1,
        }
    return mapping

def build_week(*, week_start, goal_id, weight_kg, routines, meals_per_day=4):
    if goal_id not in GOALS:
        goal_id = "recomp"
    weight_kg = max(40.0, min(float(weight_kg), 180.0))
    meals_per_day = 4 if meals_per_day not in (3, 4, 5) else meals_per_day
    training = map_training_days(routines, week_start)
    used_ids = set()
    used_by_slot = {}
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        info = training.get(day.isoformat())
        kind = "train" if info else "rest"
        targets = _macros_for(weight_kg, goal_id, kind)
        seed = offset * 31 + day.weekday() * 7
        slots = ["breakfast", "lunch", "dinner"]
        if meals_per_day >= 4:
            slots.insert(2, "snack")
        if meals_per_day >= 5 and kind == "train":
            slots.insert(1, "peri")
        meals = []
        for i, slot in enumerate(slots):
            recipe = pick_recipe(slot, goal_id, kind, seed + i * 11 + offset, used_ids, used_by_slot.setdefault(slot, set()))
            used_ids.add(recipe["recipe_id"])
            used_by_slot[slot].add(recipe["name"])
            meals.append(recipe)
        planned = {"kcal": sum(m["kcal"] for m in meals), "protein": sum(m["protein"] for m in meals), "carbs": sum(m["carbs"] for m in meals), "fat": sum(m["fat"] for m in meals)}
        days.append({
            "date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()], "kind": kind,
            "routine_name": None if not info else info["routine_name"],
            "targets": targets, "planned": planned, "meals": meals,
            "note": (f"Día de {info['routine_name']}: más hidrato alrededor del entreno." if info else "Descanso: ración más ligera. Sin cerdo ni marisco."),
        })
    return {"week_start": week_start.isoformat(), "goal": GOALS[goal_id], "weight_kg": weight_kg,
            "rules": {"no_pork": True, "no_seafood": True, "easy_recipes": True, "training_split": "A/B/C · 3 días",
                       "variety": "no repetir receta en la misma semana si hay alternativa"}, "days": days}

def shopping_list(week):
    tally = {}
    for day in week["days"]:
        for meal in day["meals"]:
            recipe = recipe_by_id(meal["recipe_id"])
            if not recipe:
                continue
            for line in recipe["ingredients"]:
                tally[line] = tally.get(line, 0) + 1
    return [{"item": k, "appearances": v} for k, v in sorted(tally.items())]
