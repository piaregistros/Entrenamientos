"""Catalogo determinista. Sin cerdo ni marisco. Recetas 5-25 min."""
from __future__ import annotations

FORBIDDEN = ("cerdo", "jamon", "jamón", "chorizo", "bacon", "marisco", "gamba", "atun", "atún", "salmon", "pescado")

GOALS = {
    "lose_fat": {"id": "lose_fat", "name": "Perder grasa", "kcal_per_kg": {"train": 28, "rest": 26}, "protein_g_per_kg": 2.2, "fat_g_per_kg": 0.7, "summary": "Deficit controlado. Mas proteina, raciones mas ligeras en descanso."},
    "recomp": {"id": "recomp", "name": "Recomposicion", "kcal_per_kg": {"train": 31, "rest": 29}, "protein_g_per_kg": 2.1, "fat_g_per_kg": 0.8, "summary": "Cerca de mantenimiento. Prioriza proteina en A/B/C."},
    "maintain": {"id": "maintain", "name": "Mantenimiento", "kcal_per_kg": {"train": 33, "rest": 31}, "protein_g_per_kg": 1.8, "fat_g_per_kg": 0.8, "summary": "Estabilidad de peso con 3 dias A/B/C."},
    "gain_muscle": {"id": "gain_muscle", "name": "Ganar musculo", "kcal_per_kg": {"train": 37, "rest": 34}, "protein_g_per_kg": 2.0, "fat_g_per_kg": 0.9, "summary": "Ligero superavit. Mas carbohidrato los dias de rutina."},
    "performance": {"id": "performance", "name": "Rendimiento", "kcal_per_kg": {"train": 36, "rest": 32}, "protein_g_per_kg": 1.9, "fat_g_per_kg": 0.8, "summary": "Hidratos alrededor de A/B/C. Descanso mas ligero."},
}

def _r(id, name, slot, minutes, tags, kcal, protein, carbs, fat, ingredients, steps):
    return {"id": id, "name": name, "slot": slot, "minutes": minutes, "tags": tags, "kcal": kcal, "protein": protein, "carbs": carbs, "fat": fat, "ingredients": ingredients, "steps": steps}

ALL = ["train", "rest", "lose_fat", "recomp", "maintain", "gain_muscle", "performance"]

