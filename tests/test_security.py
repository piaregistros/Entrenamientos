import pytest


PABLO_ID = "1effca7d-97cf-41f2-a930-9ce482972f02"
ESTEFI_ID = "2bf9e2da-6314-46c3-95cd-edbaf1d13b9c9"


def test_unauthenticated_users_endpoint_is_rejected(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/api/users")

    assert response.status_code == 401


def test_estefi_can_access_own_routines(client_estefi):
    response = client_estefi.get(
        "/api/routines",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200


def test_estefi_cannot_access_pablo_routines(client_estefi):
    response = client_estefi.get(
        "/api/routines",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 403


def test_pablo_can_access_estefi_routines(client_pablo):
    response = client_pablo.get(
        "/api/routines",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200


def test_estefi_cannot_read_pablo_body_metrics(client_estefi):
    response = client_estefi.get(
        "/api/body-metrics",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 403


def test_pablo_can_read_estefi_body_metrics(client_pablo):
    response = client_pablo.get(
        "/api/body-metrics",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200


def test_estefi_cannot_read_pablo_stats(client_estefi):
    response = client_estefi.get(
        "/api/stats/summary",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 403


def test_pablo_can_read_estefi_stats(client_pablo):
    response = client_pablo.get(
        "/api/stats/summary",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200


def test_estefi_cannot_spoof_user_id_when_creating_workout(
    client_estefi,
    test_db,
):
    response = client_estefi.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "date": "2026-09-08T07:00:00",
            "duration_minutes": 0,
            "notes": "security test",
            "status": "in_progress",
        },
    )

    assert response.status_code == 403


def test_pablo_can_create_workout_for_estefi(
    client_pablo,
    test_db,
):
    response = client_pablo.post(
        "/api/workouts",
        json={
            "user_id": ESTEFI_ID,
            "routine_id": None,
            "date": "2026-09-08T07:00:00",
            "duration_minutes": 0,
            "notes": "security test",
            "status": "in_progress",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    import sqlite3

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row

    row = conn.execute(
        "SELECT user_id FROM workout_logs WHERE id = ?",
        (workout_id,),
    ).fetchone()

    assert row["user_id"] == ESTEFI_ID

    conn.execute(
        "DELETE FROM workout_logs WHERE id = ?",
        (workout_id,),
    )
    conn.commit()
    conn.close()


def test_estefi_cannot_change_pablo_password(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "name": "Estefi",
                "password": "test-estefi-password",
            },
        )

        assert login.status_code == 200

        csrf_token = client.cookies.get("entrenamiento_csrf")
        assert csrf_token
        client.headers.update({"X-CSRF-Token": csrf_token})

        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "test-estefi-password",
                "new_password": "new-estefi-password-123",
                "new_password_confirmation": "new-estefi-password-123",
            },
        )

        assert response.status_code == 200

        me = client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["id"] == ESTEFI_ID


def test_logout_revokes_session(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "name": "Pablo",
                "password": "test-pablo-password",
            },
        )

        assert login.status_code == 200

        csrf_token = client.cookies.get("entrenamiento_csrf")
        assert csrf_token
        client.headers.update({"X-CSRF-Token": csrf_token})

        me = client.get("/api/auth/me")
        assert me.status_code == 200

        logout = client.post("/api/auth/logout")
        assert logout.status_code == 200

        me_after = client.get("/api/auth/me")
        assert me_after.status_code == 401


# ============================================================
# Tests específicos de CSRF
# ============================================================

def test_authenticated_post_without_csrf_is_rejected(client_pablo):
    client_pablo.headers.pop("X-CSRF-Token", None)

    response = client_pablo.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "CSRF sin token",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_authenticated_post_with_invalid_csrf_is_rejected(client_pablo):
    client_pablo.headers.update({
        "X-CSRF-Token": "token-csrf-invalido",
    })

    response = client_pablo.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "CSRF token falso",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "CSRF validation failed"


def test_authenticated_post_with_valid_csrf_is_allowed(client_pablo):
    csrf_token = client_pablo.cookies.get("entrenamiento_csrf")

    assert csrf_token

    client_pablo.headers.update({
        "X-CSRF-Token": csrf_token,
    })

    response = client_pablo.post(
        "/api/workouts",
        json={
            "user_id": PABLO_ID,
            "routine_id": None,
            "notes": "CSRF correcto",
        },
    )

    assert response.status_code == 200

    workout_id = response.json()["id"]

    from app import database

    conn = database.get_connection()

    try:
        conn.execute(
            "DELETE FROM workout_logs WHERE id = ?",
            (workout_id,),
        )
        conn.commit()
    finally:
        conn.close()


def test_login_works_without_csrf(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={
                "name": "Pablo",
                "password": "test-pablo-password",
            },
        )

        assert response.status_code == 200
        assert client.cookies.get("entrenamiento_session")
        assert client.cookies.get("entrenamiento_csrf")


def test_logout_clears_csrf_cookie(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        login = client.post(
            "/api/auth/login",
            json={
                "name": "Pablo",
                "password": "test-pablo-password",
            },
        )

        assert login.status_code == 200

        csrf_token = client.cookies.get("entrenamiento_csrf")
        assert csrf_token

        client.headers.update({
            "X-CSRF-Token": csrf_token,
        })

        logout = client.post("/api/auth/logout")

        assert logout.status_code == 200
        assert not client.cookies.get("entrenamiento_csrf")

        me = client.get("/api/auth/me")
        assert me.status_code == 401



# ============================================================
# BODY EVOLUTION — BODY METRICS AMPLIADOS
# ============================================================

def test_pablo_can_create_body_metric_with_composition_data(client_pablo):
    response = client_pablo.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "weight_kg": 72.4,
            "body_fat_pct": 15.2,
            "muscle_mass_kg": 57.8,
            "water_pct": 61.3,
            "visceral_fat": 6,
            "basal_metabolic_rate_kcal": 1685,
            "bone_mass_kg": 3.1,
            "notes": "Medición de prueba",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == PABLO_ID
    assert data["weight_kg"] == 72.4
    assert data["body_fat_pct"] == 15.2
    assert data["muscle_mass_kg"] == 57.8
    assert data["water_pct"] == 61.3
    assert data["visceral_fat"] == 6
    assert data["basal_metabolic_rate_kcal"] == 1685
    assert data["bone_mass_kg"] == 3.1


def test_pablo_can_read_body_metric_composition_data(client_pablo):
    create_response = client_pablo.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "weight_kg": 72.4,
            "body_fat_pct": 15.2,
            "muscle_mass_kg": 57.8,
            "water_pct": 61.3,
            "visceral_fat": 6,
            "basal_metabolic_rate_kcal": 1685,
            "bone_mass_kg": 3.1,
        },
    )
    assert create_response.status_code == 200

    response = client_pablo.get(
        "/api/body-metrics",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    metrics = response.json()["metrics"]

    metric = next(
        item for item in metrics
        if item["date"] == "2026-09-09"
    )

    assert metric["weight_kg"] == 72.4
    assert metric["body_fat_pct"] == 15.2
    assert metric["muscle_mass_kg"] == 57.8
    assert metric["water_pct"] == 61.3
    assert metric["visceral_fat"] == 6
    assert metric["basal_metabolic_rate_kcal"] == 1685
    assert metric["bone_mass_kg"] == 3.1


def test_pablo_can_update_body_metric_composition_data(client_pablo):
    create_response = client_pablo.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "weight_kg": 72.4,
            "body_fat_pct": 15.2,
            "muscle_mass_kg": 57.8,
            "water_pct": 61.3,
            "visceral_fat": 6,
            "basal_metabolic_rate_kcal": 1685,
            "bone_mass_kg": 3.1,
        },
    )
    assert create_response.status_code == 200

    response = client_pablo.get(
        "/api/body-metrics",
        params={"user_id": PABLO_ID},
    )

    metric = next(
        item for item in response.json()["metrics"]
        if item["date"] == "2026-09-09"
    )

    metric_id = metric["id"]

    response = client_pablo.put(
        f"/api/body-metrics/{metric_id}",
        params={"user_id": PABLO_ID},
        json={
            "date": "2026-09-09",
            "weight_kg": 72.6,
            "body_fat_pct": 15.0,
            "muscle_mass_kg": 58.0,
            "water_pct": 61.5,
            "visceral_fat": 5.8,
            "basal_metabolic_rate_kcal": 1690,
            "bone_mass_kg": 3.1,
            "notes": "Medición actualizada",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["weight_kg"] == 72.6
    assert data["body_fat_pct"] == 15.0
    assert data["muscle_mass_kg"] == 58.0
    assert data["water_pct"] == 61.5
    assert data["visceral_fat"] == 5.8
    assert data["basal_metabolic_rate_kcal"] == 1690


def test_body_metric_duplicate_date_is_rejected(client_pablo):
    first_response = client_pablo.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "weight_kg": 72.4,
        },
    )
    assert first_response.status_code == 200

    response = client_pablo.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "weight_kg": 73.0,
        },
    )

    assert response.status_code == 409


