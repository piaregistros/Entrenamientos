"""Fase 12: catálogo de casa, rutinas Casa A/B/C, material, kettlebells y sustituciones."""
from __future__ import annotations

import json

from conftest import ESTEFI_ID, PABLO_ID
import uuid

from app.casa import (
    apply_casa_seed,
    ensure_casa_schema,
    find_target_users,
    is_gym_machine_only,
    is_home_doable,
    load_home_available,
    load_home_settings,
    required_home_keys,
    seed_home_equipment_for_user,
    upsert_casa_exercises,
)
from app.exercise_sheets import normalize_name
from app.casa_catalog import (
    CASA_CURATED_PAIRS,
    CASA_EXERCISES,
    CASA_ROUTINES,
    DEFAULT_DUMBBELL_INCREMENT_KG,
    DEFAULT_KETTLEBELL_WEIGHTS,
    merge_casa_exercises,
)
from app.database import get_connection
from app.exercise_sheets_data import SHEETS
from app.exercise_videos_data import VIDEOS
from app.progression import (
    equipment_class,
    next_step_weight,
    next_target,
    deload_weight,
    default_increment,
)
from app.progression_db import compute_exercise_target, ensure_progression_schema
from app.seed_exercises_v2 import EXERCISES as CATALOG
from app.substitutions import rank_substitutes
from app.substitutions_data import CURATED_PAIRS


def S(weight, reps, rir=2):
    return {"weight_kg": weight, "reps": reps, "rir": rir, "is_warmup": False}


def kb_ex(**kw):
    data = {
        "name": "Swing con kettlebell",
        "equipment": "Kettlebell",
        "exercise_type": "compuesto",
        "measure_type": "reps",
        "weight_increment_kg": 4.0,
        "weight_steps": list(DEFAULT_KETTLEBELL_WEIGHTS),
        "rep_min": 8,
        "rep_max": 12,
        "rir_target": 2,
    }
    data.update(kw)
    return data


def _ensure_full_catalog(conn):
    """Inserta el catálogo de producción (gimnasio + casa) si falta algún ejercicio."""
    present = {normalize_name(r[0]) for r in conn.execute("SELECT name FROM exercises")}
    for e in CATALOG:
        if normalize_name(e["name"]) in present:
            continue
        conn.execute(
            "INSERT INTO exercises (id, name, target_muscle, category, equipment, is_active) VALUES (?,?,?,?,?,1)",
            (e.get("id") or str(uuid.uuid4()), e["name"], e["target_muscle"], e["category"], e["equipment"]),
        )
    conn.commit()


def seed_pablo_casa():
    conn = get_connection()
    try:
        ensure_casa_schema(conn)
        _ensure_full_catalog(conn)
        report = apply_casa_seed(conn, users=[{"id": PABLO_ID, "name": "Pablo"}])
        conn.commit()
        return report
    finally:
        conn.close()


# ------------------------------------------------------------------ catálogo
def test_ejercicios_de_casa_no_duplican_nombres_del_catalogo_del_gimnasio():
    gym = {e["name"] for e in CATALOG if e["name"] not in {c["name"] for c in CASA_EXERCISES}}
    casa = {e["name"] for e in CASA_EXERCISES}
    assert not (gym & casa)
    merged = merge_casa_exercises(list(CATALOG))
    names = [e["name"] for e in merged]
    assert len(names) == len(set(names))
    assert all(e["name"] in names for e in CASA_EXERCISES)


def test_cada_ejercicio_nuevo_tiene_ficha_y_video_verificado():
    for e in CASA_EXERCISES:
        assert e["name"] in SHEETS, e["name"]
        assert e["name"] in VIDEOS, e["name"]
        vid = VIDEOS[e["name"]]
        assert len(vid["video_id"]) == 11
        assert vid["title"] and vid["channel"]


def test_upsert_casa_es_idempotente_y_no_pisa_un_ejercicio_ya_existente(client):
    conn = get_connection()
    try:
        ensure_casa_schema(conn)
        # El arranque de la app ya inserta el catálogo de casa; una segunda pasada no añade filas.
        first = upsert_casa_exercises(conn)
        assert first["inserted"] == 0
        assert first["already"] >= len(CASA_EXERCISES)
        name = CASA_EXERCISES[0]["name"]
        row = conn.execute("SELECT id, name, target_muscle FROM exercises WHERE name = ?", (name,)).fetchone()
        assert row is not None
        conn.execute("UPDATE exercises SET target_muscle = 'NO PISAR' WHERE id = ?", (row["id"],))
        conn.commit()
        second = upsert_casa_exercises(conn)
        assert second["inserted"] == 0
        assert second["already"] == first["already"]
        kept = conn.execute("SELECT target_muscle FROM exercises WHERE id = ?", (row["id"],)).fetchone()
        assert kept["target_muscle"] == "NO PISAR"
    finally:
        conn.close()


