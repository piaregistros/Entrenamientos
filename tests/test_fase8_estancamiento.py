"""Fase 8: avisos de estancamiento y deload, temporizador (backend) y copias."""
import pytest

from conftest import BENCH_ID, ESTEFI_ID, EXERCISES, PABLO_ID

LEG_PRESS_ID = EXERCISES["leg_press"][0]
from app.main import app
from app.progress_routes import init_progress_db
from app.progression import deload_weight, next_target
from app.stagnation import detect_stagnation

# Reutilizamos el reloj de fechas distintas del test de la fase 6.
from test_fase6_doble_progresion import _complete


def S(weight, reps, rir=2, warmup=False):
    return {"weight_kg": weight, "reps": reps, "rir": rir, "is_warmup": warmup}


def ex(name="Press banca plano", equipment="Barra", exercise_type="compuesto", measure="reps",
       inc=2.5, rep_min=8, rep_max=12, rir=2, **extra):
    data = {
        "id": "ex-1", "name": name, "equipment": equipment, "exercise_type": exercise_type,
        "measure_type": measure, "weight_increment_kg": inc, "rep_min": rep_min,
        "rep_max": rep_max, "rir_target": rir, "target_muscle": "Pectoral",
    }
    data.update(extra)
    return data


def plateau(n, weight=50, reps=10):
    return [[S(weight, reps), S(weight, reps), S(weight, reps)] for _ in range(n)]


# ------------------------------------------------------------------ pura
def test_tres_sesiones_iguales_es_estancamiento():
    r = detect_stagnation(ex(), plateau(3))
    assert r is not None
    assert r["kind"] == "plateau"
    assert r["sessions_without_progress"] == 3
    assert r["fail_streak"] == 0
    assert r["last_weight_kg"] == 50 and r["last_min_reps"] == 10
    assert r["suggested_deload_kg"] == deload_weight(50, 2.5)
    assert r["suggestion"] == "deload_or_swap"
    assert "3 sesiones" in r["reason"]
    assert "deload" in r["reason"].lower() or "−10" in r["reason"] or "-10" in r["reason"]


def test_dos_sesiones_iguales_aun_no_es_estancamiento():
    assert detect_stagnation(ex(), plateau(2)) is None


def test_subir_peso_en_la_ultima_rompe_el_estancamiento():
    sessions = plateau(3)
    sessions[0] = [S(52.5, 8), S(52.5, 8), S(52.5, 8)]  # más reciente primero
    assert detect_stagnation(ex(), sessions) is None


def test_subir_reps_en_la_ultima_rompe_el_estancamiento():
    sessions = [
        [S(50, 11), S(50, 11), S(50, 11)],
        [S(50, 10), S(50, 10), S(50, 10)],
        [S(50, 10), S(50, 10), S(50, 10)],
    ]
    assert detect_stagnation(ex(), sessions) is None


def test_cuatro_sesiones_en_meseta_cuenta_cuatro():
    r = detect_stagnation(ex(), plateau(4, weight=80, reps=8))
    assert r["sessions_without_progress"] == 4
    assert r["suggested_deload_kg"] == deload_weight(80, 2.5)


def test_calentamientos_y_series_vacias_no_cuentan():
    sessions = [
        [S(50, 10, warmup=True), S(50, 10), S(50, 10)],
        [S(50, 0), S(50, 10), S(50, 10)],
        [S(50, 10), S(50, 10)],
    ]
    r = detect_stagnation(ex(), sessions)
    assert r is not None and r["sessions_without_progress"] == 3


def test_racha_de_fallos_de_dos_es_aviso_de_deload():
    failed = [[S(60, 5), S(60, 4), S(60, 5)] for _ in range(2)]
    r = detect_stagnation(ex(), failed)
    assert r is not None
    assert r["kind"] == "fail_streak"
    assert r["fail_streak"] >= 2
    assert r["suggested_deload_kg"] == deload_weight(60, 2.5)
    assert "fallado" in r["reason"]
    # Coincide con next_target (deload a las 2 fallidas).
    t = next_target(ex(), failed)
    assert t["kind"] == "deload"
    assert r["suggested_deload_kg"] == t["weight_kg"]


def test_un_solo_fallo_sin_meseta_no_alerta():
    sessions = [
        [S(50, 6), S(50, 7)],
        [S(50, 10), S(50, 10)],
    ]
    assert detect_stagnation(ex(), sessions) is None


