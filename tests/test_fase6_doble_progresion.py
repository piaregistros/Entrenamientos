"""Fase 6: doble progresión única (apply_progression == /recommendations), por tipo de ejercicio."""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import (
    BENCH_ID,
    EXERCISES,
    PABLO_ID,
    ROUTINE_A_ID,
    ROUTINE_B_ID,
)
from app.database import get_connection
from app.progress_routes import init_progress_db, rebuild_all_progress, recompute_exercise_progress
from app.progression import (
    DEFAULT_TIME_RANGE,
    default_increment,
    deload_weight,
    equipment_class,
    fmt_num,
    infer_measure_type,
    next_target,
    resolve_increment,
)
from app.progression_db import ensure_progression_schema

PLANK_ID = EXERCISES["plank"][0]
LEG_PRESS_ID = EXERCISES["leg_press"][0]
LATERAL_ID = EXERCISES["lateral_raise"][0]
SHOULDER_ID = EXERCISES["shoulder_press"][0]


# ------------------------------------------------------------------ helpers
def S(weight, reps, rir=2, warmup=False):
    return {"weight_kg": weight, "reps": reps, "rir": rir, "is_warmup": warmup}


def ex(name="Press banca plano", equipment="Barra", exercise_type="compuesto", measure="reps",
       inc=2.5, rep_min=8, rep_max=12, rir=2):
    return {
        "name": name, "equipment": equipment, "exercise_type": exercise_type, "measure_type": measure,
        "weight_increment_kg": inc, "rep_min": rep_min, "rep_max": rep_max, "rir_target": rir,
    }


# ------------------------------------------------------------ reglas de reps
def test_sin_historial_es_start():
    r = next_target(ex(), [])
    assert r["kind"] == "start" and r["weight_kg"] is None and r["reps"] == 8


def test_dentro_del_rango_sube_una_rep_por_serie_y_mantiene_peso():
    r = next_target(ex(), [[S(50, 9), S(50, 9), S(50, 10)]])
    assert r["kind"] == "add_reps"
    assert r["weight_kg"] == 50 and r["reps"] == 10        # la serie más floja manda: 9 + 1
    assert "Intenta 1 rep más por serie" in r["reason"]


def test_maximo_en_todas_las_series_sube_peso_y_vuelve_al_minimo():
    r = next_target(ex(), [[S(50, 12), S(50, 12), S(50, 12)]])
    assert r["kind"] == "increase_weight"
    assert r["weight_kg"] == 52.5 and r["reps"] == 8
    assert r["reason"].startswith("Llegaste a 12 reps en todas las series → +2,5 kg")


def test_una_sola_serie_por_debajo_del_maximo_no_sube_peso():
    r = next_target(ex(), [[S(50, 12), S(50, 12), S(50, 11)]])
    assert r["kind"] == "add_reps" and r["weight_kg"] == 50 and r["reps"] == 12


def test_maximo_con_rir_por_debajo_del_objetivo_mantiene():
    r = next_target(ex(), [[S(50, 12, 2), S(50, 12, 2), S(50, 12, 0)]])
    assert r["kind"] == "maintain_weight" and r["weight_kg"] == 50
    assert "RIR" in r["reason"]


def test_rir_sin_registrar_no_bloquea_la_subida():
    r = next_target(ex(), [[S(50, 12, None), S(50, 12, None)]])
    assert r["kind"] == "increase_weight"


def test_fallo_mantiene_la_carga():
    r = next_target(ex(), [[S(50, 8), S(50, 7), S(50, 6)]])
    assert r["kind"] == "maintain_weight" and r["weight_kg"] == 50 and r["reps"] == 8
    assert r["fail_streak"] == 1
    assert "Mantén 50 kg" in r["reason"]


def test_dos_fallos_seguidos_hacen_deload_redondeado_al_paso():
    r = next_target(ex(), [[S(100, 6)] * 3, [S(100, 7)] * 3])
    assert r["kind"] == "deload" and r["fail_streak"] == 2
    assert r["weight_kg"] == 90.0 and r["reps"] == 8       # -10 % = 90
    r2 = next_target(ex(), [[S(52.5, 6)] * 3, [S(52.5, 5)] * 3])
    assert r2["weight_kg"] == 47.5                          # 47.25 -> paso 2.5


