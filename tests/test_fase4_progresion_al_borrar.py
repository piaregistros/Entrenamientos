"""Fase 4: borrar/editar entrenos invalida y recalcula exercise_progress."""
from conftest import PABLO_ID, ESTEFI_ID, EXERCISES, BENCH_ID, ROUTINE_A_ID
from app.database import get_connection
from app.progress_routes import (
    init_progress_db,
    rebuild_all_progress,
    recompute_exercise_progress,
)

FACE_PULL_ID = EXERCISES["face_pull"][0]


def _progress(user_id=PABLO_ID):
    conn = get_connection()
    try:
        return {
            r["exercise_id"]: (r["next_weight_kg"], r["reason"])
            for r in conn.execute("SELECT * FROM exercise_progress WHERE user_id = ?", (user_id,))
        }
    finally:
        conn.close()


def _complete_workout(client, sets, routine_id=ROUTINE_A_ID):
    """sets: lista de (exercise_id, kg, reps, rir). Devuelve workout_id."""
    r = client.post("/api/workouts", json={"user_id": PABLO_ID, "routine_id": routine_id})
    assert r.status_code == 200, r.text
    wid = r.json()["id"]
    counters = {}
    ids = []
    for ex, kg, reps, rir in sets:
        counters[ex] = counters.get(ex, 0) + 1
        s = client.post(
            f"/api/workouts/{wid}/sets",
            params={"user_id": PABLO_ID},
            json={"exercise_id": ex, "set_number": counters[ex], "weight_kg": kg, "reps": reps, "rir": rir},
        )
        assert s.status_code == 200, s.text
        ids.append(s.json()["id"])
    r = client.put(f"/api/workouts/{wid}", params={"user_id": PABLO_ID}, json={"status": "completed", "duration_minutes": 50})
    assert r.status_code == 200, r.text
    return wid, ids


def test_borrar_el_ultimo_entreno_vuelve_al_estado_del_anterior(client):
    init_progress_db()
    # Historial sembrado: banca 35 kg x8 (completado, sin fila en exercise_progress)
    wid, _ = _complete_workout(client, [(BENCH_ID, 50, 8, 2)] * 3)
    assert _progress()[BENCH_ID][0] == 52.5

    assert client.delete(f"/api/workouts/{wid}").status_code == 200

    after = _progress()
    # Ahora la carga sale del entreno anterior (35 kg), no del borrado (50 kg)
    assert BENCH_ID in after
    assert after[BENCH_ID][0] == 37.5
    assert "52.5" not in str(after[BENCH_ID])


def test_borrar_el_unico_entreno_de_un_ejercicio_elimina_su_progresion(client):
    init_progress_db()
    wid, _ = _complete_workout(client, [(FACE_PULL_ID, 20, 12, 2)] * 3)
    assert FACE_PULL_ID in _progress()
    assert client.delete(f"/api/workouts/{wid}").status_code == 200
    assert FACE_PULL_ID not in _progress()
    # y /progress/home ya no ofrece carga para ese ejercicio
    loads = client.get("/api/progress/home", params={"user_id": PABLO_ID}).json()["loads"]
    assert FACE_PULL_ID not in loads


def test_borrar_entreno_antiguo_no_cambia_la_progresion_del_ultimo(client):
    init_progress_db()
    w_old, _ = _complete_workout(client, [(BENCH_ID, 40, 8, 2)] * 3)
    w_new, _ = _complete_workout(client, [(BENCH_ID, 45, 8, 2)] * 3)
    assert _progress()[BENCH_ID][0] == 47.5
    assert client.delete(f"/api/workouts/{w_old}").status_code == 200
    assert _progress()[BENCH_ID][0] == 47.5


def test_borrar_entreno_en_curso_no_toca_la_progresion(client):
    init_progress_db()
    _complete_workout(client, [(BENCH_ID, 45, 8, 2)] * 3)
    before = _progress()
    r = client.post("/api/workouts", json={"user_id": PABLO_ID, "routine_id": ROUTINE_A_ID})
    wid = r.json()["id"]
    assert client.delete(f"/api/workouts/{wid}").status_code == 200
    assert _progress() == before


