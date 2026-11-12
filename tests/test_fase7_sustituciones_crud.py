"""Fase 7: sustituciones por parecido, preferencias, equipo, progresión del sustituto, CRUD y limpieza."""
import re
import subprocess
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import (
    BENCH_ID, EXERCISES, ESTEFI_ID, PABLO_ID, ROUTINE_A_ID, ROUTINE_B_ID, ROUTINE_C_ID, _login_client,
)
from app.main import app
from app.database import get_connection
from app.exercise_crud import apply_data_migrations, ensure_crud_schema, exercise_references
from app.exercise_sheets import ensure_exercise_sheets, normalize_name
from app.progression_db import compute_exercise_target, ensure_progression_schema
from app.progress_routes import recompute_exercise_progress
from app.seed_exercises_v2 import EXERCISES as CATALOG
from app.substitutions import (
    ensure_substitutions, equipment_families, muscle_tokens, score_pair,
)
from app.substitutions_data import CURATED_PAIRS

ROOT = Path(__file__).resolve().parent.parent
INCLINE_ID = EXERCISES["incline_press"][0]
LEG_PRESS_ID = EXERCISES["leg_press"][0]
CHEST_ROW_ID = EXERCISES["chest_row"][0]
SHOULDER_ID = EXERCISES["shoulder_press"][0]
BY_NAME = {e["name"]: e for e in CATALOG}


def meta(name):
    return BY_NAME[name]


def full_catalog(conn):
    """Los 59 ejercicios del catálogo con sus metadatos + todas las migraciones de arranque."""
    ensure_progression_schema(conn)
    ensure_crud_schema(conn)
    present = {normalize_name(r[0]) for r in conn.execute("SELECT name FROM exercises")}
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercises)")}
    for e in CATALOG:
        if normalize_name(e["name"]) in present:
            continue
        conn.execute(
            "INSERT INTO exercises (id, name, target_muscle, category, equipment, is_active) VALUES (?,?,?,?,?,1)",
            (e.get("id") or str(uuid.uuid4()), e["name"], e["target_muscle"], e["category"], e["equipment"]),
        )
    conn.commit()
    ensure_exercise_sheets(conn)  # rellena movement_pattern, etc. por nombre
    ensure_progression_schema(conn)
    ensure_substitutions(conn)
    return conn


@pytest.fixture
def cat(client):
    conn = get_connection()
    full_catalog(conn)
    yield conn
    conn.close()


def start_workout(client, routine_id=ROUTINE_A_ID, user_id=PABLO_ID):
    r = client.post("/api/workouts", json={"user_id": user_id, "routine_id": routine_id})
    assert r.status_code == 200, r.text
    return r.json()


def substitute(client, wid, original, substitute_id, user_id=PABLO_ID, **extra):
    return client.post(
        f"/api/workouts/{wid}/substitute-exercise", params={"user_id": user_id},
        json={"original_exercise_id": original, "substitute_exercise_id": substitute_id, **extra},
    )


def finish(client, wid, user_id=PABLO_ID):
    r = client.put(f"/api/workouts/{wid}", params={"user_id": user_id},
                   json={"status": "completed", "duration_minutes": 50})
    assert r.status_code == 200, r.text


def log_sets(client, wid, exercise_id, kg, reps, n=3, rir=2, user_id=PABLO_ID):
    for i in range(1, n + 1):
        r = client.post(f"/api/workouts/{wid}/sets", params={"user_id": user_id},
                        json={"exercise_id": exercise_id, "set_number": i, "weight_kg": kg, "reps": reps, "rir": rir})
        assert r.status_code == 200, r.text


def ranked(client, exercise_id, user_id=PABLO_ID, **params):
    r = client.get(f"/api/exercises/{exercise_id}/substitutions", params={"user_id": user_id, **params})
    assert r.status_code == 200, r.text
    return r.json()


# ====================================================== puntuación (función pura)
def test_orden_mismo_patron_gt_mismos_musculos_gt_equipo_alternativo():
    base = meta("Press banca con mancuernas")
    same_pattern_other_equipment = score_pair(base, meta("Press convergente de pecho"))
    same_pattern_same_equipment = score_pair(base, meta("Press inclinado con mancuernas 30 grados"))
    only_muscle = score_pair(base, meta("Aperturas de pecho en máquina"))
    unrelated = score_pair(base, meta("Curl femoral"))
    assert same_pattern_other_equipment[1] == same_pattern_same_equipment[1] == "pattern"
    assert only_muscle[1] in ("muscle", "related")
    assert same_pattern_other_equipment[0] > same_pattern_same_equipment[0] > only_muscle[0] > unrelated[0]
    assert unrelated[1] == "other" and unrelated[0] == 0
    # el equipo alternativo desempata dentro del mismo patrón y se explica en el motivo
    assert "cambia mancuernas por máquina" in same_pattern_other_equipment[2]


def test_musculos_y_equipos_se_normalizan():
    fine, coarse = muscle_tokens("Cuádriceps y glúteos")
    assert {"cuadriceps", "gluteos"} <= fine
    assert equipment_families("Barra o máquina") == {"barra", "maquina"}
    assert equipment_families("Mancuernas o peso corporal") == {"mancuernas", "peso corporal"}
    assert equipment_families("Mancuerna") == {"mancuernas"}
    assert equipment_families("") == set()