def test_un_fallo_tras_una_sesion_buena_no_es_deload():
    r = next_target(ex(), [[S(100, 6)] * 3, [S(100, 10)] * 3])
    assert r["kind"] == "maintain_weight" and r["fail_streak"] == 1


def test_fallo_previo_pero_ultima_sesion_buena_resetea_racha():
    r = next_target(ex(), [[S(100, 9)] * 3, [S(100, 6)] * 3])
    assert r["kind"] == "add_reps" and r["fail_streak"] == 0


def test_calentamientos_y_series_ligeras_no_cuentan():
    sets = [S(20, 15, warmup=True), S(50, 12), S(50, 12), S(40, 6)]   # back-off de 40 kg ignorado
    r = next_target(ex(), [sets])
    assert r["kind"] == "increase_weight" and r["weight_kg"] == 52.5


def test_series_con_cero_reps_se_ignoran():
    assert next_target(ex(), [[S(50, 0)]])["kind"] == "start"


def test_deload_nunca_deja_la_misma_carga():
    assert deload_weight(2.5, 2.5) == 0.0
    assert deload_weight(20, 2.5) == 17.5
    assert deload_weight(10, 1) == 9


def test_formato_espanol_de_numeros():
    assert fmt_num(2.5) == "2,5" and fmt_num(2.0) == "2" and fmt_num(52.5) == "52,5"


# --------------------------------------------------------- incrementos por equipo
@pytest.mark.parametrize(
    "equipment,etype,measure,expected",
    [
        ("Barra", "compuesto", "reps", 2.5),
        ("Barra o máquina", "compuesto", "reps", 2.5),
        ("Mancuernas", "compuesto", "reps", 2.0),
        ("Mancuerna", "compuesto", "reps", 2.0),
        ("Mancuernas", "aislamiento", "reps", 1.0),
        ("Mancuernas o peso corporal", "compuesto", "reps", 2.0),
        ("Máquina", "compuesto", "reps", 5.0),
        ("Máquina o banco", "compuesto", "reps", 5.0),
        ("Máquina", "aislamiento", "reps", 2.5),
        ("Polea", "compuesto", "reps", 5.0),
        ("Polea", "aislamiento", "reps", 2.5),
        ("Polea", "core", "reps", 2.5),
        ("Peso corporal", "core", "bodyweight", 0.0),
        ("Peso corporal", "compuesto", "bodyweight", 2.5),
        ("Peso corporal", "core", "time", 0.0),
        ("", None, "reps", 2.5),
        ("Kettlebell", "compuesto", "reps", 2.0),
    ],
)
def test_incremento_por_defecto_segun_equipo(equipment, etype, measure, expected):
    assert default_increment(equipment, etype, measure) == expected


def test_resolve_increment_prefiere_el_valor_del_ejercicio():
    assert resolve_increment(ex(equipment="Barra", inc=1.25)) == 1.25


@pytest.mark.parametrize("stored", [None, 0, 0.0])
def test_sin_incremento_configurado_usa_el_del_equipo(stored):
    cfg = ex(name="Press de hombro mancuernas", equipment="Mancuernas", inc=stored)
    assert resolve_increment(cfg) == 2.0
    r = next_target(cfg, [[S(20, 12)] * 3])
    assert r["kind"] == "increase_weight" and r["weight_kg"] == 22.0
    assert "+2 kg" in r["reason"]


def test_mancuernas_aislamiento_sube_1_kg():
    cfg = ex(name="Elevaciones laterales", equipment="Mancuernas", exercise_type="aislamiento",
             inc=None, rep_min=12, rep_max=15)
    r = next_target(cfg, [[S(10, 15)] * 3])
    assert r["weight_kg"] == 11.0 and r["reps"] == 12


