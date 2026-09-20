"""Dieta determinista. Escala raciones al objetivo; no apila extras."""
from __future__ import annotations
from datetime import date, timedelta
from .diet_catalog import GOALS, recipe_by_id, recipes_for

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

def _macros_for(weight_kg, goal_id, day_kind):
    spec = GOALS[goal_id]
    kcal = int(round(weight_kg * spec["kcal_per_kg"][day_kind]))
    protein = int(round(weight_kg * spec["protein_g_per_kg"]))
    fat = int(round(weight_kg * spec["fat_g_per_kg"]))
    carbs = max(0, int(round((kcal - protein * 4 - fat * 9) / 4)))
    return {"kcal": kcal, "protein_g": protein, "carbs_g": carbs, "fat_g": fat, "day_kind": day_kind, "goal": goal_id}

def _as_meal(chosen):
    return {
        "recipe_id": chosen["id"], "name": chosen["name"], "slot": chosen["slot"],
        "minutes": chosen["minutes"], "kcal": chosen["kcal"],
        "protein": chosen["protein"], "carbs": chosen["carbs"], "fat": chosen["fat"],
        "ingredients": list(chosen["ingredients"]), "steps": list(chosen["steps"]),
    }

def pick_recipe(slot, day_index, used_ids):
    pool = recipes_for(slot)
    unused = [x for x in pool if x["id"] not in used_ids]
    choices = unused if unused else pool
    return _as_meal(choices[day_index % len(choices)])

def _scale_grams(text, factor):
    out = []
    num = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch.isdigit():
            num += ch
            i += 1
            continue
        if num:
            out.append(str(int(round(int(num) * factor))))
            num = ""
        out.append(ch)
        i += 1
    if num:
        out.append(str(int(round(int(num) * factor))))
    return "".join(out)

def scale_meals(meals, target_kcal):
    current = sum(m["kcal"] for m in meals) or 1
    factor = target_kcal / current
    factor = max(0.85, min(factor, 1.7))
    factor = round(factor, 2)
    scaled = []
    for m in meals:
        item = dict(m)
        item["kcal"] = int(round(m["kcal"] * factor))
        item["protein"] = int(round(m["protein"] * factor))
        item["carbs"] = int(round(m["carbs"] * factor))
        item["fat"] = int(round(m["fat"] * factor))
        item["ingredients"] = [_scale_grams(x, factor) for x in m["ingredients"]]
        if abs(factor - 1) >= 0.08:
            item["name"] = m["name"]  # misma receta, ración distinta
        scaled.append(item)
    return scaled, factor

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
        meals, factor = scale_meals(meals, targets["kcal"])
        planned = {
            "kcal": sum(m["kcal"] for m in meals),
            "protein": sum(m["protein"] for m in meals),
            "carbs": sum(m["carbs"] for m in meals),
            "fat": sum(m["fat"] for m in meals),
        }
        note = f"Objetivo {targets['kcal']} kcal. Raciones x{factor}."
        if info:
            note += f" Dia {info['routine_name']}."
        else:
            note += " Descanso."
        days.append({
            "date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()],
            "kind": kind, "routine_name": None if not info else info["routine_name"],
            "targets": targets, "planned": planned, "meals": meals, "note": note,
        })
    return {
        "week_start": week_start.isoformat(),
        "goal": GOALS[goal_id],
        "weight_kg": weight_kg,
        "rules": {
            "no_pork": True, "no_seafood": True,
            "portions": "mismas recetas, gramos subidos o bajados al objetivo",
        },
        "days": days,
    }

def shopping_list(week):
    tally = {}
    for day in week["days"]:
        for meal in day["meals"]:
            recipe = recipe_by_id(meal["recipe_id"])
            lines = meal.get("ingredients") or (recipe["ingredients"] if recipe else [])
            for line in lines:
                tally[line] = tally.get(line, 0) + 1
    return [{"item": k, "appearances": v} for k, v in sorted(tally.items())]
