from conftest import PABLO_ID, ESTEFI_ID, BENCH_ID


def test_users_are_isolated(client):
    response = client.get("/api/users")

    assert response.status_code == 200

    users = response.json()

    assert len(users) == 2
    assert {user["id"] for user in users} == {
        PABLO_ID,
        ESTEFI_ID,
    }


def test_create_workout_and_set(client):
    response = client.post(
        "/api/workouts",
        params={"user_id": PABLO_ID},
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "Test automatizado",
        },
    )

    assert response.status_code == 200

    workout = response.json()

    assert workout["user_id"] == PABLO_ID
    assert workout["status"] == "in_progress"

    workout_id = workout["id"]

    response = client.post(
        f"/api/workouts/{workout_id}/sets",
        params={"user_id": PABLO_ID},
        json={
            "exercise_id": BENCH_ID,
            "set_number": 1,
            "weight_kg": 35,
            "reps": 8,
            "rir": 2,
            "is_warmup": False,
            "notes": None,
        },
    )

    assert response.status_code == 200

    workout_set = response.json()

    assert workout_set["workout_log_id"] == workout_id
    assert workout_set["exercise_id"] == BENCH_ID
    assert workout_set["weight_kg"] == 35
    assert workout_set["reps"] == 8
    assert workout_set["rir"] == 2


def test_user_cannot_modify_other_users_workout(client):
    response = client.post(
        "/api/workouts",
        params={"user_id": PABLO_ID},
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "Privacidad",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    response = client.put(
        f"/api/workouts/{workout_id}",
        params={"user_id": ESTEFI_ID},
        json={
            "status": "completed",
            "duration_minutes": 60,
            "notes": "Intento no autorizado",
        },
    )

    assert response.status_code == 404


def test_workout_lifecycle(client):
    response = client.post(
        "/api/workouts",
        params={"user_id": PABLO_ID},
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "Lifecycle",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    response = client.put(
        f"/api/workouts/{workout_id}",
        params={"user_id": PABLO_ID},
        json={
            "status": "completed",
            "duration_minutes": 55,
            "notes": "Sesión terminada",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    response = client.put(
        f"/api/workouts/{workout_id}",
        params={"user_id": PABLO_ID},
        json={
            "status": "in_progress",
        },
    )

    assert response.status_code == 409


def test_set_edit_and_delete(client):
    response = client.post(
        "/api/workouts",
        params={"user_id": PABLO_ID},
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "Edit/delete",
        },
    )

    assert response.status_code == 200
    workout_id = response.json()["id"]

    response = client.post(
        f"/api/workouts/{workout_id}/sets",
        params={"user_id": PABLO_ID},
        json={
            "exercise_id": BENCH_ID,
            "set_number": 1,
            "weight_kg": 35,
            "reps": 8,
            "rir": 2,
            "is_warmup": False,
        },
    )

    assert response.status_code == 200
    set_id = response.json()["id"]

    response = client.put(
        f"/api/workouts/{workout_id}/sets/{set_id}",
        params={"user_id": PABLO_ID},
        json={
            "set_number": 1,
            "weight_kg": 37.5,
            "reps": 9,
            "rir": 1,
            "is_warmup": False,
        },
    )

    assert response.status_code == 200

    updated = response.json()

    assert updated["weight_kg"] == 37.5
    assert updated["reps"] == 9
    assert updated["rir"] == 1

    response = client.delete(
        f"/api/workouts/{workout_id}/sets/{set_id}",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