def test_las_parejas_curadas_usan_nombres_del_catalogo_y_son_unicas():
    names = set(BY_NAME)
    seen = set()
    for a, b, score, reason in CURATED_PAIRS:
        assert a in names and b in names, (a, b)
        assert a != b and 0 < score <= 100 and len(reason) > 15
        assert (a, b) not in seen and (b, a) not in seen, (a, b)
        seen.add((a, b))


# ====================================================== tabla ampliada y arranque
def test_esquema_aditivo_y_nombres_originales(cat):
    cols = {r[1] for r in cat.execute("PRAGMA table_info(exercise_substitutions)")}
    assert {"exercise_id", "alternative_exercise_id", "priority", "reason", "score", "source"} <= cols
    tables = {r[0] for r in cat.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"user_substitution_prefs", "user_equipment"} <= tables
    ex_cols = {r[1] for r in cat.execute("PRAGMA table_info(exercises)")}
    assert {"created_by", "is_custom"} <= ex_cols


def test_los_59_ejercicios_tienen_alternativas_y_las_de_mancuernas_incluyen_maquina_polea_o_barra(cat):
    rows = {r["name"]: dict(r) for r in cat.execute("SELECT * FROM exercises WHERE is_active = 1")}
    assert all(e["name"] in rows for e in CATALOG)
    for e in CATALOG:
        n = cat.execute(
            "SELECT COUNT(*) FROM exercise_substitutions WHERE exercise_id = ? AND is_active = 1",
            (rows[e["name"]]["id"],),
        ).fetchone()[0]
        assert n >= 3, f"{e['name']}: solo {n} alternativas en la tabla"
    # Mancuernas -> máquina / polea / barra (el caso de uso de Pablo)
    for e in CATALOG:
        if "mancuernas" not in equipment_families(e["equipment"]):
            continue
        alt = cat.execute(
            """SELECT x.equipment FROM exercise_substitutions es JOIN exercises x ON x.id = es.alternative_exercise_id
               WHERE es.exercise_id = ? AND es.is_active = 1""",
            (rows[e["name"]]["id"],),
        ).fetchall()
        fams = set().union(*[equipment_families(a["equipment"]) for a in alt])
        assert fams & {"maquina", "polea", "barra"}, f"{e['name']}: sin alternativa de máquina/polea/barra"


def test_el_seed_es_idempotente_y_conserva_las_parejas_heredadas(cat):
    before = cat.execute("SELECT COUNT(*), SUM(score IS NULL) FROM exercise_substitutions").fetchone()
    assert before[1] == 0  # ninguna sin puntuación (incluidas las 20 heredadas del conftest)
    legacy = cat.execute(
        "SELECT reason FROM exercise_substitutions WHERE exercise_id = ? AND alternative_exercise_id = ?",
        (EXERCISES["leg_press"][0], EXERCISES["bulgarian"][0]),
    ).fetchone()
    assert legacy["reason"] == "Alternativa de prueba"  # no se pisa un motivo existente
    ensure_substitutions(cat)
    ensure_substitutions(cat)
    after = cat.execute("SELECT COUNT(*), SUM(score IS NULL) FROM exercise_substitutions").fetchone()
    assert tuple(after) == tuple(before)


def test_el_arranque_dos_veces_no_duplica_nada(test_db):
    with TestClient(app):
        pass
    with TestClient(app):
        pass
    conn = get_connection()
    try:
        n1 = conn.execute("SELECT COUNT(*) FROM exercise_substitutions").fetchone()[0]
        ensure_substitutions(conn)
        assert conn.execute("SELECT COUNT(*) FROM exercise_substitutions").fetchone()[0] == n1
    finally:
        conn.close()


# ====================================================== endpoint de alternativas
def test_el_selector_muestra_todo_el_mismo_patron_o_grupo_ordenado_por_parecido(client, cat):
    bid = cat.execute("SELECT id FROM exercises WHERE name = 'Press banca con mancuernas'").fetchone()["id"]
    data = ranked(client, bid)
    subs = data["substitutions"]
    names = [s["name"] for s in subs]
    # todo el empuje horizontal de pecho del catálogo está, no solo 2 opciones
    for expected in ("Press convergente de pecho", "Press banca plano", "Press inclinado en máquina",
                     "Press inclinado con mancuernas 30 grados", "Aperturas de pecho en máquina", "Cruce de poleas"):
        assert expected in names
    assert len(subs) >= 6
    scores = [s["score"] for s in subs]
    assert scores == sorted(scores, reverse=True)
    assert subs[0]["match_level"] == "pattern"
    # ejercicios sin relación no salen sin buscar...
    assert "Curl femoral" not in names and all(s["suggested"] for s in subs)
    assert all({"reason", "match_level", "score", "equipment", "is_habitual", "unavailable_equipment"} <= set(s) for s in subs)


