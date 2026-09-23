"""Catalogo. Sin cerdo ni marisco. Pescado kosher (aletas y escamas). Recetas 5-25 min."""
from __future__ import annotations

FORBIDDEN = ("cerdo", "jamon", "jamón", "chorizo", "bacon", "marisco", "gamba", "langostino", "mejillón", "calamar", "pulpo")

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
    _r("b8", "Tostada de atun y tomate", "breakfast", 6, 380, 28, 30, 12, ["2 tostadas", "80 g atun al natural", "tomate"], ["Escurre el atun y monta."]),
    _r("b9", "Skyr con frutos rojos y avena", "breakfast", 4, 360, 30, 40, 6, ["200 g skyr", "80 g frutos rojos", "30 g avena"], ["Mezcla frio."]),
    _r("b10", "Tortita de avena al sarten", "breakfast", 12, 410, 26, 48, 10, ["40 g avena", "1 huevo", "1 clara", "platano"], ["Tritura y sarten 2 min/lado."]),
    _r("b11", "Tostada de ricotta y miel", "breakfast", 5, 370, 22, 38, 12, ["2 tostadas", "80 g ricotta", "miel"], ["Unta."]),
    _r("b12", "Wrap de pavo y huevo duro", "breakfast", 7, 400, 32, 28, 14, ["1 tortita", "60 g pavo", "1 huevo duro", "tomate"], ["Enrolla."]),
    _r("l1", "Pollo plancha, arroz y brocoli", "lunch", 20, 620, 48, 62, 16, ["180 g pollo", "70 g arroz", "brocoli"], ["Plancha y arroz."]),
    _r("l2", "Pavo, patata al micro y ensalada", "lunch", 18, 580, 46, 55, 14, ["180 g pavo", "250 g patata", "ensalada"], ["Micro + plancha."]),
    _r("l3", "Lentejas rapidas con verdura", "lunch", 15, 520, 28, 68, 12, ["250 g lentejas bote", "zanahoria", "cebolla"], ["Sofrie 10 min."]),
    _r("l4", "Wrap de pollo y verduras", "lunch", 12, 540, 40, 48, 18, ["tortita", "150 g pollo", "verdura", "yogur"], ["Rellena."]),
    _r("l5", "Ternera magra con cuscus y calabacin", "lunch", 20, 650, 46, 58, 22, ["160 g ternera", "60 g cuscus", "calabacin"], ["Saltea 7 min."]),
    _r("l6", "Garbanzos salteados con huevo", "lunch", 12, 500, 26, 52, 18, ["200 g garbanzos", "2 huevos", "espinacas"], ["Saltea y huevo."]),
    _r("l7", "Arroz con pavo y pimiento", "lunch", 18, 600, 42, 64, 14, ["70 g arroz", "160 g pavo", "pimiento"], ["Arroz + salteado."]),
    _r("l8", "Quinoa, pollo y calabacin", "lunch", 20, 580, 44, 50, 16, ["60 g quinoa", "160 g pollo", "calabacin"], ["Cocina quinoa 12 min."]),
    _r("l9", "Atun, arroz y ensalada", "lunch", 15, 560, 42, 58, 12, ["120 g atun al natural", "70 g arroz", "ensalada"], ["Arroz, escurre el atun, mezcla."]),
    _r("l10", "Salmon plancha con patata", "lunch", 20, 620, 40, 45, 24, ["160 g salmon", "250 g patata", "limon"], ["Plancha 4 min/lado. Patata al micro."]),
    _r("l11", "Merluza al micro con verdura", "lunch", 12, 480, 38, 28, 14, ["180 g merluza", "calabacin", "pimiento"], ["Micro tapado 6-8 min."]),
    _r("l12", "Pasta integral con atun y tomate", "lunch", 15, 590, 38, 70, 12, ["80 g pasta integral", "100 g atun", "tomate triturado"], ["Hierve pasta 10 min, mezcla."]),
    _r("l13", "Batata al micro con pollo", "lunch", 18, 600, 44, 58, 14, ["250 g batata", "160 g pollo", "yogur"], ["Batata micro 8 min. Pollo plancha."]),
    _r("l14", "Trucha plancha con arroz", "lunch", 18, 580, 42, 52, 16, ["180 g trucha", "70 g arroz", "limon"], ["Plancha 4 min/lado."]),
    _r("l15", "Bowl de alubias, arroz y huevo", "lunch", 12, 540, 28, 64, 14, ["200 g alubias bote", "60 g arroz", "1 huevo"], ["Calienta y monta."]),
    _r("l16", "Noodles de arroz con verdura y huevo", "lunch", 14, 520, 22, 68, 12, ["70 g noodles arroz", "verdura bolsa", "2 huevos"], ["Hierve 4 min, saltea."]),
    _r("s1", "Yogur proteico y fruta", "snack", 3, 220, 20, 24, 4, ["200 g yogur", "fruta"], ["Abre y come."]),
    _r("s2", "Pavo, queso fresco y manzana", "snack", 4, 250, 24, 18, 8, ["80 g pavo", "80 g queso fresco", "manzana"], ["Empareja."]),
    _r("s3", "Hummus y zanahoria", "snack", 5, 230, 8, 22, 12, ["80 g hummus", "2 zanahorias"], ["Moja."]),
    _r("s4", "Batido de leche y platano", "snack", 3, 210, 12, 32, 4, ["250 ml leche desnatada", "1 platano"], ["Tritura."]),
    _r("s5", "Copos de maiz y yogur", "snack", 3, 240, 16, 36, 4, ["30 g copos", "150 g yogur"], ["Mezcla."]),
    _r("s6", "Huevo duro y pepino", "snack", 6, 180, 14, 4, 12, ["2 huevos", "pepino"], ["Cuece 8 min."]),
    _r("s7", "Atun de lata y tostada", "snack", 4, 240, 26, 18, 8, ["80 g atun al natural", "1 tostada integral"], ["Escurre y unta."]),
    _r("s8", "Sardinas al natural y pepino", "snack", 3, 220, 22, 4, 12, ["80 g sardinas al natural", "pepino"], ["Escurre. Kosher."]),
    _r("s9", "Edamame al vapor", "snack", 6, 200, 18, 14, 8, ["150 g edamame congelado", "sal"], ["Micro 4 min."]),
    _r("s10", "Tortitas de arroz con pavo", "snack", 3, 210, 18, 20, 6, ["2 tortitas arroz", "60 g pavo"], ["Monta."]),
    _r("s11", "Skyr y arandanos", "snack", 2, 180, 20, 16, 2, ["150 g skyr", "50 g arandanos"], ["Mezcla."]),
    _r("s12", "Queso fresco y pera", "snack", 3, 200, 16, 16, 6, ["100 g queso fresco", "1 pera"], ["Corta."]),
    _r("p1", "Batido peri-entreno", "peri", 4, 280, 28, 36, 3, ["30 g proteina", "platano", "agua"], ["Tritura."]),
    _r("p2", "Tostada de miel y canela", "peri", 5, 240, 8, 42, 4, ["pan", "miel", "canela", "queso fresco"], ["Tuesta."]),
    _r("p3", "Platano y yogur liquido", "peri", 2, 200, 10, 36, 2, ["1 platano", "200 ml yogur liquido"], ["Fuera de casa."]),
    _r("p4", "Tortitas de arroz y miel", "peri", 2, 220, 4, 40, 4, ["2 tortitas", "miel"], ["Unta."]),
    _r("p5", "Datiles y yogur", "peri", 2, 230, 10, 38, 2, ["3 datiles", "150 g yogur"], ["Pica datiles."]),
    _r("d1", "Salteado de pollo y verduras", "dinner", 18, 480, 42, 22, 22, ["180 g pollo", "pimiento", "calabacin"], ["Saltea 12 min."]),
    _r("d2", "Hamburguesa de pavo con calabacin", "dinner", 16, 430, 40, 12, 22, ["180 g pavo picado", "calabacin"], ["Plancha."]),
    _r("d3", "Revuelto de huevo, espinacas y queso", "dinner", 10, 390, 30, 8, 26, ["3 huevos", "espinacas", "queso fresco"], ["Revuelve."]),
    _r("d4", "Tofu salteado con arroz", "dinner", 15, 510, 28, 55, 18, ["150 g tofu", "60 g arroz", "verdura"], ["Saltea tofu."]),
    _r("d5", "Muslo de pollo al horno y ensalada", "dinner", 25, 520, 44, 16, 28, ["muslo sin piel", "ensalada", "patata micro"], ["Horno 20 min."]),
    _r("d6", "Pavo plancha con judias verdes", "dinner", 16, 410, 40, 16, 16, ["180 g pavo", "judias verdes"], ["Plancha + vapor."]),
    _r("d7", "Calabacin relleno de pollo", "dinner", 20, 390, 36, 14, 18, ["1 calabacin", "150 g pollo picado", "tomate"], ["Horno o sarten 15 min."]),
    _r("d8", "Sopa de lentejas y huevo poche", "dinner", 15, 420, 26, 48, 10, ["lentejas bote", "caldo", "1 huevo"], ["Hierve 8 min, huevo encima."]),
    _r("d9", "Merluza plancha y brocoli", "dinner", 16, 390, 40, 12, 12, ["180 g merluza", "150 g brocoli", "limon"], ["Plancha 4 min/lado."]),
    _r("d10", "Salmon al horno con calabacin", "dinner", 22, 480, 38, 10, 28, ["160 g salmon", "1 calabacin"], ["Horno 180C 15 min o airfryer 12."]),
    _r("d11", "Atun salteado con verduras", "dinner", 12, 400, 36, 14, 16, ["120 g atun al natural", "pimiento", "cebolla"], ["Saltea verdura 6 min, anade atun."]),
    _r("d12", "Bacalao al micro con tomate", "dinner", 12, 360, 38, 10, 10, ["180 g bacalao desalado", "tomate", "aceite 1 cdita"], ["Micro tapado 6 min."]),
    _r("d13", "Tofu con champiñones", "dinner", 14, 380, 26, 12, 22, ["150 g tofu", "200 g champiñones", "soja"], ["Saltea 8 min."]),
    _r("d14", "Trucha al horno y ensalada", "dinner", 20, 420, 40, 8, 20, ["180 g trucha", "ensalada", "limon"], ["Horno 180C 12 min."]),
    _r("d15", "Revuelto de claras y pavo", "dinner", 10, 340, 36, 6, 16, ["4 claras + 1 huevo", "80 g pavo", "espinacas"], ["Revuelve 4 min."]),
    _r("d16", "Calabacín a la plancha y ternera", "dinner", 16, 430, 38, 10, 22, ["150 g ternera magra", "1 calabacin"], ["Plancha 6+6 min."]),
]

def recipe_by_id(recipe_id: str):
    for item in RECIPES:
        if item["id"] == recipe_id:
            return item
    return None

def recipes_for(slot: str, goal: str = "", day_kind: str = ""):
    return [x for x in RECIPES if x["slot"] == slot]