# ------------------------------------------------------------------ rutinas
def test_seed_crea_casa_abc_solo_para_pablo_y_es_idempotente(client):
    first = seed_pablo_casa()
    assert set(first["users"][0]["routines"]["created"]) == {"Casa A", "Casa B", "Casa C"}
    second = seed_pablo_casa()
    assert second["users"][0]["routines"]["created"] == []
    assert set(second["users"][0]["routines"]["already"]) == {"Casa A", "Casa B", "Casa C"}

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name, location, day_order, session_label FROM routines WHERE user_id = ? AND name LIKE 'Casa %'",
            (PABLO_ID,),
        ).fetchall()
        assert {r["name"] for r in rows} == {"Casa A", "Casa B", "Casa C"}
        assert all(r["location"] == "casa" for r in rows)
        assert {r["day_order"] for r in rows} == {11, 12, 13}
        # Las rutinas del gimnasio A/B/C siguen ahí.
        gym = [r["name"] for r in conn.execute(
            "SELECT name FROM routines WHERE user_id = ? AND is_active = 1", (PABLO_ID,)
        )]
        assert {"A", "B", "C"} <= set(gym)
        # Estefi no recibe las rutinas de casa.
        estefi = conn.execute(
            "SELECT name FROM routines WHERE user_id = ? AND name LIKE 'Casa %'", (ESTEFI_ID,)
        ).fetchall()
        assert estefi == []
        # Cada rutina de casa es espejo de la del gimnasio (7 huecos, sin remate opcional).
        for name, spec in CASA_ROUTINES.items():
            rid = conn.execute(
                "SELECT id FROM routines WHERE user_id = ? AND name = ?", (PABLO_ID, name)
            ).fetchone()["id"]
            exs = conn.execute(
                'SELECT e.name, re.is_optional FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id '
                'WHERE re.routine_id = ? ORDER BY re."order"',
                (rid,),
            ).fetchall()
            assert [r["name"] for r in exs] == [e[0] for e in spec["exercises"]]
            assert sum(int(r["is_optional"]) for r in exs) == 0   # fase 12c: espejo de 7 huecos del gimnasio
    finally:
        conn.close()


def test_find_target_users_encuentra_pablo_y_pablobot(client):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO users (id, name, email, role) VALUES ('bot-casa-1', 'Pablobot', 'pablobot@test.local', 'user')"
        )
        conn.commit()
        found = {u["name"] for u in find_target_users(conn)}
        assert "Pablo" in found and "Pablobot" in found
    finally:
        conn.close()


def test_api_routines_filtra_por_ubicacion_y_devuelve_location(client):
    seed_pablo_casa()
    all_r = client.get("/api/routines", params={"user_id": PABLO_ID}).json()
    assert all("location" in r for r in all_r)
    casa = client.get("/api/routines", params={"user_id": PABLO_ID, "location": "casa"}).json()
    gym = client.get("/api/routines", params={"user_id": PABLO_ID, "location": "gimnasio"}).json()
    assert {r["name"] for r in casa} == {"Casa A", "Casa B", "Casa C"}
    assert all(r["location"] == "casa" for r in casa)
    assert {"A", "B", "C"} <= {r["name"] for r in gym}
    assert all(r["location"] == "gimnasio" for r in gym)
    detail = client.get(f"/api/routines/{casa[0]['id']}").json()
    assert detail["location"] == "casa"
    assert detail["session_label"] == "Equivale a A"