def test_maquina_de_placas_sube_5_kg_en_compuesto():
    cfg = ex(name="Prensa de piernas", equipment="Máquina", inc=None, rep_min=8, rep_max=10)
    r = next_target(cfg, [[S(100, 10)] * 3])
    assert r["weight_kg"] == 105 and "+5 kg" in r["reason"]


def test_incremento_curado_de_0_en_ejercicio_con_carga_no_lo_bloquea():
    cfg = ex(name="Face pull", equipment="Polea", exercise_type="aislamiento", inc=0)
    r = next_target(cfg, [[S(20, 12)] * 3])
    assert r["kind"] == "increase_weight" and r["weight_kg"] == 22.5


# ------------------------------------------------------------------ isométricos
def plank(inc=0.0, rep_min=30, rep_max=60):
    return ex(name="Plancha", equipment="Peso corporal", exercise_type="core", measure="time",
              inc=inc, rep_min=rep_min, rep_max=rep_max)


def test_plancha_progresa_por_tiempo_5_s():
    r = next_target(plank(), [[S(0, 30, None), S(0, 32, None)]])
    assert r["kind"] == "add_time" and r["reps"] == 35 and r["unit"] == "s"
    assert "35 s" in r["reason"]


def test_plancha_en_el_maximo_sin_lastre_propone_serie_o_variante():
    r = next_target(plank(), [[S(0, 60, None)] * 2])
    assert r["kind"] == "maintain_weight" and r["weight_kg"] == 0
    assert "variante más difícil" in r["reason"] and "kg" not in r["reason"]


def test_plancha_en_el_maximo_con_lastre_configurado_sube_lastre():
    r = next_target(plank(inc=2.5), [[S(0, 60, None)] * 2])
    assert r["kind"] == "increase_weight" and r["weight_kg"] == 2.5 and r["reps"] == 30
    assert "lastre" in r["reason"]
    r2 = next_target(plank(inc=2.5), [[S(5, 60, None)] * 2])
    assert r2["weight_kg"] == 7.5


def test_plancha_no_llega_al_minimo_mantiene_y_dos_veces_hace_deload_de_tiempo():
    r = next_target(plank(), [[S(0, 25, None)] * 2])
    assert r["kind"] == "maintain_weight" and r["reps"] == 30 and r["fail_streak"] == 1
    r2 = next_target(plank(), [[S(0, 25, None)] * 2, [S(0, 20, None)] * 2])
    assert r2["kind"] == "deload" and r2["reps"] == 30


def test_tiempo_con_rango_de_reps_heredado_usa_el_rango_de_tiempo():
    cfg = plank(rep_min=10, rep_max=15)          # el generador de rutinas pone 10-15
    r = next_target(cfg, [[S(0, 30, None)] * 2])
    assert r["reps"] == 35
    assert next_target(cfg, [])["reps"] == DEFAULT_TIME_RANGE[0]


@pytest.mark.parametrize(
    "name,equipment,expected",
    [
        ("Plancha", "Peso corporal", "time"),
        ("Plancha lateral", "Peso corporal", "time"),
        ("Sentadilla isométrica", "Peso corporal", "time"),
        ("Wall sit", "", "time"),
        ("Hollow hold", "Peso corporal", "time"),
        ("Elevación de rodillas", "Peso corporal", "bodyweight"),
        ("Dominadas", "Peso corporal", "bodyweight"),
        ("Zancadas", "Mancuernas o peso corporal", "reps"),
        ("Press banca plano", "Barra", "reps"),
        ("Pallof press", "Polea", "reps"),
    ],
)
def test_inferencia_de_measure_type_no_depende_de_llamarse_plancha(name, equipment, expected):
    assert infer_measure_type(name, equipment) == expected


def test_isometrico_sin_measure_type_guardado_se_infiere_por_nombre():
    cfg = ex(name="Plancha lateral", equipment="Peso corporal", exercise_type="core", measure=None,
             inc=None, rep_min=None, rep_max=None)
    r = next_target(cfg, [[S(0, 30, None)] * 2])
    assert r["measure_type"] == "time" and r["kind"] == "add_time" and r["reps"] == 35


