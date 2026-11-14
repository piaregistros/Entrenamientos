"""Fase 12c: la sugerida es SIEMPRE la del gimnasio; Casa X es espejo de X y cuenta como haber hecho X."""
from conftest import (BENCH_ID, EXERCISES, PABLO_ID, ROUTINE_A_ID, ROUTINE_B_ID, ROUTINE_C_ID)
from app.casa import seed_casa_routines_for_user, apply_casa_seed
from app.casa_catalog import CASA_GYM_LINKS, CASA_ROUTINES, CASA_ROUTINES_VERSION
from app.database import get_connection
from app.progress_routes import init_progress_db, pick_next_routine
from test_fase6_doble_progresion import _complete
from test_fase12_entreno_casa import seed_pablo_casa

SETS = [(BENCH_ID, 40, 8, 2)]


def casa_ids():
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT name, id FROM routines WHERE user_id = ? AND location = 'casa' ORDER BY day_order", (PABLO_ID,)
        ).fetchall()
        return {r["name"]: r["id"] for r in rows}
    finally:
        conn.close()


def home(client, **params):
    r = client.get("/api/progress/home", params={"user_id": PABLO_ID, **params})
    assert r.status_code == 200, r.text
    return r.json()


def setup(client):
    init_progress_db()
    seed_pablo_casa()
    ids = casa_ids()
    assert set(ids) == {"Casa A", "Casa B", "Casa C"}
    _clear_history()
    return ids


def _clear_history():
    conn = get_connection()
    try:
        conn.execute("DELETE FROM workout_sets")
        conn.execute("DELETE FROM workout_logs")
        conn.commit()
    finally:
        conn.close()


def test_sin_historial_sugiere_la_primera_del_gimnasio_aunque_existan_las_de_casa(client):
    setup(client)
    h = home(client)
    assert h["next_routine_id"] == ROUTINE_A_ID
    assert h["location"] == "gimnasio"
    assert "Casa" not in h["tomorrow"]


def test_casa_x_cuenta_como_x_y_la_sugerida_sigue_siendo_de_gimnasio(client):
    ids = setup(client)
    esperado = [("Casa A", ROUTINE_B_ID), ("Casa B", ROUTINE_C_ID), ("Casa C", ROUTINE_A_ID)]
    for casa, siguiente in esperado:
        _complete(client, SETS, routine_id=ids[casa])
        h = home(client)
        assert h["next_routine_id"] == siguiente, casa
        assert "Casa" not in (h["next_routine_name"] or "")


def test_mezclando_gimnasio_y_casa_la_rotacion_no_se_rompe(client):
    ids = setup(client)
    _complete(client, SETS, routine_id=ROUTINE_A_ID)
    assert home(client)["next_routine_id"] == ROUTINE_B_ID
    _complete(client, SETS, routine_id=ids["Casa B"])        # tocaba B y la hizo en casa: cuenta como B
    assert home(client)["next_routine_id"] == ROUTINE_C_ID
    _complete(client, SETS, routine_id=ROUTINE_C_ID)
    assert home(client)["next_routine_id"] == ROUTINE_A_ID
    _complete(client, SETS, routine_id=ROUTINE_A_ID)
    _complete(client, SETS, routine_id=ids["Casa B"])
    _complete(client, SETS, routine_id=ids["Casa C"])
    assert home(client)["next_routine_id"] == ROUTINE_A_ID


def test_location_casa_devuelve_el_espejo_de_la_que_toca(client):
    ids = setup(client)
    h = home(client, location="casa")
    assert h["next_routine_id"] == ids["Casa A"]
    assert "sustituye a la" in h["tomorrow"]
    _complete(client, SETS, routine_id=ROUTINE_A_ID)
    assert home(client, location="casa")["next_routine_id"] == ids["Casa B"]
    assert home(client)["next_routine_id"] == ROUTINE_B_ID
    _complete(client, SETS, routine_id=ids["Casa B"])
    assert home(client, location="casa")["next_routine_id"] == ids["Casa C"]
    _complete(client, SETS, routine_id=ids["Casa C"])
    assert home(client, location="casa")["next_routine_id"] == ids["Casa A"]


def test_ubicacion_desconocida_cae_en_gimnasio(client):
    setup(client)
    assert home(client, location="luna")["next_routine_id"] == ROUTINE_A_ID


def test_usuario_solo_con_casa_sigue_teniendo_sugerencia(client):
    ids = setup(client)
    conn = get_connection()
    try:
        conn.execute("UPDATE routines SET is_active = 0 WHERE user_id = ? AND location != 'casa'", (PABLO_ID,))
        conn.commit()
        row, _ = pick_next_routine(conn, PABLO_ID, "gimnasio")
        assert row is not None and row["id"] == ids["Casa A"]
    finally:
        conn.close()


# ------------------------------------------------------------------ rutinas espejo
def _gym_routine(conn, rid):
    return conn.execute(
        """SELECT e.name, re."order", re.target_sets, re.target_rep_min, re.target_rep_max, e.movement_pattern
           FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id
           WHERE re.routine_id = ? ORDER BY re."order" """, (rid,)).fetchall()