def test_estefi_cannot_create_body_metric_for_pablo(client_estefi):
    response = client_estefi.post(
        "/api/body-metrics",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-10",
            "weight_kg": 70.0,
        },
    )

    assert response.status_code == 403


# ============================================================
# BODY MEASUREMENTS
# ============================================================

def test_pablo_can_create_body_measurement(client_pablo):
    response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "waist_cm": 82.5,
            "chest_cm": 101.0,
            "arm_left_cm": 35.0,
            "arm_right_cm": 35.5,
            "thigh_left_cm": 57.0,
            "thigh_right_cm": 57.5,
            "hip_cm": 96.0,
            "neck_cm": 39.0,
            "notes": "Primera medición",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["user_id"] == PABLO_ID
    assert data["date"] == "2026-09-09"
    assert data["waist_cm"] == 82.5
    assert data["chest_cm"] == 101.0
    assert data["arm_left_cm"] == 35.0
    assert data["arm_right_cm"] == 35.5
    assert data["thigh_left_cm"] == 57.0
    assert data["thigh_right_cm"] == 57.5
    assert data["hip_cm"] == 96.0
    assert data["neck_cm"] == 39.0


def test_pablo_can_read_body_measurements(client_pablo):
    create_response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "waist_cm": 82.5,
            "chest_cm": 101.0,
        },
    )
    assert create_response.status_code == 200

    response = client_pablo.get(
        "/api/body/measurements",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    measurements = response.json()["measurements"]

    measurement = next(
        item for item in measurements
        if item["date"] == "2026-09-09"
    )

    assert measurement["waist_cm"] == 82.5
    assert measurement["chest_cm"] == 101.0


def test_pablo_can_update_body_measurement(client_pablo):
    create_response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "waist_cm": 82.5,
            "chest_cm": 101.0,
        },
    )
    assert create_response.status_code == 200

    response = client_pablo.get(
        "/api/body/measurements",
        params={"user_id": PABLO_ID},
    )

    measurement = next(
        item for item in response.json()["measurements"]
        if item["date"] == "2026-09-09"
    )

    measurement_id = measurement["id"]

    response = client_pablo.put(
        f"/api/body/measurements/{measurement_id}",
        params={"user_id": PABLO_ID},
        json={
            "date": "2026-09-09",
            "waist_cm": 82.0,
            "chest_cm": 101.5,
            "arm_left_cm": 35.2,
            "arm_right_cm": 35.7,
            "thigh_left_cm": 57.2,
            "thigh_right_cm": 57.7,
            "hip_cm": 95.5,
            "neck_cm": 39.0,
            "notes": "Actualizada",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["waist_cm"] == 82.0
    assert data["chest_cm"] == 101.5


def test_body_measurement_duplicate_date_is_rejected(client_pablo):
    first_response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "waist_cm": 82.5,
        },
    )
    assert first_response.status_code == 200

    response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "waist_cm": 80.0,
        },
    )

    assert response.status_code == 409


