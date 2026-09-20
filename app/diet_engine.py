"""Dieta determinista. Compra = receta original x factor del dia."""
from __future__ import annotations
import re
from datetime import date, timedelta
from .diet_catalog import GOALS, recipe_by_id, recipes_for

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

ALIASES = [
    (("pechuga de pollo", "pollo picado", "muslo", "pollo"), "pollo"),
    (("filete de pavo", "pavo picado", "pechuga de pavo", "pavo"), "pavo"),
    (("ternera",), "ternera"),
    (("yogur",), "yogur"),
    (("cottage",), "cottage"),
    (("queso fresco",), "queso fresco"),
    (("requeson", "requesón"), "requeson"),
    (("avena",), "avena"),
    (("arroz",), "arroz"),
    (("pan", "tostada"), "pan integral"),
    (("lentejas",), "lentejas"),
    (("garbanzos",), "garbanzos"),
    (("patata",), "patata"),
    (("quinoa",), "quinoa"),
    (("cuscus", "cuscús"), "cuscus"),
    (("tofu",), "tofu"),
    (("clara",), "claras"),
    (("huevo",), "huevos"),
    (("leche",), "leche"),
    (("platano", "plátano"), "platano"),
    (("manzana",), "manzana"),
    (("kiwi",), "kiwi"),
    (("brocoli", "brócoli"), "brocoli"),
    (("calabacin", "calabacín"), "calabacin"),
    (("pimiento",), "pimiento"),
    (("zanahoria",), "zanahoria"),
    (("espinaca",), "espinacas"),
    (("tomate",), "tomate"),
    (("cebolla",), "cebolla"),
    (("judias", "judías"), "judias verdes"),
    (("ensalada", "lechuga"), "ensalada"),
    (("aguacate",), "aguacate"),
    (("nuez", "nueces"), "nueces"),
    (("hummus",), "hummus"),
    (("proteina", "proteína"), "proteina en polvo"),
    (("aceite", "aove"), "aceite de oliva"),
    (("miel",), "miel"),
    (("canela",), "canela"),
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
    def repl(m):
        return str(int(round(float(m.group(1)) * factor))) + m.group(2)
    return re.sub(r"(\d+)(\s*g)\b", repl, text, flags=re.I)

def scale_meals(meals, target_kcal):
    current = sum(m["kcal"] for m in meals) or 1
    factor = max(0.9, min(target_kcal / current, 1.45))
    factor = round(factor, 2)
    scaled = []
    for m in meals:
        item = dict(m)
        for key in ("kcal", "protein", "carbs", "fat"):
            item[key] = int(round(m[key] * factor))
        item["ingredients"] = [_scale_grams(x, factor) for x in m["ingredients"]]
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
        note += f" Dia {info['routine_name']}." if info else " Descanso."
        days.append({
            "date": day.isoformat(), "weekday": WEEKDAYS[day.weekday()],
            "kind": kind, "routine_name": None if not info else info["routine_name"],
            "targets": targets, "planned": planned, "meals": meals,
            "portion_factor": factor, "note": note,
        })
    return {
        "week_start": week_start.isoformat(), "goal": GOALS[goal_id], "weight_kg": weight_kg,
        "rules": {"no_pork": True, "no_seafood": True},
        "days": days,
    }

def _norm(s: str) -> str:
    s = s.lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u")):
        s = s.replace(a, b)
    return s

def _canon(name: str) -> str:
    n = _norm(name)
    for keys, label in ALIASES:
        for k in keys:
            if k in n:
                return label
    return n.strip()

def _parse_catalog_line(line: str):
    low = _norm(line)
    grams = ml = count = 0.0
    m = re.search(r"(\d+[\.,]?\d*)\s*g\b", low)
    if m:
        grams = float(m.group(1).replace(",", "."))
    m = re.search(r"(\d+[\.,]?\d*)\s*ml\b", low)
    if m:
        ml = float(m.group(1).replace(",", "."))
    m = re.match(r"\s*(\d+)\s+(huevo|clara|rebanada|tostada|platano|manzana|kiwi|tortita)", low)
    if m:
        count = float(m.group(1))
    name = _canon(re.sub(r"\d+[\.,]?\d*\s*(g|ml|cdita)?", " ", low))
    name = re.sub(r"\s+", " ", name).strip(" ,+")
    return name or low, grams, ml, count

def _fmt(name, grams, ml, count):
    if grams >= 1000:
        qty = f"{grams/1000:.1f} kg"
    elif grams > 0:
        qty = f"{int(round(grams))} g"
    elif ml > 0:
        qty = f"{int(round(ml))} ml"
    elif count > 0:
        qty = str(int(round(count)))
    else:
        qty = "al gusto"
    return f"{name[:1].upper() + name[1:]} — {qty}"

def shopping_list(week):
    bag = {}
    for day in week["days"]:
        factor = float(day.get("portion_factor") or 1.0)
        factor = max(0.9, min(factor, 1.45))
        for meal in day["meals"]:
            rec = recipe_by_id(meal.get("recipe_id"))
            lines = rec["ingredients"] if rec else []
            for line in lines:
                name, grams, ml, count = _parse_catalog_line(line)
                cur = bag.setdefault(name, {"grams": 0.0, "ml": 0.0, "count": 0.0, "hits": 0})
                cur["grams"] += grams * factor
                cur["ml"] += ml * factor
                cur["count"] += count
                cur["hits"] += 1
    out = []
    for name, cur in sorted(bag.items(), key=lambda kv: (-kv[1]["grams"], kv[0])):
        out.append({
            "item": _fmt(name, cur["grams"], cur["ml"], cur["count"]),
            "appearances": cur["hits"],
            "grams": int(round(cur["grams"])),
        })
    return out