def test_casa_a_b_c_son_espejo_slot_a_slot_de_las_del_gimnasio(client):
    ids = setup(client)
    conn = get_connection()
    try:
        for letter, gym_id in (("A", ROUTINE_A_ID), ("B", ROUTINE_B_ID), ("C", ROUTINE_C_ID)):
            gym, casa = _gym_routine(conn, gym_id), _gym_routine(conn, ids[f"Casa {letter}"])
            assert len(gym) == len(casa) == 7, letter
            for g, c in zip(gym, casa):
                if c["name"] == "Dominadas agarre neutro":     # peso corporal: rango propio (6-10)
                    assert (g["order"], g["target_sets"]) == (c["order"], c["target_sets"])
                    continue
                assert (g["order"], g["target_sets"], g["target_rep_min"], g["target_rep_max"]) == \
                       (c["order"], c["target_sets"], c["target_rep_min"], c["target_rep_max"]), (letter, g["name"], c["name"])
    finally:
        conn.close()


def test_los_ejercicios_distintos_estan_enlazados_con_su_equivalente_del_gimnasio():
    for name, spec in CASA_ROUTINES.items():
        for item in spec["exercises"]:
            ex = item[0]
            # o es el mismo ejercicio que en el gimnasio (no necesita enlace) o tiene enlace
            assert ex in CASA_GYM_LINKS or ex in {
                "Press banca plano", "Press de hombro con mancuernas agarre neutro", "Hip thrust", "Plancha",
                "Press inclinado con mancuernas 30 grados", "Sentadilla búlgara", "Remo unilateral con mancuerna",
            }, (name, ex)


def test_reaplicar_seed_actualiza_una_vez_y_luego_respeta_las_ediciones_sin_tocar_historial(client):
    ids = setup(client)
    _complete(client, SETS, routine_id=ids["Casa A"])
    conn = get_connection()
    try:
        before_logs = conn.execute("SELECT COUNT(*) FROM workout_logs").fetchone()[0]
        before_sets = conn.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0]
        # Simula una Casa A de la fase 12 (versión antigua con otros ejercicios)
        conn.execute("DELETE FROM casa_routine_versions")
        conn.execute("DELETE FROM routine_exercises WHERE routine_id = ?", (ids["Casa A"],))
        old = conn.execute("SELECT id FROM exercises WHERE name = 'Peso muerto con trap bar'").fetchone()["id"]
        conn.execute(
            """INSERT INTO routine_exercises (id, routine_id, exercise_id, "order", target_sets, target_rep_min,
               target_rep_max, target_rir, rest_seconds, is_optional) VALUES ('x1', ?, ?, 1, 3, 6, 8, 2, 150, 0)""",
            (ids["Casa A"], old))
        conn.commit()
        users = [{"id": PABLO_ID, "name": "Pablo"}]
        r1 = apply_casa_seed(conn, users=users)
        assert "Casa A" in r1["users"][0]["routines"]["updated"]
        names = [x["name"] for x in _gym_routine(conn, ids["Casa A"])]
        assert names[0] == "Sentadilla libre" and len(names) == 7
        # El usuario edita: quita un ejercicio. Una segunda pasada NO lo repone.
        conn.execute("DELETE FROM routine_exercises WHERE routine_id = ? AND \"order\" = 7", (ids["Casa A"],))
        conn.commit()
        r2 = apply_casa_seed(conn, users=users)
        assert r2["users"][0]["routines"]["updated"] == []
        assert len(_gym_routine(conn, ids["Casa A"])) == 6
        # --force-routines sí la repone
        r3 = apply_casa_seed(conn, users=users, force=True)
        assert len(r3["users"][0]["routines"]["updated"]) == 3
        assert len(_gym_routine(conn, ids["Casa A"])) == 7
        # mismo id de rutina e historial intacto
        assert casa_ids() == ids
        assert conn.execute("SELECT COUNT(*) FROM workout_logs").fetchone()[0] == before_logs
        assert conn.execute("SELECT COUNT(*) FROM workout_sets").fetchone()[0] == before_sets
        v = conn.execute("SELECT MIN(version) FROM casa_routine_versions WHERE user_id = ?", (PABLO_ID,)).fetchone()[0]
        assert v == CASA_ROUTINES_VERSION
    finally:
        conn.close()


def test_punto_de_partida_de_un_ejercicio_de_casa_desde_el_del_gimnasio(client):
    from app.progression_db import compute_exercise_target, ensure_progression_schema
    ids = setup(client)
    leg_press = EXERCISES["leg_press"][0]
    _complete(client, [(leg_press, 100, 8, 2)] * 3, routine_id=ROUTINE_A_ID)
    conn = get_connection()
    try:
        ensure_progression_schema(conn)
        squat = conn.execute("SELECT id FROM exercises WHERE name = 'Sentadilla libre'").fetchone()["id"]
        res, _ = compute_exercise_target(conn, PABLO_ID, squat, routine_id=ids["Casa A"])
        assert res["kind"] == "start"
        assert res["weight_kg"] == 40.0            # 0,4 × 100 kg, redondeado al incremento
        assert res["gym_link"]["exercise"] == "Prensa de piernas"
        # Sin historial en el gimnasio no se inventa nada
        curl = conn.execute("SELECT id FROM exercises WHERE name = 'Curl con mancuernas'").fetchone()["id"]
        res2, _ = compute_exercise_target(conn, PABLO_ID, curl, routine_id=ids["Casa A"])
        assert res2["weight_kg"] is None and "gym_link" not in res2
    finally:
        conn.close()