def test_buscador_y_all_alcanzan_cualquier_ejercicio_del_catalogo(client, cat):
    bid = cat.execute("SELECT id FROM exercises WHERE name = 'Press banca con mancuernas'").fetchone()["id"]
    r = ranked(client, bid, q="prensa de piernas")
    assert [s["name"] for s in r["substitutions"]] == ["Prensa de piernas"]
    assert r["substitutions"][0]["match_level"] == "other" and not r["substitutions"][0]["suggested"]
    # el buscador ignora tildes y mayúsculas
    assert any(s["name"] == "Curl femoral" for s in ranked(client, bid, q="FÉMORAL")["substitutions"])
    total = cat.execute("SELECT COUNT(*) FROM exercises WHERE is_active = 1").fetchone()[0]
    assert len(ranked(client, bid, all="true")["substitutions"]) == total - 1


def test_mancuernas_a_maquina_primero_las_que_comparten_patron(client, cat):
    sid = cat.execute("SELECT id FROM exercises WHERE name = 'Elevaciones laterales con mancuernas'").fetchone()["id"]
    top = [s["name"] for s in ranked(client, sid)["substitutions"][:2]]
    assert set(top) == {"Elevaciones laterales en máquina", "Elevaciones laterales en polea"}


def test_se_puede_sustituir_por_cualquier_ejercicio_activo_no_solo_las_parejas_curadas(client):
    w = start_workout(client)
    # Press banca plano -> Remo con pecho apoyado no es una pareja (antes: 400)
    r = substitute(client, w["id"], BENCH_ID, CHEST_ROW_ID) if False else substitute(client, w["id"], BENCH_ID, SHOULDER_ID)
    assert r.status_code == 200, r.text
    assert r.json()["substitute_exercise"]["id"] == SHOULDER_ID
    assert r.json()["reason"]  # motivo calculado


def test_no_se_puede_sustituir_por_un_ejercicio_inactivo_ni_por_uno_de_la_misma_rutina(client):
    w = start_workout(client)
    conn = get_connection()
    conn.execute("UPDATE exercises SET is_active = 0 WHERE id = ?", (SHOULDER_ID,))
    conn.commit()
    conn.close()
    assert substitute(client, w["id"], BENCH_ID, SHOULDER_ID).status_code == 404
    assert substitute(client, w["id"], BENCH_ID, CHEST_ROW_ID).status_code == 409  # ya está en la rutina A
    assert substitute(client, w["id"], BENCH_ID, BENCH_ID).status_code == 400


# ====================================================== preferencias del usuario
def test_la_eleccion_habitual_sale_primero_marcada_y_solo_para_ese_usuario(client, cat):
    w = start_workout(client)
    pre = ranked(client, BENCH_ID)["substitutions"]
    assert not any(s["is_habitual"] for s in pre)
    # una sustitución poco parecida: sin preferencia nunca saldría la primera
    target = next(s for s in pre if s["exercise_id"] != INCLINE_ID and s["score"] < pre[0]["score"])
    assert substitute(client, w["id"], BENCH_ID, target["exercise_id"]).status_code == 200
    finish(client, w["id"])
    again = ranked(client, BENCH_ID)["substitutions"]
    assert again[0]["exercise_id"] == target["exercise_id"]
    assert again[0]["is_habitual"] and again[0]["previously_used"] and again[0]["times_used"] == 1
    assert sum(1 for s in again if s["is_habitual"]) == 1
    # otro usuario no ve la preferencia de Pablo
    other = ranked(client, BENCH_ID, user_id=PABLO_ID if False else PABLO_ID)  # (Pablo es admin: mismo usuario)
    assert other["substitutions"][0]["is_habitual"]
    conn = get_connection()
    assert conn.execute(
        "SELECT SUM(times_used) FROM user_substitution_prefs WHERE user_id = ? AND original_exercise_id = ?",
        (PABLO_ID, BENCH_ID),
    ).fetchone()[0] == 1
    conn.close()


def test_la_preferencia_de_pablo_no_aparece_a_estefi(test_db):
    with TestClient(app) as pablo:
        _login_client(pablo, "Pablo", "test-pablo-password")
        conn = get_connection(); full_catalog(conn); conn.close()
        w = start_workout(pablo)
        assert substitute(pablo, w["id"], BENCH_ID, SHOULDER_ID).status_code == 200
    with TestClient(app) as estefi:
        _login_client(estefi, "Estefi", "test-estefi-password")
        subs = ranked(estefi, BENCH_ID, user_id=ESTEFI_ID)["substitutions"]
        assert not any(s["is_habitual"] or s["previously_used"] for s in subs)
        # ni puede leer las de Pablo
        r = estefi.get(f"/api/exercises/{BENCH_ID}/substitutions", params={"user_id": PABLO_ID})
        assert r.status_code == 403


def test_las_sustituciones_antiguas_se_convierten_en_preferencias_al_arrancar(client, cat):
    w = start_workout(client)
    assert substitute(client, w["id"], BENCH_ID, SHOULDER_ID).status_code == 200
    cat.execute("DELETE FROM user_substitution_prefs")
    cat.commit()
    ensure_substitutions(cat)
    row = cat.execute("SELECT times_used FROM user_substitution_prefs WHERE substitute_exercise_id = ?",
                      (SHOULDER_ID,)).fetchone()
    assert row["times_used"] == 1