RECIPES = [
    _r("r-yogurt-avena", "Yogur griego con avena y fruta", "breakfast", 5, ALL, 420, 32, 48, 10, ["250 g yogur griego natural", "40 g copos de avena", "1 platano o 150 g frutos rojos"], ["Mezcla yogur y avena.", "Anade la fruta."]),
    _r("r-tortilla-clara", "Tortilla de claras con pan integral", "breakfast", 10, ALL, 380, 34, 32, 12, ["4 claras + 1 huevo entero", "1 rebanada pan integral", "Espinacas o tomate"], ["Cuaja 3-4 min.", "Sirve con el pan."]),
    _r("r-tostada-pavo-huevo", "Tostada de pavo y huevo", "breakfast", 8, ["train", "rest", "recomp", "maintain", "gain_muscle", "performance"], 430, 30, 36, 16, ["2 rebanadas pan integral", "60 g pechuga de pavo", "1 huevo", "Aguacate 30 g"], ["Tuesta el pan.", "Monta pavo, huevo y aguacate."]),
    _r("r-bowl-cottage", "Bowl de cottage, kiwi y nueces", "breakfast", 5, ["rest", "lose_fat", "recomp", "maintain"], 340, 28, 28, 12, ["200 g queso cottage", "1 kiwi o manzana", "15 g nueces"], ["Corta y mezcla."]),
    _r("r-pollo-arroz-brocoli", "Pollo plancha, arroz y brocoli", "lunch", 20, ALL, 620, 48, 62, 16, ["180 g pechuga de pollo", "70 g arroz crudo", "150 g brocoli", "1 cdita aceite oliva"], ["Cocina el arroz.", "Plancha el pollo 4 min/lado.", "Saltea el brocoli."]),
    _r("r-pavo-patata-ensalada", "Pavo, patata al micro y ensalada", "lunch", 18, ALL, 580, 46, 55, 14, ["180 g filete de pavo", "250 g patata", "Ensalada verde + tomate"], ["Patata al micro 8 min.", "Pavo a la plancha."]),
    _r("r-lentejas-rapidas", "Lentejas rapidas con verdura", "lunch", 15, ["rest", "lose_fat", "recomp", "maintain"], 520, 28, 68, 12, ["250 g lentejas cocidas", "1 zanahoria", "1/2 cebolla"], ["Sofrie 5 min.", "Anade lentejas 6 min."]),
    _r("r-wrap-pollo", "Wrap de pollo y verduras", "lunch", 12, ["train", "rest", "recomp", "maintain", "gain_muscle", "performance"], 540, 40, 48, 18, ["1 tortita integral", "150 g pollo", "Lechuga, tomate, yogur"], ["Rellena y cierra."]),
    _r("r-ternera-cous", "Ternera magra con cuscus y calabacin", "lunch", 20, ["train", "gain_muscle", "performance", "maintain"], 650, 46, 58, 22, ["160 g ternera magra", "60 g cuscus", "1 calabacin"], ["Cuscus 5 min.", "Saltea ternera 7 min."]),
    _r("r-garbanzos-huevo", "Garbanzos salteados con huevo", "lunch", 12, ["rest", "lose_fat", "recomp", "maintain"], 500, 26, 52, 18, ["200 g garbanzos cocidos", "2 huevos", "Espinacas"], ["Saltea y corona con huevo."]),
    _r("r-snack-yogur", "Yogur proteico y fruta", "snack", 3, ALL, 220, 20, 24, 4, ["200 g yogur griego", "1 pieza de fruta"], ["Abre y come."]),
    _r("r-snack-fiambre", "Pavo, queso fresco y manzana", "snack", 4, ["train", "rest", "recomp", "maintain", "gain_muscle", "performance"], 250, 24, 18, 8, ["80 g pavo", "80 g queso fresco", "1 manzana"], ["Empareja. Sin cerdo."]),
    _r("r-snack-hummus", "Hummus y zanahoria", "snack", 5, ["rest", "lose_fat", "recomp", "maintain"], 230, 8, 22, 12, ["80 g hummus", "2 zanahorias"], ["Corta y moja."]),
    _r("r-batido-peri", "Batido peri-entreno", "peri", 4, ["train", "gain_muscle", "performance", "recomp", "maintain"], 280, 28, 36, 3, ["30 g proteina", "1 platano", "250 ml agua o leche desnatada"], ["Tritura 20 s. Antes o despues de A/B/C."]),
    _r("r-toast-miel", "Tostada de miel y canela (pre A/B/C)", "peri", 5, ["train", "performance", "gain_muscle"], 240, 8, 42, 4, ["1 rebanada pan integral", "Miel", "Canela", "Queso fresco 40 g"], ["Tuesta y unta. 45-60 min antes."]),
    _r("r-pollo-verduras", "Salteado de pollo y verduras", "dinner", 18, ALL, 480, 42, 22, 22, ["180 g pollo", "Pimiento, calabacin, cebolla", "1 cdita aceite"], ["Saltea verdura 6 min y pollo 6 min."]),
    _r("r-pavo-calabacin", "Hamburguesa de pavo con calabacin", "dinner", 16, ["train", "rest", "lose_fat", "recomp", "maintain"], 430, 40, 12, 22, ["180 g pavo picado", "1 calabacin"], ["Burger 4 min/lado."]),
    _r("r-huevos-revueltos", "Revuelto de huevo, espinacas y queso", "dinner", 10, ["rest", "lose_fat", "recomp", "maintain"], 390, 30, 8, 26, ["3 huevos", "Espinacas", "30 g queso fresco"], ["Revuelve 3 min."]),
    _r("r-tofu-arroz", "Tofu salteado con arroz", "dinner", 15, ["rest", "recomp", "maintain", "lose_fat"], 510, 28, 55, 18, ["150 g tofu firme", "60 g arroz crudo", "Verdura"], ["Saltea tofu. Arroz aparte."]),
    _r("r-pollo-horno-rapido", "Muslo de pollo al horno y ensalada", "dinner", 25, ["train", "gain_muscle", "performance", "maintain"], 520, 44, 16, 28, ["1 muslo sin piel", "Ensalada", "Patata al micro"], ["Horno 200C 20 min o airfryer 16."]),
]

def recipe_by_id(recipe_id: str):
    for item in RECIPES:
        if item["id"] == recipe_id:
            return item
    return None

def recipes_for(slot: str, goal: str, day_kind: str):
    out = [x for x in RECIPES if x["slot"] == slot and goal in x["tags"] and day_kind in x["tags"]]
    if not out:
        out = [x for x in RECIPES if x["slot"] == slot and goal in x["tags"]]
    if not out:
        out = [x for x in RECIPES if x["slot"] == slot]
    return out