# ------------------------------------------------------------------ peso corporal
def knees(inc=0.0):
    return ex(name="Elevación de rodillas", equipment="Peso corporal", exercise_type="core",
              measure="bodyweight", inc=inc, rep_min=10, rep_max=15)


def test_peso_corporal_sube_reps_hasta_el_maximo():
    r = next_target(knees(), [[S(0, 12, 1), S(0, 12, 1)]])
    assert r["kind"] == "add_reps" and r["reps"] == 13 and r["weight_kg"] == 0
    assert "peso corporal" in r["reason"]


def test_peso_corporal_en_el_maximo_sin_lastre_no_inventa_kilos():
    r = next_target(knees(), [[S(0, 15)] * 3])
    assert r["kind"] == "maintain_weight" and "kg" not in r["reason"]


def test_peso_corporal_en_el_maximo_con_lastre_empieza_a_lastrar():
    pull = ex(name="Dominadas", equipment="Peso corporal", exercise_type="compuesto", measure="bodyweight",
              inc=None, rep_min=6, rep_max=10)
    r = next_target(pull, [[S(0, 10)] * 3])
    assert r["kind"] == "increase_weight" and r["weight_kg"] == 2.5 and r["reps"] == 6
    assert "lastre" in r["reason"]
    r2 = next_target(pull, [[S(2.5, 10)] * 3])
    assert r2["weight_kg"] == 5.0


def test_peso_corporal_dos_fallos_no_baja_kilos_inexistentes():
    r = next_target(knees(), [[S(0, 6)] * 2, [S(0, 7)] * 2])
    assert r["kind"] == "deload" and r["weight_kg"] == 0


def test_zancadas_con_mancuernas_o_peso_corporal_empiezan_sin_peso_y_pasan_a_mancuernas():
    cfg = ex(name="Zancadas", equipment="Mancuernas o peso corporal", inc=2.0, rep_min=8, rep_max=12)
    r = next_target(cfg, [[S(0, 12)] * 3])
    assert r["weight_kg"] == 2.0 and r["reps"] == 8


# ------------------------------------------------------- esquema y catálogo (59)
def _catalog_rows():
    from app.seed_exercises_v2 import EXERCISES as CATALOG
    return CATALOG


def test_catalogo_tiene_59_ejercicios():
    assert len(_catalog_rows()) == 59


def _load_catalog_into(conn):
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(exercises)")}
    if "exercise_type" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN exercise_type TEXT")
    import uuid
    existing = {r["name"].lower() for r in conn.execute("SELECT name FROM exercises")}
    for e in _catalog_rows():
        if e["name"].lower() in existing:
            continue
        conn.execute(
            "INSERT INTO exercises (id, name, target_muscle, category, equipment, exercise_type, is_active) "
            "VALUES (?,?,?,?,?,?,1)",
            (e.get("id") or str(uuid.uuid4()), e["name"], e["target_muscle"], e["category"], e["equipment"], e["exercise_type"]),
        )
    conn.commit()


def test_los_59_ejercicios_quedan_con_measure_type_e_incremento(client):
    conn = get_connection()
    try:
        _load_catalog_into(conn)
        ensure_progression_schema(conn)
        rows = {r["name"]: dict(r) for r in conn.execute("SELECT * FROM exercises")}
    finally:
        conn.close()
    for e in _catalog_rows():
        row = rows[e["name"]]
        assert row["measure_type"] in ("reps", "time", "bodyweight"), e["name"]
        assert row["weight_increment_kg"] is not None, e["name"]
        if row["measure_type"] == "reps":
            assert float(row["weight_increment_kg"]) > 0, e["name"]
    assert rows["Plancha"]["measure_type"] == "time"
    assert rows["Elevación de rodillas"]["measure_type"] == "bodyweight"
    assert sum(1 for r in rows.values() if r["measure_type"] == "time") == 1
    assert rows["Press banca con mancuernas"]["weight_increment_kg"] == 2.0
    assert rows["Elevaciones laterales con mancuernas"]["weight_increment_kg"] == 1.0
    assert rows["Hack squat"]["weight_increment_kg"] == 5.0
    assert rows["Crunch en polea"]["weight_increment_kg"] == 2.5
    assert rows["Sentadilla libre"]["weight_increment_kg"] == 2.5