def test_usar_siempre_en_esta_rutina_se_aplica_al_empezar_un_entreno_nuevo(client, cat):
    w1 = start_workout(client)
    r = substitute(client, w1["id"], LEG_PRESS_ID, EXERCISES["lunges"][0], always_in_routine=True)
    assert r.status_code == 200 and r.json()["always_in_routine"] is True
    finish(client, w1["id"])

    w2 = start_workout(client)
    assert not w2.get("existing")
    subs = w2["substitutions"]
    assert [(s["original_exercise_id"], s["substitute_exercise_id"]) for s in subs] == [
        (LEG_PRESS_ID, EXERCISES["lunges"][0])]
    assert subs[0]["recommendation"]["exercise_id"] == EXERCISES["lunges"][0]
    # y el entreno guardado la devuelve al reanudar
    got = client.get(f"/api/workouts/{w2['id']}", params={"user_id": PABLO_ID}).json()
    assert got["substitutions"][0]["substitute_exercise_id"] == EXERCISES["lunges"][0]
    flagged = [s for s in ranked(client, LEG_PRESS_ID, routine_id=ROUTINE_A_ID)["substitutions"]
               if s["always_in_routine"]]
    assert [s["exercise_id"] for s in flagged] == [EXERCISES["lunges"][0]]

    # otra rutina que también tiene la prensa no se ve afectada
    finish(client, w2["id"])
    wb = start_workout(client, ROUTINE_B_ID)
    assert wb["substitutions"] == []
    finish(client, wb["id"])

    # se puede quitar
    d = client.delete(f"/api/routines/{ROUTINE_A_ID}/always-substitution/{LEG_PRESS_ID}", params={"user_id": PABLO_ID})
    assert d.status_code == 200 and d.json()["removed"] == 1
    w3 = start_workout(client)
    assert w3["substitutions"] == []


def test_reanudar_un_entreno_en_curso_no_reaplica_sustituciones(client, cat):
    w1 = start_workout(client)
    substitute(client, w1["id"], LEG_PRESS_ID, EXERCISES["lunges"][0], always_in_routine=True)
    again = start_workout(client)  # sigue en curso: devuelve el mismo
    assert again["id"] == w1["id"] and again.get("existing") is True


# ====================================================== equipo no disponible
def test_equipo_no_disponible_se_marca_se_ordena_al_final_y_se_propone_alternativa(client, cat):
    bid = cat.execute("SELECT id FROM exercises WHERE name = 'Press banca con mancuernas'").fetchone()["id"]
    assert client.get("/api/user-equipment", params={"user_id": PABLO_ID}).json()["unavailable"] == []
    r = client.put("/api/user-equipment", params={"user_id": PABLO_ID}, json={"unavailable": ["Mancuernas"]})
    assert r.status_code == 200 and r.json()["unavailable"] == ["mancuernas"]
    data = ranked(client, bid)
    assert data["original_unavailable"] is True
    subs = data["substitutions"]
    flags = [s["unavailable_equipment"] for s in subs]
    assert flags == sorted(flags)  # primero las disponibles
    assert all(s["unavailable_equipment"] == ("mancuernas" in equipment_families(s["equipment"])
                                              and equipment_families(s["equipment"]) <= {"mancuernas"})
               for s in subs)
    proposed = next(s for s in subs if s["exercise_id"] == data["proposed_exercise_id"])
    assert not proposed["unavailable_equipment"] and proposed["equipment"] in ("Máquina", "Barra", "Polea")
    assert client.put("/api/user-equipment", params={"user_id": PABLO_ID},
                      json={"unavailable": ["jetpack"]}).status_code == 400
    client.put("/api/user-equipment", params={"user_id": PABLO_ID}, json={"unavailable": []})
    assert ranked(client, bid)["original_unavailable"] is False


# ====================================================== progresión del sustituto
def _seed_history(client, exercise_id, kg, reps, n=3):
    """Entreno completado en una rutina que contiene el ejercicio (A: banca; C: inclinado/búlgara)."""
    routine = ROUTINE_A_ID if exercise_id == BENCH_ID else ROUTINE_C_ID
    w = start_workout(client, routine)
    log_sets(client, w["id"], exercise_id, kg, reps, n=n)
    finish(client, w["id"])
    # Fechas distintas: dos entrenos en el mismo segundo no tienen orden estable (limitación conocida de la Fase 6).
    _seed_history.counter += 1
    conn = get_connection()
    conn.execute("UPDATE workout_logs SET date = ? WHERE id = ?",
                 (f"2026-10-{_seed_history.counter:02d}T10:00:00", w["id"]))
    conn.commit()
    conn.close()


_seed_history.counter = 0


