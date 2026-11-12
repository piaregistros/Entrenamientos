"""Fase 3: ejercicios extra y sustituciones persistentes en la sesión activa."""
from conftest import PABLO_ID, ESTEFI_ID, EXERCISES, ROUTINE_A_ID
from app.database import get_connection

LEG_PRESS_ID = EXERCISES["leg_press"][0]
BULGARIAN_ID = EXERCISES["bulgarian"][0]
FACE_PULL_ID = EXERCISES["face_pull"][0]   # no está en la rutina A
HIP_THRUST_ID = EXERCISES["hip_thrust"][0]  # no está en la rutina A


def _start(client, routine_id=ROUTINE_A_ID):
    r = client.post("/api/workouts", json={"user_id": PABLO_ID, "routine_id": routine_id})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _get(client, workout_id):
    r = client.get(f"/api/workouts/{workout_id}", params={"user_id": PABLO_ID})
    assert r.status_code == 200, r.text
    return r.json()


def _add_extra(client, workout_id, exercise_id, **body):
    return client.post(
        f"/api/workouts/{workout_id}/extra-exercises",
        params={"user_id": PABLO_ID},
        json={"exercise_id": exercise_id, **body},
    )


def test_extra_se_guarda_y_se_devuelve_al_reanudar_sin_series(client):
    wid = _start(client)
    assert _get(client, wid)["extra_exercises"] == []

    r = _add_extra(client, wid, FACE_PULL_ID)
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True

    # "recargar": un GET nuevo debe devolverlo aunque no tenga ninguna serie
    data = _get(client, wid)
    assert len(data["extra_exercises"]) == 1
    extra = data["extra_exercises"][0]
    assert extra["exercise_id"] == FACE_PULL_ID
    assert extra["position"] == 1
    assert extra["target_sets"] == 3 and extra["target_rep_min"] == 8 and extra["target_rep_max"] == 12
    assert extra["exercise"]["name"] == "Face pull"
    assert extra["exercise"]["equipment"] == "Polea"
    assert data["sets"] == []


def test_extras_conservan_orden_y_parametros(client):
    wid = _start(client)
    assert _add_extra(client, wid, FACE_PULL_ID, target_sets=2, target_rep_min=12, target_rep_max=15, rest_seconds=60).status_code == 200
    assert _add_extra(client, wid, HIP_THRUST_ID).status_code == 200
    extras = _get(client, wid)["extra_exercises"]
    assert [e["exercise_id"] for e in extras] == [FACE_PULL_ID, HIP_THRUST_ID]
    assert [e["position"] for e in extras] == [1, 2]
    assert extras[0]["target_sets"] == 2 and extras[0]["rest_seconds"] == 60


def test_extra_es_idempotente(client):
    wid = _start(client)
    assert _add_extra(client, wid, FACE_PULL_ID).json()["created"] is True
    r = _add_extra(client, wid, FACE_PULL_ID)
    assert r.status_code == 200
    assert r.json()["created"] is False
    assert len(_get(client, wid)["extra_exercises"]) == 1


def test_extra_ejercicio_de_la_rutina_se_rechaza(client):
    wid = _start(client)
    r = _add_extra(client, wid, LEG_PRESS_ID)
    assert r.status_code == 409


def test_extra_validaciones(client):
    wid = _start(client)
    assert _add_extra(client, wid, "no-existe").status_code == 404
    assert _add_extra(client, wid, FACE_PULL_ID, target_rep_min=10, target_rep_max=5).status_code == 400
    assert _add_extra(client, wid, FACE_PULL_ID, target_sets=0).status_code == 422
    r = client.post(f"/api/workouts/no-existe/extra-exercises", params={"user_id": PABLO_ID}, json={"exercise_id": FACE_PULL_ID})
    assert r.status_code == 404