def test_el_rellenado_es_idempotente_y_no_pisa_valores_existentes(client):
    conn = get_connection()
    try:
        ensure_progression_schema(conn)
        conn.execute("UPDATE exercises SET weight_increment_kg = 1.25 WHERE id = ?", (BENCH_ID,))
        conn.execute("UPDATE exercises SET measure_type = 'bodyweight' WHERE id = ?", (LEG_PRESS_ID,))
        conn.commit()
        first = ensure_progression_schema(conn)
        second = ensure_progression_schema(conn)
        assert first == {"measure_type": 0, "weight_increment_kg": 0} == second
        assert conn.execute("SELECT weight_increment_kg FROM exercises WHERE id=?", (BENCH_ID,)).fetchone()[0] == 1.25
        assert conn.execute("SELECT measure_type FROM exercises WHERE id=?", (LEG_PRESS_ID,)).fetchone()[0] == "bodyweight"
        # los incrementos curados no se tocan
        assert conn.execute("SELECT weight_increment_kg FROM exercises WHERE id=?", (EXERCISES["shoulder_press"][0],)).fetchone()[0] == 2.0
    finally:
        conn.close()


def test_el_arranque_aplica_el_esquema_de_progresion(client):
    conn = get_connection()
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(exercises)")}
        pcols = {r["name"] for r in conn.execute("PRAGMA table_info(exercise_progress)")}
    finally:
        conn.close()
    assert "measure_type" in cols
    assert {"next_reps", "kind", "fail_streak", "measure_type", "source_workout_id"} <= pcols


# ------------------------------------------------ integración (BD + API + coherencia)
_CLOCK = {"n": 0}


def _complete(client, sets, routine_id=ROUTINE_A_ID, deload=False):
    """sets: (exercise_id, kg, reps, rir). Devuelve workout_id. Cada entreno tiene fecha distinta y creciente
    (las fechas tienen precisión de segundos; así el orden no depende de la velocidad del test)."""
    r = client.post("/api/workouts", json={"user_id": PABLO_ID, "routine_id": routine_id})
    assert r.status_code == 200, r.text
    wid = r.json()["id"]
    _CLOCK["n"] += 1
    stamp = (datetime.now(timezone.utc) + timedelta(minutes=_CLOCK["n"])).isoformat(timespec="seconds")
    conn = get_connection()
    try:
        conn.execute("UPDATE workout_logs SET date = ? WHERE id = ?", (stamp, wid))
        conn.commit()
    finally:
        conn.close()
    counters = {}
    for exercise, kg, reps, rir in sets:
        counters[exercise] = counters.get(exercise, 0) + 1
        s = client.post(
            f"/api/workouts/{wid}/sets",
            params={"user_id": PABLO_ID},
            json={"exercise_id": exercise, "set_number": counters[exercise], "weight_kg": kg, "reps": reps, "rir": rir},
        )
        assert s.status_code == 200, s.text
    body = {"status": "completed", "duration_minutes": 50}
    if deload:
        body["is_deload"] = 1
    r = client.put(f"/api/workouts/{wid}", params={"user_id": PABLO_ID}, json=body)
    assert r.status_code == 200, r.text
    return wid


def _progress(user_id=PABLO_ID):
    conn = get_connection()
    try:
        return {r["exercise_id"]: dict(r) for r in conn.execute("SELECT * FROM exercise_progress WHERE user_id=?", (user_id,))}
    finally:
        conn.close()


def _recs(client, routine_id=ROUTINE_A_ID):
    data = client.get(f"/api/routines/{routine_id}/recommendations", params={"user_id": PABLO_ID}).json()
    return {r["exercise_id"]: r for r in data["recommendations"]}


