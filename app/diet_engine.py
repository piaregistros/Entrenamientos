"""Dieta determinista. Objetivos por kg; raciones + extras para acercarse al objetivo."""
from __future__ import annotations
from datetime import date, timedelta
from .diet_catalog import GOALS, recipe_by_id, recipes_for

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Extras simples (sin cerdo ni marisco) para llegar al objetivo de kcal.
EXTRAS = [
    {"id": "x-arroz", "name": "Extra: 50 g arroz (crudo)", "kcal": 180, "protein": 4, "carbs": 40, "fat": 0, "ingredients": ["50 g arroz"], "steps": ["Cocina junto a la comida o cena."]},
    {"id": "x-yogur", "name": "Extra: yogur griego 170 g", "kcal": 160, "protein": 17, "carbs": 8, "fat": 6, "ingredients": ["170 g yogur griego"], "steps": ["Como snack extra."]},
    {"id": "x-pan", "name": "Extra: 1 rebanada pan integral", "kcal": 80, "protein": 3, "carbs": 15, "fat": 1, "ingredients": ["1 rebanada pan integral"], "steps": ["Con la comida."]},
    {"id": "x-platano", "name": "Extra: 1 platano", "kcal": 100, "protein": 1, "carbs": 24, "fat": 0, "ingredients": ["1 platano"], "steps": ["Peri o merienda."]},
    {"id": "x-aceite", "name": "Extra: 1 cdita aceite de oliva", "kcal": 40, "protein": 0, "carbs": 0, "fat": 5, "ingredients": ["1 cdita AOVE"], "steps": ["En verdura o ensalada."]},
    {"id": "x-cottage", "name": "Extra: cottage 150 g", "kcal": 130, "protein": 16, "carbs": 6, "fat": 4, "ingredients": ["150 g cottage"], "steps": ["Snack proteico."]},
]

def _macros_for(weight_kg, goal_id, day_kind):
    spec = GOALS[goal_id]
    kcal = int(round(weight_kg * spec["kcal_per_kg"][day_kind]))
    protein = int(round(weight_kg * spec["protein_g_per_kg"]))
    fat = int(round(weight_kg * spec["fat_g_per_kg"]))
    carbs = max(0, int(round((kcal - protein * 4 - fat * 9) / 4)))
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "day_kind": day_kind, "goal": goal_id}

def _as_meal(chosen):
    return {
        "recipe_id": chosen.get("id") or chosen.get("recipe_id"),
        "name": chosen["name"], "slot": chosen.get("slot", "extra"),
        "minutes": chosen.get("minutes", 1),
        "kcal": chosen["kcal"], "protein": chosen["protein"],
        "carbs": chosen["carbs"], "fat": chosen["fat"],
        "ingredients": list(chosen["ingredients"]), "steps": list(chosen["steps"]),
    }

def pick_recipe(slot, day_index, used_ids):
    pool = recipes_for(slot)
    unused = [x for x in pool if x["id"] not in used_ids]
    choices = unused if unused else pool
    return _as_meal(choices[day_index % len(choices)])

def top_up(meals, target_kcal, day_index):
    planned = sum(m["kcal"] for m in meals)
    i = 0
    while planned + 60 < target_kcal and i < 8:
        extra = dict(EXTRAS[(day_index + i) % len(EXTRAS)])
        extra["slot"] = "extra"
        meals.append(_as_meal(extra))
        planned += extra["kcal"]
        i += 1
    return meals

def map_training_days(routines, week_start):
    active = sorted([r for r in routines if r.get("is_active", 1)], key=lambda r: r.get("day_order") or 0)
    mapping = {}
    for idx, off in enumerate([0, 2, 4]):
        day = week_start + timedelta(days=off)
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
    days = []
    for offset in range(7):
        day = week_start + timedelta(days=offset)
        info = training.get(day.isoformat())
        kind = "train" if info else "rest"
        targets = _macros_for(weight_kg, goal_id, kind)
        slots = ["breakfast", "lunch", "dinner"]
        if meals_per_day >= 4:
            slots.insert(2, "snack")
        if meals_per_day >= 5 and kind == "train":
            slots.insert(1, "peri")
        meals = []
        for slot in slots:
            recipe = pick_recipe(slot, offset, used_ids)
            used_ids.add(recipe["recipe_id"])
            meals.append(recipe)
        meals = top_up(meals, targets["kcal"], offset)
        planned = {
            "kcal": sum(m["kcal"] for m in meals),
            "protein": sum(m["protein"] for m in meals),
            "carbs": sum(m["carbs"] for m in meals),
            "fat": sum(m["fat"] for m in meals),
        }
        days.append({
            "date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()],
            "kind": kind, "routine_name": None if not info else info["routine_name"],
            "targets": targets, "planned": planned, "meals": meals,
            "note": (
                f"Objetivo {targets['kcal']} kcal (basal no es el objetivo). Dia {info['routine_name']}."
                if info else
                f"Objetivo {targets['kcal']} kcal. Descanso."
            ),
        })
    return {
        "week_start": week_start.isoformat(),
        "goal": GOALS[goal_id],
        "weight_kg": weight_kg,
        "rules": {
            "no_pork": True, "no_seafood": True,
            "bmr_is_not_target": True,
            "gain_muscle": "TDEE estimado por kg + superavit; extras si el plato se queda corto",
        },
        "days": days,
    }

def shopping_list(week):
    tally = {}
    for day in week["days"]:
        for meal in day["meals"]:
            recipe = recipe_by_id(meal["recipe_id"])
            lines = recipe["ingredients"] if recipe else meal.get("ingredients") or []
            for line in lines:
                tally[line] = tally.get(line, 0) + 1
    return [{"item": k, "appearances": v} for k, v in sorted(tally.items())]
