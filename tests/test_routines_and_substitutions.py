from conftest import PABLO_ID, ESTEFI_ID, BENCH_ID


# IDs de la semilla de rutinas
ROUTINE_A_ID = "67da7730-d791-455e-b63e-85379e7a560d"
LEG_PRESS_ID = "f7b355b1-4b00-46b7-b768-57d11637e6cc"
BULGARIAN_ID = "21314d5b-324c-437c-8eb9-2cd458c21429"
LUNGES_ID = "74ce1fc4-b7e3-4c28-a483-f680c9706d4e"


def test_list_user_routines(client):
    response = client.get(
        "/api/routines",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    routines = response.json()

    assert isinstance(routines, list)
    assert len(routines) == 3

    assert {routine["id"] for routine in routines} == {
        ROUTINE_A_ID,
        "ab7bfa70-ae2d-4067-8fcc-7671d3896320",
        "06b5a2d1-0560-4a4b-a738-518f8f6cb742",
    }


def test_routine_can_be_retrieved(client):
    response = client.get(
        f"/api/routines/{ROUTINE_A_ID}",
    )

    assert response.status_code == 200

    # La ruta individual debe existir.
    routine = response.json()
    assert routine["id"] == ROUTINE_A_ID


def test_routine_with_last_performance(client):
    response = client.get(
        f"/api/routines/{ROUTINE_A_ID}/with-last-performance",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["routine"]["id"] == ROUTINE_A_ID
    assert "exercises" in data
    assert isinstance(data["exercises"], list)

    bench = next(
        exercise
        for exercise in data["exercises"]
        if exercise["exercise_id"] == BENCH_ID
    )

    assert bench["last_performance"] is not None
    assert bench["last_performance"]["sets"][0]["weight_kg"] == 35
    assert bench["last_performance"]["sets"][0]["reps"] == 8


def test_exercise_last_performance(client):
    response = client.get(
        f"/api/exercises/{BENCH_ID}/last-performance",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["exercise"]["id"] == BENCH_ID
    assert data["workout"] is not None
    assert data["workout"]["id"] == "677cd2fc-bf08-40f7-b890-4398b229abbc"
    assert len(data["sets"]) == 3
    assert data["sets"][0]["weight_kg"] == 35
    assert data["sets"][0]["reps"] == 8


def test_exercise_last_performance_isolated_by_user(client):
    response = client.get(
        f"/api/exercises/{BENCH_ID}/last-performance",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["workout"] is None
    assert data["sets"] == []


def test_exercise_substitutions(client):
    response = client.get(
        f"/api/exercises/{LEG_PRESS_ID}/substitutions",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["exercise_id"] == LEG_PRESS_ID
    assert "substitutions" in data

    substitutions = data["substitutions"]

    assert len(substitutions) >= 2

    ids = {item["exercise_id"] for item in substitutions}

    assert BULGARIAN_ID in ids
    assert LUNGES_ID in ids


def test_routine_recommendations(client):
    response = client.get(
        f"/api/routines/{ROUTINE_A_ID}/recommendations",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["routine_id"] == ROUTINE_A_ID
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)


def test_substitute_exercise_end_to_end(client):
    # Crear entrenamiento basado en la rutina A
    response = client.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": ROUTINE_A_ID,
            "notes": "Test sustitución",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    # Prensa -> Búlgara
    response = client.post(
        f"/api/workouts/{workout_id}/substitute-exercise",
        params={"user_id": PABLO_ID},
        json={
            "original_exercise_id": LEG_PRESS_ID,
            "substitute_exercise_id": BULGARIAN_ID,
            "reason": "Prensa ocupada",
        },
    )

    assert response.status_code == 200

    substitution = response.json()

    assert substitution["original_exercise"]["id"] == LEG_PRESS_ID
    assert substitution["substitute_exercise"]["id"] == BULGARIAN_ID

    # Intentar registrar la prensa original debe fallar
    response = client.post(
        f"/api/workouts/{workout_id}/sets",
        params={"user_id": PABLO_ID},
        json={
            "exercise_id": LEG_PRESS_ID,
            "set_number": 1,
            "weight_kg": 50,
            "reps": 8,
            "rir": 2,
        },
    )

    assert response.status_code == 409

    # Registrar la alternativa sí debe funcionar
    response = client.post(
        f"/api/workouts/{workout_id}/sets",
        params={"user_id": PABLO_ID},
        json={
            "exercise_id": BULGARIAN_ID,
            "set_number": 1,
            "weight_kg": 10,
            "reps": 8,
            "rir": 2,
        },
    )

    assert response.status_code == 200

    workout_set = response.json()

    assert workout_set["exercise_id"] == BULGARIAN_ID
    assert workout_set["reps"] == 8


def test_duplicate_substitution_is_rejected(client):
    response = client.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": ROUTINE_A_ID,
            "notes": "Test duplicado",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    payload = {
        "original_exercise_id": LEG_PRESS_ID,
        "substitute_exercise_id": BULGARIAN_ID,
        "reason": "Prensa ocupada",
    }

    response = client.post(
        f"/api/workouts/{workout_id}/substitute-exercise",
        params={"user_id": PABLO_ID},
        json=payload,
    )

    assert response.status_code == 200

    response = client.post(
        f"/api/workouts/{workout_id}/substitute-exercise",
        params={"user_id": PABLO_ID},
        json=payload,
    )

    assert response.status_code == 409


def test_substitution_cannot_be_used_by_other_user(client):
    response = client.post(
        "/api/workouts",
        json={
            "user_id": ESTEFI_ID,
            "routine_id": None,
            "notes": "Privacidad",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    response = client.post(
        f"/api/workouts/{workout_id}/substitute-exercise",
        params={"user_id": PABLO_ID},
        json={
            "original_exercise_id": LEG_PRESS_ID,
            "substitute_exercise_id": BULGARIAN_ID,
        },
    )

    assert response.status_code == 404