def test_apply_progression_y_recommendations_dan_lo_mismo(client):
    init_progress_db()
    leg_curl = EXERCISES["leg_curl"][0]
    _complete(client, [
        (BENCH_ID, 50, 8, 2), (BENCH_ID, 50, 8, 2), (BENCH_ID, 50, 8, 2),            # 6-8: máximo -> sube
        (LEG_PRESS_ID, 100, 9, 2), (LEG_PRESS_ID, 100, 9, 2), (LEG_PRESS_ID, 100, 8, 2),  # 8-10: +1 rep
        (leg_curl, 40, 6, 2), (leg_curl, 40, 7, 2),                                    # 10-12: fallo
        (LATERAL_ID, 10, 15, 0), (LATERAL_ID, 10, 15, 2),                              # máximo con RIR 0
    ])
    progress, recs = _progress(), _recs(client)
    assert progress[BENCH_ID]["next_weight_kg"] == 52.5 == recs[BENCH_ID]["recommended_weight_kg"]
    assert progress[BENCH_ID]["next_reps"] == 6 == recs[BENCH_ID]["recommended_rep_target"]
    assert recs[BENCH_ID]["recommendation"] == "increase_weight" == progress[BENCH_ID]["kind"]
    assert progress[LEG_PRESS_ID]["next_weight_kg"] == 100 and progress[LEG_PRESS_ID]["next_reps"] == 9
    assert recs[LEG_PRESS_ID]["recommendation"] == "add_reps"
    assert progress[leg_curl]["kind"] == "maintain_weight" and progress[leg_curl]["fail_streak"] == 1
    assert progress[LATERAL_ID]["kind"] == "maintain_weight" and progress[LATERAL_ID]["next_weight_kg"] == 10
    for eid, rec in recs.items():
        if eid in progress:
            assert progress[eid]["next_weight_kg"] == rec["recommended_weight_kg"], eid
            assert progress[eid]["next_reps"] == rec["recommended_rep_target"], eid
            assert progress[eid]["reason"] == rec["reason"], eid


def test_el_texto_pedido_aparece_en_el_endpoint(client):
    init_progress_db()
    _complete(client, [(LEG_PRESS_ID, 100, 10, 2)] * 3)
    reason = _recs(client)[LEG_PRESS_ID]["reason"]
    assert reason.startswith("Llegaste a 10 reps en todas las series → +5 kg")
    _complete(client, [(LEG_PRESS_ID, 105, 8, 2)] * 3)
    assert "Intenta 1 rep más por serie" in _recs(client)[LEG_PRESS_ID]["reason"]


def test_recommendations_incluye_tipo_unidad_e_incremento(client):
    init_progress_db()
    recs = _recs(client, ROUTINE_B_ID)
    assert recs[PLANK_ID]["measure_type"] == "time" and recs[PLANK_ID]["unit"] == "s"
    assert recs[SHOULDER_ID]["increment_kg"] == 2.0
    assert recs[LEG_PRESS_ID]["recommendation"] == "start"


def test_plancha_progresa_por_tiempo_en_la_api(client):
    init_progress_db()
    _complete(client, [(PLANK_ID, 0, 40, None), (PLANK_ID, 0, 40, None)], routine_id=ROUTINE_B_ID)
    p = _progress()[PLANK_ID]
    assert p["kind"] == "add_time" and p["next_reps"] == 45 and p["measure_type"] == "time"
    rec = _recs(client, ROUTINE_B_ID)[PLANK_ID]
    assert rec["recommended_rep_target"] == 45 and rec["recommendation"] == "add_reps"
    assert "45 s" in rec["reason"]


def test_ejercicio_isometrico_personalizado_progresa_por_tiempo(client):
    init_progress_db()
    r = client.post("/api/exercises", json={"name": "Plancha lateral", "equipment": "Peso corporal", "category": "core"})
    assert r.status_code == 200, r.text
    assert r.json()["measure_type"] == "time" and r.json()["weight_increment_kg"] == 0.0
    eid = r.json()["id"]
    _complete(client, [(eid, 0, 30, None), (eid, 0, 30, None)])
    p = _progress()[eid]
    assert p["kind"] == "add_time" and p["next_reps"] == 35


