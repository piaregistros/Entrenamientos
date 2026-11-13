"""Fase 11: gráficas de 1RM/volumen, equilibrio y calentamiento sugerido."""
from datetime import date, timedelta

from fastapi.testclient import TestClient

from conftest import BENCH_ID, ESTEFI_ID, EXERCISES, PABLO_ID
from app.main import app
from app.database import get_connection
from app.charts import (
    epley,
    effective_contributions,
    muscle_groups_from_text,
    session_point,
    week_start_of,
)
from app.warmup import BAR_KG, is_isolation, suggest_warmup
from test_fase6_doble_progresion import _complete


LEG_PRESS_ID = EXERCISES["leg_press"][0]
PLANK_ID = EXERCISES["plank"][0]
ROW_ID = EXERCISES["chest_row"][0]


def S(weight, reps):
    return {"weight_kg": weight, "reps": reps}


def bench_ex(**extra):
    data = {
        "name": "Press banca plano",
        "equipment": "Barra",
        "exercise_type": "compuesto",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    }
    data.update(extra)
    return data


def curl_ex(**extra):
    data = {
        "name": "Curl de bíceps en máquina",
        "equipment": "Máquina",
        "exercise_type": "aislamiento",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
        "category": "brazos",
    }
    data.update(extra)
    return data


def _dated(wid, day):
    stamp = day if isinstance(day, str) else day.isoformat()
    conn = get_connection()
    try:
        conn.execute("UPDATE workout_logs SET date = ? WHERE id = ?", (stamp, wid))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ 1RM / grupos
def test_epley_basico():
    assert epley(100, 10) == 133.3
    assert epley(80, 1) == 80.0
    assert epley(0, 10) == 0.0
    assert epley(100, 0) == 0.0


def test_grupos_musculares_compuestos_y_secundarios():
    assert muscle_groups_from_text("Pectoral") == ["Pecho"]
    assert muscle_groups_from_text("Cuádriceps y glúteos") == ["Cuádriceps", "Glúteos"]
    assert muscle_groups_from_text("Deltoides posterior y espalda alta") == [
        "Deltoides posterior", "Espalda",
    ]
    prim_sec = effective_contributions("Pectoral", '["Tríceps", "Deltoides"]')
    assert ("Pecho", 1.0) in prim_sec
    assert ("Tríceps", 0.5) in prim_sec
    assert ("Hombros", 0.5) in prim_sec


def test_session_point_ignora_e1rm_en_tiempo():
    pt = session_point([S(0, 40), S(0, 45)], "time", False, "w1", date(2026, 1, 6))
    assert pt["best_time_s"] == 45
    assert pt["e1rm"] is None
    assert pt["volume_kg"] == 0.0


def test_session_point_e1rm_y_volumen():
    pt = session_point([S(50, 8), S(50, 8), S(40, 10)], "reps", False, "w1", date(2026, 1, 6))
    assert pt["top_weight_kg"] == 50
    assert pt["e1rm"] == epley(50, 8)
    assert pt["volume_kg"] == 50 * 8 + 50 * 8 + 40 * 10
    assert pt["working_sets"] == 3


# ------------------------------------------------------------------ calentamiento (puro)
def test_compuesto_barra_tres_series_redondeadas():
    sets = suggest_warmup(bench_ex(), 100)
    assert [s["percent"] for s in sets] == [40, 60, 80]
    assert [s["reps"] for s in sets] == [8, 5, 3]
    assert sets[0]["weight_kg"] == 40.0
    assert sets[1]["weight_kg"] == 60.0
    assert sets[2]["weight_kg"] == 80.0
    assert "80 %" in sets[2]["label"]


def test_compuesto_barra_nunca_por_debajo_de_la_barra():
    sets = suggest_warmup(bench_ex(), 50)
    # 40 % de 50 = 20 → barra. 50 kg < 40: plan reducido (50/70).
    # 50 está en "ligero" (< 40? no, 50 >= 40), so 40/60/80
    # 40% = 20, 60% = 30, 80% = 40. All >= bar, 40 is 80% of 50 so skipped (>= 0.9? 40/50=0.8, kept)
    assert sets[0]["weight_kg"] >= BAR_KG
    assert all(s["weight_kg"] < 50 * 0.9 for s in sets)


