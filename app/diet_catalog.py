"""Catalogo. Sin cerdo ni marisco. Recetas 5-25 min."""
from __future__ import annotations

FORBIDDEN = ("cerdo", "jamon", "chorizo", "bacon", "marisco", "gamba", "atun", "salmon", "pescado")

GOALS = {
    "lose_fat": {"id": "lose_fat", "name": "Perder grasa", "kcal_per_kg": {"train": 28, "rest": 26}, "protein_g_per_kg": 2.2, "fat_g_per_kg": 0.7, "summary": "Deficit controlado."},
    "recomp": {"id": "recomp", "name": "Recomposicion", "kcal_per_kg": {"train": 31, "rest": 29}, "protein_g_per_kg": 2.1, "fat_g_per_kg": 0.8, "summary": "Cerca de mantenimiento."},
    "maintain": {"id": "maintain", "name": "Mantenimiento", "kcal_per_kg": {"train": 33, "rest": 31}, "protein_g_per_kg": 1.8, "fat_g_per_kg": 0.8, "summary": "Estabilidad de peso."},
    "gain_muscle": {"id": "gain_muscle", "name": "Ganar musculo", "kcal_per_kg": {"train": 37, "rest": 34}, "protein_g_per_kg": 2.0, "fat_g_per_kg": 0.9, "summary": "Ligero superavit."},
    "performance": {"id": "performance", "name": "Rendimiento", "kcal_per_kg": {"train": 36, "rest": 32}, "protein_g_per_kg": 1.9, "fat_g_per_kg": 0.8, "summary": "Hidratos en A/B/C."},
}

def _r(i, n, slot, m, kcal, p, c, f, ing, steps):
    return {"id": i, "name": n, "slot": slot, "minutes": m, "tags": [], "kcal": kcal, "protein": p, "carbs": c, "fat": f, "ingredients": ing, "steps": steps}