def test_estefi_cannot_create_body_measurement_for_pablo(client_estefi):
    response = client_estefi.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "2026-09-10",
            "waist_cm": 80.0,
        },
    )

    assert response.status_code == 403


def test_estefi_cannot_read_pablo_body_measurements(client_estefi):
    response = client_estefi.get(
        "/api/body/measurements",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 403


def test_invalid_body_measurement_date_is_rejected(client_pablo):
    response = client_pablo.post(
        "/api/body/measurements",
        json={
            "user_id": PABLO_ID,
            "date": "09/09/2026",
            "waist_cm": 80.0,
        },
    )

    assert response.status_code == 400


# ============================================================
# BODY PHOTOS
# ============================================================

def _jpeg_bytes(size=256):
    """Datos con firma JPEG para probar la validación del backend."""
    return b"\xff\xd8\xff\xe0" + b"\x00" * max(0, size - 4)


def test_body_photo_upload_and_list(client_pablo):
    response = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "frontal.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["user_id"] == PABLO_ID
    assert data["date"] == "2026-09-09"
    assert data["month_key"] == "2026-09"
    assert data["angle"] == "front"
    assert data["content_type"] == "image/jpeg"
    assert data["original_filename"] == "frontal.jpg"

    response = client_pablo.get(
        "/api/body/photos",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200

    photos = response.json()["photos"]

    assert len(photos) == 1
    assert photos[0]["angle"] == "front"


def test_body_photo_all_angles_allowed(client_pablo):
    for angle in ("front", "side", "back"):
        response = client_pablo.post(
            "/api/body/photos",
            params={
                "user_id": PABLO_ID,
                "date": "2026-09-10",
                "angle": angle,
            },
            files={
                "file": (
                    f"{angle}.jpg",
                    _jpeg_bytes(),
                    "image/jpeg",
                )
            },
        )

        assert response.status_code == 200, response.text

    response = client_pablo.get(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "month_key": "2026-09",
        },
    )

    assert response.status_code == 200

    angles = {
        photo["angle"]
        for photo in response.json()["photos"]
    }

    assert angles == {"front", "side", "back"}


def test_body_photo_duplicate_same_month_and_angle_blocked(client_pablo):
    first = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-01",
            "angle": "front",
        },
        files={
            "file": (
                "first.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert first.status_code == 200, first.text

    second = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-20",
            "angle": "front",
        },
        files={
            "file": (
                "second.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert second.status_code == 409


def test_body_photo_different_month_allowed(client_pablo):
    for date in ("2026-09-10", "2026-10-10"):
        response = client_pablo.post(
            "/api/body/photos",
            params={
                "user_id": PABLO_ID,
                "date": date,
                "angle": "front",
            },
            files={
                "file": (
                    "front.jpg",
                    _jpeg_bytes(),
                    "image/jpeg",
                )
            },
        )

        assert response.status_code == 200, response.text


def test_body_photo_invalid_file_rejected(client_pablo):
    response = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "malicious.txt",
                b"esto no es una imagen",
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400


def test_body_photo_invalid_angle_rejected(client_pablo):
    response = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "diagonal",
        },
        files={
            "file": (
                "photo.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 400


def test_body_photo_over_10mb_rejected(client_pablo):
    oversized = (
        b"\xff\xd8\xff\xe0"
        + b"\x00" * (10 * 1024 * 1024)
    )

    response = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "huge.jpg",
                oversized,
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413


def test_body_photo_estefi_cannot_access_pablo(client_pablo, client_estefi):
    upload = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "front.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert upload.status_code == 200, upload.text

    photo_id = upload.json()["id"]

    response = client_estefi.get(
        "/api/body/photos",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 403

    response = client_estefi.get(
        f"/api/body/photos/{photo_id}/file",
    )

    assert response.status_code == 403


def test_body_photo_pablo_can_manage_estefi(client_pablo):
    response = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": ESTEFI_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "estefi.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 200, response.text

    response = client_pablo.get(
        "/api/body/photos",
        params={"user_id": ESTEFI_ID},
    )

    assert response.status_code == 200
    assert len(response.json()["photos"]) == 1


def test_body_photo_file_requires_authentication(test_db):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        response = client.get(
            "/api/body/photos/00000000-0000-0000-0000-000000000000/file"
        )

    assert response.status_code == 401


def test_body_photo_file_can_be_served(client_pablo):
    upload = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "front.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert upload.status_code == 200, upload.text

    photo_id = upload.json()["id"]

    response = client_pablo.get(
        f"/api/body/photos/{photo_id}/file",
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/jpeg")
    assert response.content.startswith(b"\xff\xd8\xff")


def test_body_photo_delete_removes_record_and_file(client_pablo):
    upload = client_pablo.post(
        "/api/body/photos",
        params={
            "user_id": PABLO_ID,
            "date": "2026-09-09",
            "angle": "front",
        },
        files={
            "file": (
                "front.jpg",
                _jpeg_bytes(),
                "image/jpeg",
            )
        },
    )

    assert upload.status_code == 200, upload.text

    data = upload.json()
    photo_id = data["id"]

    from app.main import BODY_PHOTOS_DIR
    from pathlib import Path

    relative_path = Path(data["file_path"])

    assert relative_path.parts[0] == "body_photos"

    physical_file = (
        BODY_PHOTOS_DIR
        / Path(*relative_path.parts[1:])
    )

    assert physical_file.is_file()

    response = client_pablo.delete(
        f"/api/body/photos/{photo_id}",
    )

    assert response.status_code == 200

    assert not physical_file.exists()

    response = client_pablo.get(
        "/api/body/photos",
        params={"user_id": PABLO_ID},
    )

    assert response.status_code == 200
    assert response.json()["photos"] == []