def test_aislado_menos_series():
    assert is_isolation(curl_ex()) is True
    sets = suggest_warmup(curl_ex(), 30)
    assert [s["percent"] for s in sets] == [50, 70]
    assert [s["reps"] for s in sets] == [8, 5]
    assert sets[0]["weight_kg"] == 15.0
    assert sets[1]["weight_kg"] == 20.0  # 21 → 20 al paso de 2.5? 30*0.7=21, round_to_step 21/2.5=8.4→8*2.5=20


def test_isometrico_y_peso_corporal_sin_calentamiento():
    plank = {"name": "Plancha", "equipment": "Peso corporal", "measure_type": "time", "weight_increment_kg": 0}
    assert suggest_warmup(plank, 0) == []
    pullup = {"name": "Dominadas", "equipment": "Peso corporal", "measure_type": "bodyweight", "weight_increment_kg": 0}
    assert suggest_warmup(pullup, 0) == []


def test_peso_muy_ligero_sin_calentamiento():
    assert suggest_warmup(curl_ex(), 8) == []
    assert suggest_warmup(curl_ex(), 0) == []


def test_carga_ligera_menos_series_aunque_sea_compuesto():
    sets = suggest_warmup(bench_ex(), 30)
    # 50 % = 15 kg → barra (20). 70 % = 21 → 20, se omite el duplicado.
    assert len(sets) == 1
    assert sets[0]["percent"] == 50
    assert sets[0]["weight_kg"] == BAR_KG
    assert "Barra" in sets[0]["label"]


def test_redondeo_al_paso_de_mancuerna():
    ex = {
        "name": "Press de hombro con mancuernas",
        "equipment": "Mancuernas",
        "exercise_type": "compuesto",
        "measure_type": "reps",
        "weight_increment_kg": 2.0,
    }
    sets = suggest_warmup(ex, 22)
    # 22 < 40 → 50/70. 11 → 12 (paso 2), 15.4 → 16.
    assert sets[0]["weight_kg"] == 12.0
    assert sets[1]["weight_kg"] == 16.0


# ------------------------------------------------------------------ API
def test_historial_de_ejercicio_con_rango(client):
    today = date.today()
    wid_old = _complete(client, [(BENCH_ID, 40, 8, 2)] * 3)
    _dated(wid_old, today - timedelta(days=40))
    wid_new = _complete(client, [(BENCH_ID, 50, 8, 2)] * 3)
    _dated(wid_new, today - timedelta(days=3))
    # Un calentamiento no debe entrar en el 1RM ni en el volumen
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO workout_sets (id, workout_log_id, exercise_id, set_number, weight_kg, reps, rir, is_warmup)
               VALUES ('wu-1', ?, ?, 0, 20, 10, NULL, 1)""",
            (wid_new, BENCH_ID),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get(f"/api/progress/exercise/{BENCH_ID}", params={"user_id": PABLO_ID, "range": "4w"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["exercise_id"] == BENCH_ID
    assert data["measure_type"] == "reps" or data["unit"] == "kg"
    assert data["range"] == "4w"
    assert data["count"] == 1
    ses = data["sessions"][0]
    assert ses["top_weight_kg"] == 50
    assert ses["e1rm"] == epley(50, 8)
    assert ses["volume_kg"] == 50 * 8 * 3
    assert ses["working_sets"] == 3
    assert ses["is_deload"] is False

    all_r = client.get(f"/api/progress/exercise/{BENCH_ID}", params={"user_id": PABLO_ID, "range": "all"})
    assert all_r.status_code == 200
    payload = all_r.json()
    # Puede haber un entreno sembrado al arrancar (banca de Pablo); lo que importa
    # es que los dos que acabamos de crear están y el calentamiento no inventa una sesión.
    by_id = {s["workout_id"]: s for s in payload["sessions"]}
    assert payload["count"] == len(payload["sessions"]) >= 2
    assert by_id[wid_old]["top_weight_kg"] == 40
    assert by_id[wid_new]["top_weight_kg"] == 50
    assert by_id[wid_new]["volume_kg"] == 50 * 8 * 3
    assert payload["sessions"][-1]["workout_id"] == wid_new


def test_historial_isometrico_usa_el_mejor_tiempo(client):
    from conftest import ROUTINE_B_ID
    today = date.today()
    wid = _complete(client, [(PLANK_ID, 0, 40, 2), (PLANK_ID, 0, 45, 2)], routine_id=ROUTINE_B_ID)
    _dated(wid, today)
    r = client.get(f"/api/progress/exercise/{PLANK_ID}", params={"user_id": PABLO_ID, "range": "4w"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["measure_type"] == "time" or data["unit"] == "s"
    assert data["count"] == 1
    assert data["sessions"][0]["best_time_s"] == 45
    assert data["sessions"][0]["e1rm"] is None


def test_volumen_semanal_y_equilibrio(client):
    today = date.today()
    monday = week_start_of(today)
    # Esta semana: banca (pecho, 3 series) + remo (espalda, 3)
    wid = _complete(client, [(BENCH_ID, 50, 8, 2)] * 3 + [(ROW_ID, 40, 8, 2)] * 3)
    _dated(wid, monday + timedelta(days=1))
    # Semana anterior: solo banca
    wid2 = _complete(client, [(BENCH_ID, 50, 8, 2)] * 3)
    _dated(wid2, monday - timedelta(days=6))
    # Calentamiento esta semana: no cuenta
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO workout_sets (id, workout_log_id, exercise_id, set_number, weight_kg, reps, rir, is_warmup)
               VALUES ('wu-vol', ?, ?, 99, 20, 10, NULL, 1)""",
            (wid, BENCH_ID),
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/progress/volume", params={"user_id": PABLO_ID, "weeks": 8})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["weeks"] == 8
    assert data["reference"] == {"min_sets": 10, "max_sets": 20}
    assert "Pecho" in data["groups"]
    assert "Espalda" in data["groups"]
    assert len(data["items"]) == 8
    # última semana = current monday
    last = data["items"][-1]
    assert last["week_start"] == monday.isoformat()
    assert last["groups"]["Pecho"] == 3
    assert last["groups"]["Espalda"] == 3
    prev = data["items"][-2]
    assert prev["groups"]["Pecho"] == 3
    assert prev["groups"].get("Espalda", 0) == 0
    assert data["balance"]["push"] > 0
    assert data["balance"]["pull"] > 0
    assert "chest" in data["heat"]
    assert "lats" in data["heat"]


