import sqlite3

def test_api_is_importable(client):
    """
    Smoke test básico: la aplicación debe poder arrancar
    y responder a una ruta válida.
    """
    response = client.get("/api/exercises")
    assert response.status_code == 200


def test_exercises_catalog_has_expected_shape(client):
    response = client.get("/api/exercises")

    assert response.status_code == 200

    data = response.json()

    assert "count" in data
    assert "exercises" in data
    assert isinstance(data["exercises"], list)

    if data["exercises"]:
        exercise = data["exercises"][0]

        for field in (
            "id",
            "name",
            "target_muscle",
            "category",
            "equipment",
            "is_active",
            "weight_increment_kg",
            "progression_type",
            "rep_progression_enabled",
        ):
            assert field in exercise


def test_known_user_exists_in_real_database(real_db_path):
    """
    Este test solamente verifica que el histórico real contiene
    al usuario Pablo. No escribe absolutamente nada en la BD.
    """
    assert real_db_path is not None

    conn = sqlite3.connect(real_db_path)

    row = conn.execute(
        """
        SELECT id, name
        FROM users
        WHERE id = ?
        """,
        ("1effca7d-97cf-41f2-a930-9ce482972f02",),
    ).fetchone()

    conn.close()

    assert row is not None
    assert row[1] == "Pablo"