def test_extra_solo_en_sesion_en_curso(client):
    wid = _start(client)
    r = client.put(f"/api/workouts/{wid}", params={"user_id": PABLO_ID}, json={"status": "cancelled"})
    assert r.status_code == 200, r.text
    assert _add_extra(client, wid, FACE_PULL_ID).status_code == 409


def test_extra_no_se_puede_añadir_a_sesion_de_otro_usuario(client_estefi, client_pablo):
    wid = _start(client_pablo)
    r = client_estefi.post(
        f"/api/workouts/{wid}/extra-exercises",
        params={"user_id": ESTEFI_ID},
        json={"exercise_id": FACE_PULL_ID},
    )
    assert r.status_code == 404
    r = client_estefi.post(
        f"/api/workouts/{wid}/extra-exercises",
        params={"user_id": PABLO_ID},
        json={"exercise_id": FACE_PULL_ID},
    )
    assert r.status_code == 403
    assert _get(client_pablo, wid)["extra_exercises"] == []


def test_extra_con_series_sigue_apareciendo_y_series_ok(client):
    # En esta rama (basada en prod) las tablas de progresión se crean de forma
    # perezosa; la fase 2 las crea en el arranque. Inofensivo en ambos casos.
    from app.progress_routes import init_progress_db
    init_progress_db()
    wid = _start(client)
    _add_extra(client, wid, FACE_PULL_ID)
    r = client.post(
        f"/api/workouts/{wid}/sets",
        params={"user_id": PABLO_ID},
        json={"exercise_id": FACE_PULL_ID, "set_number": 1, "weight_kg": 20, "reps": 12, "rir": 2},
    )
    assert r.status_code == 200, r.text
    data = _get(client, wid)
    assert [e["exercise_id"] for e in data["extra_exercises"]] == [FACE_PULL_ID]
    assert [s["exercise_id"] for s in data["sets"]] == [FACE_PULL_ID]
    # terminar la sesión no pierde el extra en el historial
    r = client.put(f"/api/workouts/{wid}", params={"user_id": PABLO_ID}, json={"status": "completed", "duration_minutes": 40})
    assert r.status_code == 200, r.text
    assert len(_get(client, wid)["extra_exercises"]) == 1


def test_sustituciones_se_leen_al_reanudar(client):
    wid = _start(client)
    assert _get(client, wid)["substitutions"] == []
    r = client.post(
        f"/api/workouts/{wid}/substitute-exercise",
        params={"user_id": PABLO_ID},
        json={"original_exercise_id": LEG_PRESS_ID, "substitute_exercise_id": BULGARIAN_ID, "reason": "Prensa ocupada"},
    )
    assert r.status_code == 200, r.text
    subs = _get(client, wid)["substitutions"]
    assert len(subs) == 1
    assert subs[0]["original_exercise_id"] == LEG_PRESS_ID
    assert subs[0]["substitute_exercise_id"] == BULGARIAN_ID
    assert subs[0]["reason"] == "Prensa ocupada"
    assert subs[0]["substitute_exercise"]["name"] == "Sentadilla búlgara"


def test_borrar_entreno_elimina_extras_en_cascada(client):
    wid = _start(client)
    _add_extra(client, wid, FACE_PULL_ID)
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM workout_extra_exercises WHERE workout_log_id=?", (wid,)).fetchone()[0] == 1
    finally:
        conn.close()
    assert client.delete(f"/api/workouts/{wid}").status_code == 200
    conn = get_connection()
    try:
        assert conn.execute("SELECT COUNT(*) FROM workout_extra_exercises WHERE workout_log_id=?", (wid,)).fetchone()[0] == 0
    finally:
        conn.close()


def test_extras_de_una_sesion_no_aparecen_en_otra(client):
    w1 = _start(client)
    _add_extra(client, w1, FACE_PULL_ID)
    client.put(f"/api/workouts/{w1}", params={"user_id": PABLO_ID}, json={"status": "cancelled"})
    w2 = _start(client)
    assert _get(client, w2)["extra_exercises"] == []