def test_isometrico_sin_subir_tiempo_es_estancamiento():
    sessions = [[S(0, 40), S(0, 40)] for _ in range(3)]
    r = detect_stagnation(ex(name="Plancha", equipment="Peso corporal", exercise_type="core",
                             measure="time", inc=0, rep_min=30, rep_max=60), sessions)
    assert r is not None
    assert r["kind"] == "plateau"
    assert r["unit"] == "s"
    assert r["suggestion"] == "swap"          # sin carga, no hay deload en kg
    assert r["suggested_deload_kg"] is None
    assert "tiempo" in r["reason"] or "s" in r["reason"]


def test_isometrico_que_suma_segundos_no_esta_estancado():
    sessions = [
        [S(0, 50), S(0, 50)],
        [S(0, 45), S(0, 45)],
        [S(0, 40), S(0, 40)],
    ]
    assert detect_stagnation(ex(name="Plancha", measure="time", inc=0, rep_min=30, rep_max=60), sessions) is None


def test_sin_historial_no_alerta():
    assert detect_stagnation(ex(), []) is None
    assert detect_stagnation(ex(), [[S(50, 10, warmup=True)]]) is None


# ------------------------------------------------------------------ API
def test_endpoint_y_home_exponen_el_estancamiento(client):
    init_progress_db()
    for _ in range(3):
        _complete(client, [(LEG_PRESS_ID, 100, 8, 2)] * 3)

    r = client.get("/api/progress/stagnation", params={"user_id": PABLO_ID})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] >= 1
    item = next(x for x in data["items"] if x["exercise_id"] == LEG_PRESS_ID)
    assert item["kind"] == "plateau"
    assert item["sessions_without_progress"] >= 3
    assert item["name"] == "Prensa de piernas"
    assert item["suggested_deload_kg"] == deload_weight(100, 5.0)
    assert "sesiones" in item["reason"]

    home = client.get("/api/progress/home", params={"user_id": PABLO_ID}).json()
    assert "stagnation" in home
    assert any(x["exercise_id"] == LEG_PRESS_ID for x in home["stagnation"])


def test_si_progresa_deja_de_salir_en_el_endpoint(client):
    init_progress_db()
    for _ in range(3):
        _complete(client, [(LEG_PRESS_ID, 100, 8, 2)] * 3)
    assert any(x["exercise_id"] == LEG_PRESS_ID for x in client.get(
        "/api/progress/stagnation", params={"user_id": PABLO_ID}).json()["items"])
    _complete(client, [(LEG_PRESS_ID, 105, 8, 2)] * 3)
    items = client.get("/api/progress/stagnation", params={"user_id": PABLO_ID}).json()["items"]
    assert all(x["exercise_id"] != LEG_PRESS_ID for x in items)


def test_entreno_de_deload_no_cuenta_para_el_estancamiento(client):
    init_progress_db()
    _complete(client, [(LEG_PRESS_ID, 100, 8, 2)] * 3)
    _complete(client, [(LEG_PRESS_ID, 100, 8, 2)] * 3)
    _complete(client, [(LEG_PRESS_ID, 80, 8, 2)] * 3, deload=True)
    # Solo 2 sesiones reales: no debe alertar (el deload se ignora).
    items = client.get("/api/progress/stagnation", params={"user_id": PABLO_ID}).json()["items"]
    assert all(x["exercise_id"] != LEG_PRESS_ID for x in items)


def test_racha_de_fallos_sale_como_fail_streak(client):
    init_progress_db()
    _complete(client, [(BENCH_ID, 60, 4, 0)] * 3)
    _complete(client, [(BENCH_ID, 60, 5, 0)] * 3)
    item = next(x for x in client.get(
        "/api/progress/stagnation", params={"user_id": PABLO_ID}).json()["items"]
        if x["exercise_id"] == BENCH_ID)
    assert item["kind"] == "fail_streak"
    assert item["fail_streak"] >= 2
    assert item["suggested_deload_kg"] == 55.0
    assert item["progression_kind"] == "deload"


def test_estefi_no_ve_el_estancamiento_de_pablo(client_estefi, client_pablo):
    init_progress_db()
    for _ in range(3):
        _complete(client_pablo, [(LEG_PRESS_ID, 100, 8, 2)] * 3)
    r = client_estefi.get("/api/progress/stagnation", params={"user_id": PABLO_ID})
    # Estefi no es admin: no puede consultar a otro usuario.
    assert r.status_code in (401, 403, 404)
    own = client_estefi.get("/api/progress/stagnation", params={"user_id": ESTEFI_ID})
    assert own.status_code == 200
    assert own.json()["count"] == 0


def test_sin_sesion_es_401():
    from fastapi.testclient import TestClient
    with TestClient(app) as anon:
        r = anon.get("/api/progress/stagnation", params={"user_id": PABLO_ID})
        assert r.status_code == 401