def test_ejercicio_personalizado_con_mancuernas_no_hereda_2_5_kg(client):
    r = client.post("/api/exercises", json={"name": "Curl concentrado", "equipment": "Mancuerna", "category": "brazos"})
    assert r.status_code == 200, r.text
    assert r.json()["weight_increment_kg"] == 2.0 and r.json()["measure_type"] == "reps"
    r = client.post("/api/exercises", json={"name": "Remo con barra T", "equipment": "Barra", "weight_increment_kg": 1.25})
    assert r.json()["weight_increment_kg"] == 1.25


def test_un_entreno_de_deload_no_mueve_la_progresion_ni_las_recomendaciones(client):
    init_progress_db()
    _complete(client, [(BENCH_ID, 50, 8, 2)] * 3)
    before = _progress()[BENCH_ID]
    _complete(client, [(BENCH_ID, 40, 8, 2)] * 3, deload=True)
    after = _progress()[BENCH_ID]
    assert (after["next_weight_kg"], after["next_reps"]) == (before["next_weight_kg"], before["next_reps"])
    rec = _recs(client)[BENCH_ID]
    assert rec["recommended_weight_kg"] == 52.5
    assert rec["last_performance"]["sets"][0]["weight_kg"] == 50


def test_dos_sesiones_fallidas_seguidas_bajan_la_carga_en_la_api(client):
    init_progress_db()
    _complete(client, [(BENCH_ID, 60, 4, 0)] * 3)
    assert _progress()[BENCH_ID]["kind"] == "maintain_weight"
    _complete(client, [(BENCH_ID, 60, 5, 0)] * 3)
    p = _progress()[BENCH_ID]
    assert p["kind"] == "deload" and p["next_weight_kg"] == 55.0 and p["fail_streak"] == 2
    rec = _recs(client)[BENCH_ID]
    assert rec["recommendation"] == "deload" and rec["recommended_weight_kg"] == 55.0
    assert "deload" in rec["reason"]


def test_recompute_y_rebuild_dan_el_mismo_resultado_que_la_aplicacion_incremental(client):
    init_progress_db()
    _complete(client, [(BENCH_ID, 50, 7, 2)] * 3)
    _complete(client, [(BENCH_ID, 50, 8, 2)] * 3)
    incremental = {k: (v["next_weight_kg"], v["next_reps"], v["kind"]) for k, v in _progress().items()}
    conn = get_connection()
    try:
        rebuild_all_progress(conn, PABLO_ID)
        conn.commit()
    finally:
        conn.close()
    rebuilt = {k: (v["next_weight_kg"], v["next_reps"], v["kind"]) for k, v in _progress().items()}
    assert rebuilt[BENCH_ID] == incremental[BENCH_ID] == (52.5, 6, "increase_weight")


def test_home_expone_reps_tipo_y_racha_para_el_frontend(client):
    init_progress_db()
    _complete(client, [(BENCH_ID, 50, 7, 2)] * 3)
    load = client.get("/api/progress/home", params={"user_id": PABLO_ID}).json()["loads"][BENCH_ID]
    assert load["next_weight_kg"] == 50 and load["next_reps"] == 8 and load["kind"] == "add_reps"
    assert load["measure_type"] == "reps" and load["fail_streak"] == 0


def test_la_antigua_regla_no_sube_peso_si_solo_se_llego_al_minimo(client):
    """Antes: >= mínimo y RIR ok -> +2,5 kg. Ahora hay que llegar al máximo del rango."""
    init_progress_db()
    _complete(client, [(LEG_PRESS_ID, 100, 8, 2)] * 3)       # rango 8-10: solo mínimo
    p = _progress()[LEG_PRESS_ID]
    assert p["next_weight_kg"] == 100 and p["kind"] == "add_reps" and p["next_reps"] == 9