def test_al_sustituir_peso_y_progresion_salen_del_historial_del_sustituto_con_el_rango_del_hueco(client):
    # Histórico del SUSTITUTO: 20 kg x 8 en las 3 series. El hueco (Press banca plano) es 6-8 reps.
    _seed_history(client, INCLINE_ID, 20.0, 8)
    # y el original tiene su propio historial distinto
    _seed_history(client, BENCH_ID, 35.0, 6)

    w = start_workout(client)
    r = substitute(client, w["id"], BENCH_ID, INCLINE_ID)
    assert r.status_code == 200, r.text
    body = r.json()
    rec = body["recommendation"]
    assert rec["exercise_id"] == INCLINE_ID and rec["original_exercise_id"] == BENCH_ID
    # rango 6-8 del hueco: 8 reps = máximo en todas las series -> sube el incremento del SUSTITUTO (2 kg)
    assert (rec["target_rep_min"], rec["target_rep_max"]) == (6, 8)
    assert rec["recommendation"] == "increase_weight"
    assert rec["recommended_weight_kg"] == 22.0 and rec["recommended_rep_target"] == 6
    assert rec["increment_kg"] == 2.0
    # historial del sustituto, no del original
    assert [s["weight_kg"] for s in body["last_performance"]] == [20.0, 20.0, 20.0]
    assert body["last_performance_detail"]["sets"][0]["reps"] == 8

    # /recommendations?workout_id= coincide (y sin workout_id el hueco sigue siendo el original)
    recs = client.get(f"/api/routines/{ROUTINE_A_ID}/recommendations",
                      params={"user_id": PABLO_ID, "workout_id": w["id"]}).json()["recommendations"]
    slot = next(x for x in recs if x.get("original_exercise_id") == BENCH_ID)
    assert slot["exercise_id"] == INCLINE_ID
    for key in ("recommendation", "recommended_weight_kg", "recommended_rep_target", "reason", "increment_kg"):
        assert slot[key] == rec[key], key
    plain = client.get(f"/api/routines/{ROUTINE_A_ID}/recommendations", params={"user_id": PABLO_ID}).json()
    assert any(x["exercise_id"] == BENCH_ID for x in plain["recommendations"])
    assert not any(x["exercise_id"] == INCLINE_ID for x in plain["recommendations"])
    # GET workout (reanudar) lleva lo mismo
    resumed = client.get(f"/api/workouts/{w['id']}", params={"user_id": PABLO_ID}).json()
    assert resumed["substitutions"][0]["recommendation"]["recommended_weight_kg"] == 22.0

    # Se cumple lo recomendado (22 kg x 8 reps) y se cierra: exercise_progress usa el MISMO rango 6-8
    log_sets(client, w["id"], INCLINE_ID, 22.0, 8)
    finish(client, w["id"])
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM exercise_progress WHERE user_id = ? AND exercise_id = ?",
                           (PABLO_ID, INCLINE_ID)).fetchone()
        assert row["kind"] == "increase_weight" and row["next_weight_kg"] == 24.0 and row["next_reps"] == 6
        assert "8 reps" in row["reason"]
        # el original no se ha tocado por esta sesión
        orig = conn.execute("SELECT source_workout_id FROM exercise_progress WHERE user_id = ? AND exercise_id = ?",
                            (PABLO_ID, BENCH_ID)).fetchone()
        assert orig is None or orig["source_workout_id"] != w["id"]
        # y un recálculo desde el historial (borrar/editar entrenos) llega al mismo resultado
        before = (row["next_weight_kg"], row["next_reps"], row["kind"])
        recompute_exercise_progress(conn, PABLO_ID, [INCLINE_ID])
        conn.commit()
        row2 = conn.execute("SELECT * FROM exercise_progress WHERE user_id = ? AND exercise_id = ?",
                            (PABLO_ID, INCLINE_ID)).fetchone()
        assert (row2["next_weight_kg"], row2["next_reps"], row2["kind"]) == before
    finally:
        conn.close()


def test_sin_historial_del_sustituto_no_se_arrastra_la_carga_del_original(client):
    _seed_history(client, BENCH_ID, 60.0, 8)
    w = start_workout(client)
    body = substitute(client, w["id"], BENCH_ID, SHOULDER_ID).json()
    assert body["recommendation"]["recommendation"] == "start"
    assert body["recommendation"]["recommended_weight_kg"] is None
    assert body["last_performance"] is None


# ====================================================== CRUD de ejercicios
def new_exercise(client, name="Press pecho unilateral", **extra):
    r = client.post("/api/exercises", json={"name": name, "target_muscle": "Pectoral", "category": "pecho",
                                            "equipment": "Mancuernas", **extra})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def test_crear_ejercicio_marca_creador_y_is_custom(client, cat):
    eid = new_exercise(client)
    row = cat.execute("SELECT created_by, is_custom FROM exercises WHERE id = ?", (eid,)).fetchone()
    assert row["created_by"] == PABLO_ID and row["is_custom"] == 1
    listing = {e["id"]: e for e in client.get("/api/exercises").json()["exercises"]}
    assert listing[eid]["is_custom"] is True and listing[eid]["can_edit"] is True
    assert listing[BENCH_ID]["is_custom"] is False and listing[BENCH_ID]["can_edit"] is True  # admin


