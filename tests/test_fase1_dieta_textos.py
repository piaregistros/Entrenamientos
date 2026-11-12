"""Fase 1: tildes en la dieta sin romper IDs ni la lista de la compra."""
import json

from conftest import PABLO_ID
from app.diet_catalog import RECIPES, GOALS, recipe_by_id
from app.diet_text import accentuate, accentuate_week
from app.database import get_connection


def test_accentuate_basico_e_idempotente():
    assert accentuate("Tostada de atun y tomate") == "Tostada de atún y tomate"
    assert accentuate("Atun, arroz") == "Atún, arroz"
    assert accentuate("añade atún") == "añade atún"  # idempotente
    assert accentuate(accentuate("1 platano")) == "1 plátano"
    assert accentuate("calabacinada") == "calabacinada"  # solo palabras completas
    assert accentuate(None) is None


def test_catalogo_ids_intactos_y_sin_palabras_sin_tilde():
    ids = [r["id"] for r in RECIPES]
    assert len(ids) == len(set(ids))
    for rid in ("b1", "l1", "s1", "p1", "d1"):
        assert recipe_by_id(rid) is not None
    assert set(GOALS) == {"lose_fat", "recomp", "maintain", "gain_muscle", "performance"}
    for r in RECIPES:
        for text in [r["name"], *r["ingredients"], *r["steps"]]:
            assert accentuate(text) == text, f"{r['id']}: '{text}' aún sin tildes"


def test_receta_devuelta_por_api_con_tilde(client):
    r = client.get("/api/diet/recipes/b8")
    assert r.status_code == 200
    assert r.json()["name"] == "Tostada de atún y tomate"
    assert r.json()["id"] == "b8"


def test_plan_guardado_sin_tildes_se_corrige_al_leer(client):
    week = client.get("/api/diet/week").json()
    assert week["days"]
    # Simula un plan antiguo guardado sin tildes
    conn = get_connection()
    try:
        row = conn.execute("SELECT id, payload FROM diet_week_plans WHERE user_id=?", (PABLO_ID,)).fetchone()
        payload = json.loads(row["payload"])
        payload["days"][0]["meals"][0]["name"] = "Tostada de atun y tomate"
        payload["days"][0]["meals"][0]["ingredients"] = ["2 tostadas", "80 g atun al natural"]
        conn.execute("UPDATE diet_week_plans SET payload=? WHERE id=?", (json.dumps(payload), row["id"]))
        conn.commit()
    finally:
        conn.close()
    again = client.get("/api/diet/week").json()
    meal = again["days"][0]["meals"][0]
    assert meal["name"] == "Tostada de atún y tomate"
    assert "80 g atún al natural" in meal["ingredients"]


def test_lista_compra_con_tildes(client):
    client.get("/api/diet/week")
    r = client.get("/api/diet/shopping-list")
    assert r.status_code == 200
    items = json.dumps(r.json(), ensure_ascii=False)
    for bad in ("Platano", "Calabacin", "Brocoli", "Atun ", "Salmon "):
        assert bad not in items