def test_editar_y_borrar_series_de_un_entreno_completado_recalcula(client):
    init_progress_db()
    wid, set_ids = _complete_workout(client, [(BENCH_ID, 50, 8, 2)] * 3)
    assert _progress()[BENCH_ID][0] == 52.5

    # editar la serie 1: 50 -> 60 kg (el máximo manda)
    r = client.put(
        f"/api/workouts/{wid}/sets/{set_ids[0]}",
        params={"user_id": PABLO_ID},
        json={"set_number": 1, "weight_kg": 60, "reps": 8, "rir": 2, "is_warmup": False},
    )
    assert r.status_code == 200, r.text
    assert _progress()[BENCH_ID][0] == 62.5

    # borrar esa serie: vuelve a 50 kg -> 52.5
    assert client.delete(f"/api/workouts/{wid}/sets/{set_ids[0]}", params={"user_id": PABLO_ID}).status_code == 200
    assert _progress()[BENCH_ID][0] == 52.5

    # añadir una serie nueva más pesada a la sesión cerrada
    r = client.post(
        f"/api/workouts/{wid}/sets",
        params={"user_id": PABLO_ID},
        json={"exercise_id": BENCH_ID, "set_number": 9, "weight_kg": 70, "reps": 8, "rir": 2},
    )
    assert r.status_code == 200, r.text
    assert _progress()[BENCH_ID][0] == 72.5


def test_no_se_toca_la_progresion_de_otros_usuarios(client):
    init_progress_db()
    wid, _ = _complete_workout(client, [(BENCH_ID, 50, 8, 2)] * 3)
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO exercise_progress (user_id, exercise_id, next_weight_kg, reason, updated_at) VALUES (?,?,?,?,?)",
            (ESTEFI_ID, BENCH_ID, 99.0, "otro usuario", "2026-01-01T00:00:00"),
        )
        conn.commit()
    finally:
        conn.close()
    assert client.delete(f"/api/workouts/{wid}").status_code == 200
    assert _progress(ESTEFI_ID)[BENCH_ID] == (99.0, "otro usuario")


def test_no_se_puede_borrar_el_entreno_de_otro_usuario(client_pablo, client_estefi):
    init_progress_db()
    wid, _ = _complete_workout(client_pablo, [(BENCH_ID, 50, 8, 2)] * 3)
    before = _progress()
    assert client_estefi.delete(f"/api/workouts/{wid}").status_code == 404
    assert _progress() == before


def test_rebuild_all_progress_limpia_estados_obsoletos(client):
    init_progress_db()
    conn = get_connection()
    try:
        # estado obsoleto: ejercicio sin ningún entreno completado + valor desfasado
        conn.execute(
            "INSERT INTO exercise_progress (user_id, exercise_id, next_weight_kg, reason, updated_at) VALUES (?,?,?,?,?)",
            (PABLO_ID, FACE_PULL_ID, 22.5, "Cumpliste 8-12 a RIR 2 → +2.5 kg", "2026-01-01T00:00:00"),
        )
        conn.execute(
            "INSERT INTO exercise_progress (user_id, exercise_id, next_weight_kg, reason, updated_at) VALUES (?,?,?,?,?)",
            (PABLO_ID, BENCH_ID, 80.0, "desfasado", "2026-01-01T00:00:00"),
        )
        conn.commit()

        # simulación: se calcula y se revierte
        report = rebuild_all_progress(conn, PABLO_ID)
        conn.rollback()
        assert {c["exercise_id"] for c in report["cambios"]} >= {FACE_PULL_ID, BENCH_ID}
        assert conn.execute("SELECT COUNT(*) FROM exercise_progress WHERE exercise_id=?", (FACE_PULL_ID,)).fetchone()[0] == 1

        rebuild_all_progress(conn, PABLO_ID)
        conn.commit()
    finally:
        conn.close()
    after = _progress()
    assert FACE_PULL_ID not in after
    assert after[BENCH_ID][0] == 37.5  # desde el entreno sembrado (35 kg x 8)


def test_recompute_funciona_sin_tabla_previa(client):
    """La tabla puede no existir aún (se crea de forma perezosa en producción)."""
    conn = get_connection()
    try:
        conn.execute("DROP TABLE IF EXISTS exercise_progress")
        recompute_exercise_progress(conn, PABLO_ID, {BENCH_ID})
        conn.commit()
        assert conn.execute("SELECT next_weight_kg FROM exercise_progress WHERE exercise_id=?", (BENCH_ID,)).fetchone()[0] == 37.5
    finally:
        conn.close()