RECIPES = [
    _r("b1", "Yogur griego con avena y fruta", "breakfast", 5, 420, 32, 48, 10, ["250 g yogur griego", "40 g avena", "1 platano"], ["Mezcla y sirve."]),
    _r("b2", "Tortilla de claras con pan integral", "breakfast", 10, 380, 34, 32, 12, ["4 claras + 1 huevo", "1 pan integral", "Espinacas"], ["Cuaja 4 min."]),
    _r("b3", "Tostada de pavo y huevo", "breakfast", 8, 430, 30, 36, 16, ["2 tostadas", "60 g pavo", "1 huevo", "aguacate 30 g"], ["Monta y listo."]),
    _r("b4", "Bowl de cottage, kiwi y nueces", "breakfast", 5, 340, 28, 28, 12, ["200 g cottage", "1 kiwi", "15 g nueces"], ["Mezcla."]),
    _r("b5", "Avena caliente con canela y claras", "breakfast", 8, 400, 30, 50, 8, ["50 g avena", "2 claras", "canela", "leche desnatada"], ["Micro 3 min, remueve claras 1 min."]),
    _r("b6", "Requeson con miel y tostada", "breakfast", 5, 390, 26, 40, 10, ["200 g requeson", "miel", "1 tostada integral"], ["Unta y sirve."]),
    _r("b7", "Huevos revueltos y tomate", "breakfast", 8, 360, 28, 12, 22, ["3 huevos", "tomate", "1 cdita aceite"], ["Revuelve 3 min."]),
    _r("l1", "Pollo plancha, arroz y brocoli", "lunch", 20, 620, 48, 62, 16, ["180 g pollo", "70 g arroz", "brocoli"], ["Plancha y arroz."]),
    _r("l2", "Pavo, patata al micro y ensalada", "lunch", 18, 580, 46, 55, 14, ["180 g pavo", "250 g patata", "ensalada"], ["Micro + plancha."]),
    _r("l3", "Lentejas rapidas con verdura", "lunch", 15, 520, 28, 68, 12, ["250 g lentejas bote", "zanahoria", "cebolla"], ["Sofrie 10 min."]),
    _r("l4", "Wrap de pollo y verduras", "lunch", 12, 540, 40, 48, 18, ["tortita", "150 g pollo", "verdura", "yogur"], ["Rellena."]),
    _r("l5", "Ternera magra con cuscus y calabacin", "lunch", 20, 650, 46, 58, 22, ["160 g ternera", "60 g cuscus", "calabacin"], ["Saltea 7 min."]),
    _r("l6", "Garbanzos salteados con huevo", "lunch", 12, 500, 26, 52, 18, ["200 g garbanzos", "2 huevos", "espinacas"], ["Saltea y huevo."]),
    _r("l7", "Arroz con pavo y pimiento", "lunch", 18, 600, 42, 64, 14, ["70 g arroz", "160 g pavo", "pimiento"], ["Arroz + salteado."]),
    _r("l8", "Quinoa, pollo y calabacin", "lunch", 20, 580, 44, 50, 16, ["60 g quinoa", "160 g pollo", "calabacin"], ["Cocina quinoa 12 min."]),
    _r("s1", "Yogur proteico y fruta", "snack", 3, 220, 20, 24, 4, ["200 g yogur", "fruta"], ["Abre y come."]),
    _r("s2", "Pavo, queso fresco y manzana", "snack", 4, 250, 24, 18, 8, ["80 g pavo", "80 g queso fresco", "manzana"], ["Empareja."]),
    _r("s3", "Hummus y zanahoria", "snack", 5, 230, 8, 22, 12, ["80 g hummus", "2 zanahorias"], ["Moja."]),
    _r("s4", "Batido de leche y platano", "snack", 3, 210, 12, 32, 4, ["250 ml leche desnatada", "1 platano"], ["Tritura."]),
    _r("s5", "Copos de maiz y yogur", "snack", 3, 240, 16, 36, 4, ["30 g copos", "150 g yogur"], ["Mezcla."]),
    _r("s6", "Huevo duro y pepino", "snack", 6, 180, 14, 4, 12, ["2 huevos", "pepino"], ["Cuece 8 min."]),
    _r("p1", "Batido peri-entreno", "peri", 4, 280, 28, 36, 3, ["30 g proteina", "platano", "agua"], ["Tritura."]),
    _r("p2", "Tostada de miel y canela", "peri", 5, 240, 8, 42, 4, ["pan", "miel", "canela", "queso fresco"], ["Tuesta."]),
    _r("p3", "Platano y yogur liquido", "peri", 2, 200, 10, 36, 2, ["1 platano", "200 ml yogur liquido"], ["Fuera de casa."]),
    _r("d1", "Salteado de pollo y verduras", "dinner", 18, 480, 42, 22, 22, ["180 g pollo", "pimiento", "calabacin"], ["Saltea 12 min."]),
    _r("d2", "Hamburguesa de pavo con calabacin", "dinner", 16, 430, 40, 12, 22, ["180 g pavo picado", "calabacin"], ["Plancha."]),
    _r("d3", "Revuelto de huevo, espinacas y queso", "dinner", 10, 390, 30, 8, 26, ["3 huevos", "espinacas", "queso fresco"], ["Revuelve."]),
    _r("d4", "Tofu salteado con arroz", "dinner", 15, 510, 28, 55, 18, ["150 g tofu", "60 g arroz", "verdura"], ["Saltea tofu."]),
    _r("d5", "Muslo de pollo al horno y ensalada", "dinner", 25, 520, 44, 16, 28, ["muslo sin piel", "ensalada", "patata micro"], ["Horno 20 min."]),
    _r("d6", "Pavo plancha con judias verdes", "dinner", 16, 410, 40, 16, 16, ["180 g pavo", "judias verdes"], ["Plancha + vapor."]),
    _r("d7", "Calabacin relleno de pollo", "dinner", 20, 390, 36, 14, 18, ["1 calabacin", "150 g pollo picado", "tomate"], ["Horno o sarten 15 min."]),
    _r("d8", "Sopa de lentejas y huevo poché", "dinner", 15, 420, 26, 48, 10, ["lentejas bote", "caldo", "1 huevo"], ["Hierve 8 min, huevo encima."]),
]

def recipe_by_id(recipe_id: str):
    for item in RECIPES:
        if item["id"] == recipe_id:
            return item
    return None

def recipes_for(slot: str, goal: str = "", day_kind: str = ""):
    return [x for x in RECIPES if x["slot"] == slot]