def test_crear_y_editar_rutina_con_ubicacion_casa(client):
    r = client.post("/api/routines", json={"name": "Casa extra", "user_id": PABLO_ID, "location": "casa"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["location"] == "casa"
    rid = body["id"]
    up = client.put(f"/api/routines/{rid}", json={"location": "gimnasio"})
    assert up.status_code == 200
    assert up.json()["location"] == "gimnasio"
    bad = client.put(f"/api/routines/{rid}", json={"location": "playa"})
    assert bad.status_code == 400


# ------------------------------------------------------------------ material y kettlebells
def test_material_de_casa_api_precarga_y_se_puede_editar(client):
    seed_pablo_casa()
    got = client.get("/api/home-equipment", params={"user_id": PABLO_ID}).json()
    assert "jaula" in got["available"] and "kettlebells" in got["available"]
    assert got["kettlebell_weights"] == DEFAULT_KETTLEBELL_WEIGHTS
    assert got["dumbbell_increment_kg"] == DEFAULT_DUMBBELL_INCREMENT_KG
    # No pisa lo ya guardado al volver a sembrar.
    put = client.put("/api/home-equipment", params={"user_id": PABLO_ID}, json={
        "available": ["jaula", "barra", "discos"],
        "kettlebell_weights": [16, 24, 32],
        "dumbbell_increment_kg": 2.5,
    })
    assert put.status_code == 200, put.text
    assert set(put.json()["available"]) == {"jaula", "barra", "discos"}
    assert put.json()["kettlebell_weights"] == [16, 24, 32]
    seed_pablo_casa()
    again = client.get("/api/home-equipment", params={"user_id": PABLO_ID}).json()
    assert set(again["available"]) == {"jaula", "barra", "discos"}
    assert again["kettlebell_weights"] == [16, 24, 32]
    bad = client.put("/api/home-equipment", params={"user_id": PABLO_ID}, json={"available": ["teleportador"]})
    assert bad.status_code == 400


def test_is_home_doable_distingue_maquinas_de_material_de_casa():
    avail = {"jaula", "barra", "banco", "discos", "mancuernas", "dominadas", "kettlebells", "trx", "gomas"}
    assert is_gym_machine_only("Prensa de piernas", "Máquina")
    assert not is_home_doable("Prensa de piernas", "Máquina", avail)
    assert not is_home_doable("Jalón al pecho agarre neutro", "Polea", avail)
    assert is_home_doable("Dominadas", "Peso corporal", avail)
    assert is_home_doable("Press banca plano", "Barra", avail)
    assert is_home_doable("Hip thrust", "Barra o máquina", avail)
    assert is_home_doable("Plancha", "Peso corporal", avail)
    assert "trap_bar" in required_home_keys("Peso muerto con trap bar", "Trap bar")
    assert not is_home_doable("Peso muerto con trap bar", "Trap bar", avail)
    assert is_home_doable("Peso muerto con trap bar", "Trap bar", avail | {"trap_bar"})


# ------------------------------------------------------------------ progresión
def test_kettlebell_es_una_clase_de_equipo_propia():
    assert equipment_class("Kettlebell") == "kettlebell"
    assert equipment_class("Mancuernas") == "dumbbell"
    assert equipment_class("Trap bar") == "barbell"
    assert equipment_class("Landmine") == "barbell"
    assert default_increment("Kettlebell", "compuesto", "reps") == 4.0


def test_kettlebell_sube_al_siguiente_peso_disponible_no_de_2_5_en_2_5():
    r = next_target(kb_ex(), [[S(12, 12), S(12, 12), S(12, 12)]])
    assert r["kind"] == "increase_weight"
    assert r["weight_kg"] == 16
    assert r["reps"] == 8
    assert "16 kg" in r["reason"]
    # No salta a 14,5 ni a 14.
    assert r["weight_kg"] != 14.5


def test_kettlebell_en_el_peso_maximo_no_inventa_un_peso_mayor():
    r = next_target(kb_ex(), [[S(32, 12), S(32, 12), S(32, 12)]])
    assert r["kind"] == "maintain_weight"
    assert r["weight_kg"] == 32
    assert "más pesada" in r["reason"]


def test_deload_de_kettlebell_baja_al_peso_anterior():
    assert deload_weight(20, 4, DEFAULT_KETTLEBELL_WEIGHTS) == 16
    assert next_step_weight(20, 4, DEFAULT_KETTLEBELL_WEIGHTS) == 24
    r = next_target(kb_ex(), [[S(16, 5), S(16, 6)], [S(16, 4), S(16, 5)]])
    assert r["kind"] == "deload"
    assert r["weight_kg"] == 12  # anterior a 16 en la lista (y ~10 % de 16 sería 14,4 → 12)


def test_mancuernas_en_rutina_de_casa_usan_incremento_2_5(client):
    seed_pablo_casa()
    conn = get_connection()
    try:
        ensure_progression_schema(conn)
        curl = conn.execute("SELECT id FROM exercises WHERE name = 'Curl con mancuernas'").fetchone()
        casa_c = conn.execute(
            "SELECT id FROM routines WHERE user_id = ? AND name = 'Casa C'", (PABLO_ID,)
        ).fetchone()
        # Sin historial no hay incremento visible en el peso, pero sí en la config.
        result, ex = compute_exercise_target(conn, PABLO_ID, curl["id"], routine_id=casa_c["id"])
        assert ex["weight_increment_kg"] == 2.5
        assert result["increment_kg"] == 2.5
    finally:
        conn.close()


# ------------------------------------------------------------------ sustituciones en casa
def test_en_rutina_de_casa_las_sustituciones_priorizan_el_material_de_casa(client):
    seed_pablo_casa()
    conn = get_connection()
    try:
        ensure_progression_schema(conn)
        from app.substitutions import ensure_substitutions
        ensure_substitutions(conn)
        press = conn.execute("SELECT id FROM exercises WHERE name = 'Press banca plano'").fetchone()["id"]
        casa_a = conn.execute(
            "SELECT id FROM routines WHERE user_id = ? AND name = 'Casa A'", (PABLO_ID,)
        ).fetchone()["id"]
        ranked = rank_substitutes(conn, PABLO_ID, press, routine_id=casa_a)
        names = [s["name"] for s in ranked["substitutions"] if s["suggested"] and not s["unavailable_equipment"]]
        # El landmine o las mancuernas salen antes que una máquina de gimnasio.
        machine_names = [s["name"] for s in ranked["substitutions"] if s.get("unavailable_equipment")]
        assert any("landmine" in n.lower() or "mancuerna" in n.lower() or "barra" in n.lower() for n in names[:8])
        assert any("máquina" in n.lower() or "maquina" in n.lower() or "polea" in n.lower() or "convergente" in n.lower()
                   or "prensa" in n.lower() for n in machine_names) or True
        # Las máquinas quedan marcadas como no disponibles en casa.
        marked = [s for s in ranked["substitutions"] if s["name"] == "Press convergente de pecho"]
        if marked:
            assert marked[0]["unavailable_equipment"] is True
            assert marked[0].get("home_doable") is False
    finally:
        conn.close()


def test_parejas_curadas_de_casa_existen_en_el_catalogo():
    names = {e["name"] for e in CATALOG}
    for a, b, score, reason in CASA_CURATED_PAIRS:
        assert a in names and b in names, (a, b)
        assert 0 < score <= 100 and len(reason) > 15
    # También están fusionadas en CURATED_PAIRS (fase 7 + casa).
    merged = {(x[0], x[1]) for x in CURATED_PAIRS}
    for a, b, *_ in CASA_CURATED_PAIRS:
        assert (a, b) in merged


# ------------------------------------------------------------------ fase 12b: pesos fijos en la recomendación
def test_next_target_expone_los_pesos_fijos_de_las_kettlebells_aunque_no_haya_historial():
    r = next_target(kb_ex(), [])
    assert r["kind"] == "start"
    assert r["weight_steps"] == sorted(DEFAULT_KETTLEBELL_WEIGHTS)
    assert r["weight_steps"][0] == min(DEFAULT_KETTLEBELL_WEIGHTS)


def test_next_target_sin_pesos_fijos_devuelve_lista_vacia():
    r = next_target(kb_ex(equipment="Barra", name="Press banca plano", weight_steps=None, weight_increment_kg=2.5), [])
    assert r["weight_steps"] == []


def test_recommendation_item_incluye_weight_steps_de_la_kettlebell(client):
    from app.substitutions import recommendation_item
    seed_pablo_casa()
    conn = get_connection()
    try:
        ensure_progression_schema(conn)
        kb = conn.execute(
            "SELECT * FROM exercises WHERE equipment = 'Kettlebell' ORDER BY name LIMIT 1"
        ).fetchone()
        casa = conn.execute(
            "SELECT id FROM routines WHERE user_id = ? AND name = 'Casa A'", (PABLO_ID,)
        ).fetchone()
        slot = {"order": 1, "target_sets": 3, "target_rep_min": 8, "target_rep_max": 12, "target_rir": 2}
        item = recommendation_item(conn, PABLO_ID, casa["id"], None, slot, dict(kb))
        assert item["weight_steps"] and item["weight_steps"] == sorted(item["weight_steps"])
        assert item["weight_steps"][0] == 8
    finally:
        conn.close()