def test_volumen_clampa_semanas(client):
    r = client.get("/api/progress/volume", params={"user_id": PABLO_ID, "weeks": 99})
    assert r.status_code == 200
    assert r.json()["weeks"] == 12
    r = client.get("/api/progress/volume", params={"user_id": PABLO_ID, "weeks": 3})
    assert r.json()["weeks"] == 8


def test_warmup_endpoint(client):
    r = client.get("/api/progress/warmup", params={"user_id": PABLO_ID, "exercise_id": BENCH_ID, "weight_kg": 100})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == 3
    assert data["sets"][0]["weight_kg"] == 40
    assert data["sets"][-1]["weight_kg"] == 80
    none = client.get("/api/progress/warmup", params={"user_id": PABLO_ID, "exercise_id": PLANK_ID, "weight_kg": 0})
    assert none.status_code == 200
    assert none.json()["count"] == 0


def test_ejercicio_inexistente_es_404(client):
    r = client.get("/api/progress/exercise/no-existe", params={"user_id": PABLO_ID})
    assert r.status_code == 404
    r = client.get("/api/progress/warmup", params={"user_id": PABLO_ID, "exercise_id": "no-existe", "weight_kg": 50})
    assert r.status_code == 404


def test_estefi_no_ve_las_graficas_de_pablo(client_estefi, client_pablo):
    today = date.today()
    wid = _complete(client_pablo, [(BENCH_ID, 60, 8, 2)] * 3)
    _dated(wid, today)
    r = client_estefi.get(f"/api/progress/exercise/{BENCH_ID}", params={"user_id": PABLO_ID, "range": "4w"})
    assert r.status_code in (401, 403, 404)
    own = client_estefi.get(f"/api/progress/exercise/{BENCH_ID}", params={"user_id": ESTEFI_ID, "range": "all"})
    assert own.status_code == 200
    assert own.json()["count"] == 0
    vol = client_estefi.get("/api/progress/volume", params={"user_id": PABLO_ID})
    assert vol.status_code in (401, 403, 404)
    own_vol = client_estefi.get("/api/progress/volume", params={"user_id": ESTEFI_ID})
    assert own_vol.status_code == 200
    assert own_vol.json()["items"][-1]["groups"].get("Pecho", 0) == 0


def test_sin_sesion_es_401():
    with TestClient(app) as anon:
        assert anon.get(f"/api/progress/exercise/{BENCH_ID}", params={"user_id": PABLO_ID}).status_code == 401
        assert anon.get("/api/progress/volume", params={"user_id": PABLO_ID}).status_code == 401
        assert anon.get("/api/progress/warmup", params={"user_id": PABLO_ID, "exercise_id": BENCH_ID, "weight_kg": 50}).status_code == 401