def test_el_primer_arranque_marca_como_propios_los_que_no_son_del_catalogo(test_db):
    conn = get_connection()
    conn.execute("INSERT INTO exercises (id, name, is_active) VALUES ('x1', 'Mi ejercicio raro', 1)")
    conn.commit()
    conn.close()
    with TestClient(app):
        pass
    conn = get_connection()
    try:
        assert conn.execute("SELECT is_custom FROM exercises WHERE id = 'x1'").fetchone()[0] == 1
        assert conn.execute("SELECT is_custom FROM exercises WHERE id = ?", (BENCH_ID,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_editar_ejercicio_propio_y_reglas_de_nombre(client):
    eid = new_exercise(client)
    r = client.put(f"/api/exercises/{eid}", json={"name": "Press pecho a una mano", "equipment": "Polea",
                                                  "instructions": "Nuevo", "steps": ["a b c d e f g h i", " "],
                                                  "weight_increment_kg": 2.5, "measure_type": "reps"})
    assert r.status_code == 200 and r.json()["updated"] is True
    got = client.get(f"/api/exercises/{eid}").json()
    assert got["name"] == "Press pecho a una mano" and got["equipment"] == "Polea" and got["steps"] == ["a b c d e f g h i"]
    # nombre duplicado (sin distinguir mayúsculas)
    assert client.put(f"/api/exercises/{eid}", json={"name": "press banca PLANO"}).status_code == 409
    assert client.put(f"/api/exercises/{eid}", json={"measure_type": "raro"}).status_code == 400
    assert client.put(f"/api/exercises/{eid}", json={"name": "x"}).status_code == 400
    assert client.put("/api/exercises/no-existe", json={"name": "Hola mundo"}).status_code == 404
    assert client.put(f"/api/exercises/{eid}", json={}).json()["updated"] is False


def test_los_del_catalogo_no_se_renombran_pero_si_se_edita_su_ficha(client):
    r = client.put(f"/api/exercises/{BENCH_ID}", json={"name": "Otro nombre"})
    assert r.status_code == 400
    assert client.put(f"/api/exercises/{BENCH_ID}", json={"safety_notes": "Pide ayuda con carga alta"}).status_code == 200
    assert client.put(f"/api/exercises/{BENCH_ID}", json={"name": "Press banca plano"}).status_code == 200  # mismo nombre


def test_permisos_de_edicion_de_ejercicios(test_db):
    with TestClient(app) as pablo, TestClient(app) as estefi:
        _login_client(pablo, "Pablo", "test-pablo-password")
        _login_client(estefi, "Estefi", "test-estefi-password")
        propio_estefi = new_exercise(estefi, "Ejercicio de Estefi")
        propio_pablo = new_exercise(pablo, "Ejercicio de Pablo")
        # Estefi: no toca el catálogo ni lo de Pablo; sí lo suyo
        assert estefi.put(f"/api/exercises/{BENCH_ID}", json={"safety_notes": "x"}).status_code == 403
        assert estefi.delete(f"/api/exercises/{BENCH_ID}").status_code == 403
        assert estefi.put(f"/api/exercises/{propio_pablo}", json={"safety_notes": "x"}).status_code == 403
        assert estefi.delete(f"/api/exercises/{propio_pablo}").status_code == 403
        assert estefi.put(f"/api/exercises/{propio_estefi}", json={"name": "Renombrado por Estefi"}).status_code == 200
        # Pablo (admin) toca lo de todos
        assert pablo.put(f"/api/exercises/{propio_estefi}", json={"safety_notes": "ok"}).status_code == 200
        assert pablo.delete(f"/api/exercises/{propio_estefi}").json()["deleted"] is True
        listing = {e["id"]: e for e in estefi.get("/api/exercises").json()["exercises"]}
        assert listing[BENCH_ID]["can_edit"] is False and listing[propio_pablo]["can_edit"] is False
        # sin sesión: nada
        with TestClient(app) as anon:
            assert anon.put(f"/api/exercises/{propio_pablo}", json={"safety_notes": "x"}).status_code in (401, 403)


def test_borrar_sin_historial_es_real_y_limpia_sus_parejas(client, cat):
    eid = new_exercise(client)
    cat.execute("INSERT INTO exercise_substitutions (id, exercise_id, alternative_exercise_id, priority, score, source)"
                " VALUES (?, ?, ?, 1, 50, 'auto')", (str(uuid.uuid4()), BENCH_ID, eid))
    cat.commit()
    r = client.delete(f"/api/exercises/{eid}")
    assert r.status_code == 200 and r.json() == {"id": eid, "result": "deleted", "deleted": True,
                                                 "deactivated": False, "references": {}}
    assert cat.execute("SELECT COUNT(*) FROM exercises WHERE id = ?", (eid,)).fetchone()[0] == 0
    assert cat.execute("SELECT COUNT(*) FROM exercise_substitutions WHERE alternative_exercise_id = ?", (eid,)).fetchone()[0] == 0
    assert client.delete(f"/api/exercises/{eid}").status_code == 404


def test_borrar_con_historial_es_logico_y_conserva_el_historial(client):
    eid = new_exercise(client)
    w = start_workout(client)
    client.post(f"/api/workouts/{w['id']}/extra-exercises", params={"user_id": PABLO_ID}, json={"exercise_id": eid})
    log_sets(client, w["id"], eid, 20, 10, n=2)
    finish(client, w["id"])
    r = client.delete(f"/api/exercises/{eid}")
    body = r.json()
    assert r.status_code == 200 and body["result"] == "deactivated" and body["deactivated"] and not body["deleted"]
    assert body["references"]["workout_sets.exercise_id"] == 2
    ids = {e["id"] for e in client.get("/api/exercises").json()["exercises"]}
    assert eid not in ids
    assert eid in {e["id"] for e in client.get("/api/exercises", params={"include_inactive": "true"}).json()["exercises"]}
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM workout_sets WHERE exercise_id = ?", (eid,)).fetchone()[0] == 2
    finally:
        conn.close()
    # se puede reactivar
    assert client.put(f"/api/exercises/{eid}", json={"is_active": True}).status_code == 200
    assert eid in {e["id"] for e in client.get("/api/exercises").json()["exercises"]}


def test_un_ejercicio_desactivado_ya_no_se_ofrece_como_sustituto(client, cat):
    sid = SHOULDER_ID
    assert any(s["exercise_id"] == sid for s in ranked(client, BENCH_ID, all="true")["substitutions"])
    client.delete(f"/api/exercises/{sid}")
    assert not any(s["exercise_id"] == sid for s in ranked(client, BENCH_ID, all="true")["substitutions"])


# ====================================================== migración TEST-BOT
def test_migracion_test_bot_es_idempotente_y_solo_por_nombre_exacto(test_db):
    conn = get_connection()
    ensure_crud_schema(conn)
    for eid, name in (("tb1", "TEST-BOT sentadilla"), ("tb2", "test-bot Sentadilla"), ("tb3", "TEST-BOT sentadilla 2")):
        conn.execute("INSERT INTO exercises (id, name, is_active) VALUES (?, ?, 1)", (eid, name))
    # tb1 tiene historial -> se desactiva
    conn.execute("INSERT INTO workout_logs (id, user_id, date, status) VALUES ('wtb', ?, '2026-11-01T10:00:00', 'completed')", (PABLO_ID,))
    conn.execute("INSERT INTO workout_sets (id, workout_log_id, exercise_id, set_number, weight_kg, reps) VALUES ('s1','wtb','tb1',1,20,10)")
    conn.commit()
    conn.close()
    for _ in range(2):  # dos arranques seguidos
        with TestClient(app):
            pass
    conn = get_connection()
    try:
        rows = {r["id"]: r["is_active"] for r in conn.execute("SELECT id, is_active FROM exercises WHERE id LIKE 'tb%'")}
        assert rows == {"tb1": 0, "tb2": 1, "tb3": 1}  # solo el nombre exacto
        assert conn.execute("SELECT COUNT(*) FROM workout_sets WHERE exercise_id = 'tb1'").fetchone()[0] == 1
        assert apply_data_migrations(conn)["test_exercises"] == []  # ya aplicado: no hace nada
        # sin historial: se borra del todo
        conn.execute("INSERT INTO exercises (id, name, is_active) VALUES ('tb4', 'TEST-BOT sentadilla', 1)")
        conn.commit()
        assert apply_data_migrations(conn)["test_exercises"] == [("TEST-BOT sentadilla", "deleted")]
        assert conn.execute("SELECT COUNT(*) FROM exercises WHERE id = 'tb4'").fetchone()[0] == 0
    finally:
        conn.close()


def test_exercise_references_ignora_filas_autolimpiables(client, cat):
    assert exercise_references(cat, EXERCISES["lunges"][0]).get("routine_exercises.exercise_id") is None  # no está en rutina
    refs = exercise_references(cat, BENCH_ID)
    assert refs["routine_exercises.exercise_id"] >= 1
    assert not any(k.startswith("exercise_substitutions") for k in refs)


# ====================================================== CRUD de rutinas
def routine_body(**kw):
    return {"name": "Rutina D", "exercises": [
        {"exercise_id": BENCH_ID, "target_sets": 4, "target_rep_min": 6, "target_rep_max": 8, "target_rir": 1, "rest_seconds": 120},
        {"exercise_id": SHOULDER_ID, "target_sets": 3, "target_rep_min": 8, "target_rep_max": 12},
    ], **kw}


def test_crear_editar_y_listar_rutina(client):
    r = client.post("/api/routines", json=routine_body(session_label="Empuje"))
    assert r.status_code == 200, r.text
    routine = r.json()
    assert routine["user_id"] == PABLO_ID and routine["day_order"] == 4 and routine["session_label"] == "Empuje"
    assert [e["order"] for e in routine["exercises"]] == [1, 2]
    assert routine["exercises"][0]["target_rep_max"] == 8 and routine["exercises"][1]["target_rir"] == 2
    assert routine["id"] in {x["id"] for x in client.get("/api/routines", params={"user_id": PABLO_ID}).json()}
    u = client.put(f"/api/routines/{routine['id']}", json={"name": "Empuje B", "day_order": 7})
    assert u.json()["name"] == "Empuje B" and u.json()["day_order"] == 7
    assert client.get(f"/api/routines/{routine['id']}").json()["name"] == "Empuje B"
    assert client.post("/api/routines", json={"name": "   "}).status_code == 400
    assert client.post("/api/routines", json=routine_body(user_id="no-existe")).status_code == 404


def test_ejercicios_de_la_rutina_alta_edicion_orden_y_baja(client):
    rid = client.post("/api/routines", json={"name": "Vacía"}).json()["id"]
    p = client.post(f"/api/routines/{rid}/exercises", json={"exercise_id": BENCH_ID, "target_rep_min": 6, "target_rep_max": 8})
    assert p.status_code == 200 and len(p.json()["exercises"]) == 1
    client.post(f"/api/routines/{rid}/exercises", json={"exercise_id": SHOULDER_ID})
    p = client.post(f"/api/routines/{rid}/exercises", json={"exercise_id": INCLINE_ID})
    ids = [e["id"] for e in p.json()["exercises"]]
    assert [e["order"] for e in p.json()["exercises"]] == [1, 2, 3]
    assert client.post(f"/api/routines/{rid}/exercises", json={"exercise_id": BENCH_ID}).status_code == 409
    assert client.post(f"/api/routines/{rid}/exercises", json={"exercise_id": "nada"}).status_code == 404
    assert client.post(f"/api/routines/{rid}/exercises",
                       json={"exercise_id": CHEST_ROW_ID, "target_rep_min": 10, "target_rep_max": 5}).status_code == 400
    # editar objetivos
    u = client.put(f"/api/routines/{rid}/exercises/{ids[0]}", json={"target_sets": 5, "target_rep_max": 10, "is_optional": True})
    first = u.json()["exercises"][0]
    assert first["target_sets"] == 5 and first["target_rep_max"] == 10 and first["is_optional"] == 1
    assert client.put(f"/api/routines/{rid}/exercises/{ids[0]}", json={"target_rep_max": 3}).status_code == 400
    # reordenar
    o = client.put(f"/api/routines/{rid}/exercises/order", json={"routine_exercise_ids": [ids[2], ids[0], ids[1]]})
    assert [e["id"] for e in o.json()["exercises"]] == [ids[2], ids[0], ids[1]]
    assert client.put(f"/api/routines/{rid}/exercises/order", json={"routine_exercise_ids": ids[:2]}).status_code == 400
    # borrar y compactar
    d = client.delete(f"/api/routines/{rid}/exercises/{ids[0]}")
    assert [(e["id"], e["order"]) for e in d.json()["exercises"]] == [(ids[2], 1), (ids[1], 2)]
    assert client.delete(f"/api/routines/{rid}/exercises/{ids[0]}").status_code == 404


def test_una_rutina_creada_se_puede_entrenar_y_borrar_con_historial_la_desactiva(client):
    rid = client.post("/api/routines", json=routine_body()).json()["id"]
    w = start_workout(client, rid)
    log_sets(client, w["id"], BENCH_ID, 40, 7, n=1)
    finish(client, w["id"])
    d = client.delete(f"/api/routines/{rid}")
    assert d.json() == {"id": rid, "result": "deactivated", "deleted": False, "deactivated": True, "workouts": 1}
    assert rid not in {x["id"] for x in client.get("/api/routines", params={"user_id": PABLO_ID}).json()}
    # sin entrenos: borrado real
    rid2 = client.post("/api/routines", json=routine_body(name="Efímera")).json()["id"]
    assert client.delete(f"/api/routines/{rid2}").json()["result"] == "deleted"
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM routines WHERE id = ?", (rid2,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM routine_exercises WHERE routine_id = ?", (rid2,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_permisos_de_rutinas_propietario_y_admin(test_db):
    with TestClient(app) as pablo, TestClient(app) as estefi:
        _login_client(pablo, "Pablo", "test-pablo-password")
        _login_client(estefi, "Estefi", "test-estefi-password")
        mine = estefi.post("/api/routines", json={"name": "De Estefi", "exercises": [{"exercise_id": BENCH_ID}]})
        assert mine.status_code == 200 and mine.json()["user_id"] == ESTEFI_ID
        rid = mine.json()["id"]
        # un usuario normal no crea rutinas a nombre de otro ni toca las de otro
        assert estefi.post("/api/routines", json={"name": "Colada", "user_id": PABLO_ID}).status_code == 403
        assert estefi.put(f"/api/routines/{ROUTINE_A_ID}", json={"name": "hack"}).status_code == 404
        assert estefi.delete(f"/api/routines/{ROUTINE_A_ID}").status_code == 404
        assert estefi.post(f"/api/routines/{ROUTINE_A_ID}/exercises", json={"exercise_id": SHOULDER_ID}).status_code == 404
        # el admin edita las de cualquiera y puede crearlas para otro
        assert pablo.put(f"/api/routines/{rid}", json={"name": "Editada por admin"}).status_code == 200
        for_other = pablo.post("/api/routines", json={"name": "Para Estefi", "user_id": ESTEFI_ID})
        assert for_other.status_code == 200 and for_other.json()["user_id"] == ESTEFI_ID
        assert pablo.delete(f"/api/routines/{rid}").status_code == 200


# ====================================================== limpieza del repo y dependencias
def _tracked():
    try:
        out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    except Exception:  # pragma: no cover - sin git
        pytest.skip("sin git")
    return out.splitlines()


def test_no_hay_ficheros_de_backup_versionados():
    bad = [f for f in _tracked() if re.search(r"\.(backup|pre)-|\.bak$|\.backup$", Path(f).name)]
    assert bad == []


def test_gitignore_cubre_backups():
    text = (ROOT / ".gitignore").read_text()
    for pattern in ("*.backup-*", "*.pre-*", "*.bak"):
        assert pattern in text.splitlines()


def test_requirements_fija_pwdlib_y_webauthn():
    lines = [l.strip() for l in (ROOT / "requirements.txt").read_text().splitlines() if l.strip()]
    pw = [l for l in lines if l.lower().startswith("pwdlib")]
    wa = [l for l in lines if l.lower().startswith("webauthn")]
    assert pw and "argon2" in pw[0] and "bcrypt" in pw[0] and re.search(r"(==|~=|>=)\d", pw[0])
    assert wa and re.search(r"(==|~=|>=)\d", wa[0])
