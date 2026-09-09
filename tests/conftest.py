import sqlite3
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app import database
from app.auth import create_password_hash


# =========================================================
# IDs estables utilizados por los tests
# =========================================================

PABLO_ID = "1effca7d-97cf-41f2-a930-9ce482972f02"
ESTEFI_ID = "2bf9e2da-6314-46c3-95cd-edbaf1d13b9c9"

EXERCISES = {
    "biceps": (
        "0ea08a73-7904-4237-a0f1-2128800c9343",
        "Curl de bíceps en máquina",
        "Bíceps",
        "brazos",
        "Máquina",
        2.5,
    ),
    "leg_curl": (
        "8ec812d8-af2a-4ca0-975f-553ff3ddfe71",
        "Curl femoral",
        "Isquiosurales",
        "pierna",
        "Máquina",
        2.5,
    ),
    "lateral_raise": (
        "06a20e79-4dbe-42c5-a689-25a36c6aa224",
        "Elevaciones laterales en máquina",
        "Deltoides lateral",
        "hombro",
        "Máquina",
        1.0,
    ),
    "triceps": (
        "b6eeeb90-d0b9-4ef0-acab-f19e2f4983e0",
        "Extensión de tríceps en polea",
        "Tríceps",
        "brazos",
        "Polea",
        2.5,
    ),
    "face_pull": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000001",
        "Face pull",
        "Deltoides posterior y espalda alta",
        "hombro",
        "Polea",
        2.5,
    ),
    "hip_thrust": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000002",
        "Hip thrust",
        "Glúteos",
        "pierna",
        "Barra o máquina",
        5.0,
    ),
    "pulldown": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000003",
        "Jalón al pecho agarre neutro",
        "Dorsal",
        "tirón",
        "Polea",
        2.5,
    ),
    "plank": (
        "0bedcc23-a4ca-4245-89f6-74935f100b46",
        "Plancha",
        "Core",
        "core",
        "Peso corporal",
        0.0,
    ),
    "leg_press": (
        "f7b355b1-4b00-46b7-b768-57d11637e6cc",
        "Prensa de piernas",
        "Cuádriceps y glúteos",
        "pierna",
        "Máquina",
        5.0,
    ),
    "bench": (
        "0dc86cc8-8e33-47e5-adf5-f7f768f50be3",
        "Press banca plano",
        "Pectoral",
        "empuje",
        "Barra",
        2.5,
    ),
    "shoulder_press": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000004",
        "Press de hombro con mancuernas agarre neutro",
        "Deltoides",
        "empuje",
        "Mancuernas",
        2.0,
    ),
    "incline_press": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000005",
        "Press inclinado con mancuernas 30 grados",
        "Pectoral superior",
        "empuje",
        "Mancuernas",
        2.0,
    ),
    "chest_row": (
        "6f1e755d-9874-4c61-a1e8-ef6a0417ac53",
        "Remo con pecho apoyado",
        "Dorsal y espalda media",
        "tirón",
        "Máquina o banco",
        2.5,
    ),
    "unilateral_row": (
        "5c9e5a2b-7c13-4c9e-8d2a-000000000006",
        "Remo unilateral con mancuerna",
        "Dorsal y espalda media",
        "tirón",
        "Mancuerna",
        2.0,
    ),
    "bulgarian": (
        "21314d5b-324c-437c-8eb9-2cd458c21429",
        "Sentadilla búlgara",
        "Cuádriceps y glúteos",
        "unilateral",
        "Mancuernas o peso corporal",
        2.0,
    ),
    "lunges": (
        "74ce1fc4-b7e3-4c28-a483-f680c9706d4e",
        "Zancadas",
        "Cuádriceps y glúteos",
        "unilateral",
        "Mancuernas o peso corporal",
        2.0,
    ),
}

BENCH_ID = EXERCISES["bench"][0]

ROUTINE_A_ID = "67da7730-d791-455e-b63e-85379e7a560d"
ROUTINE_B_ID = "ab7bfa70-ae2d-4067-8fcc-7671d3896320"
ROUTINE_C_ID = "06b5a2d1-0560-4a4b-a738-518f8f6cb742"


# =========================================================
# Rutinas A/B/C
# =========================================================

ROUTINES = {
    "A": [
        ("leg_press", 1, 3, 8, 10, 2, 150),
        ("bench", 2, 3, 6, 8, 2, 150),
        ("chest_row", 3, 3, 8, 10, 2, 120),
        ("leg_curl", 4, 2, 10, 12, 2, 90),
        ("lateral_raise", 5, 3, 12, 15, 2, 75),
        ("biceps", 6, 2, 10, 12, 2, 75),
        ("triceps", 7, 2, 10, 12, 2, 75),
    ],
    "B": [
        ("shoulder_press", 1, 3, 8, 10, 2, 120),
        ("leg_press", 2, 3, 8, 10, 2, 150),
        ("pulldown", 3, 3, 8, 10, 2, 120),
        ("hip_thrust", 4, 3, 8, 10, 2, 120),
        ("face_pull", 5, 3, 12, 15, 2, 75),
        ("lateral_raise", 6, 2, 12, 15, 2, 75),
        ("plank", 7, 2, 30, 60, 2, 60),
    ],
    "C": [
        ("incline_press", 1, 3, 8, 10, 2, 120),
        ("bulgarian", 2, 3, 8, 10, 2, 120),
        ("unilateral_row", 3, 3, 10, 12, 2, 90),
        ("leg_curl", 4, 2, 10, 12, 2, 90),
        ("lateral_raise", 5, 3, 12, 15, 2, 75),
        ("biceps", 6, 2, 10, 12, 2, 75),
        ("triceps", 7, 2, 10, 12, 2, 75),
    ],
}


# =========================================================
# Sustituciones
# =========================================================

SUBSTITUTIONS = [
    ("leg_press", "bulgarian", 1, 1, 1),
    ("leg_press", "lunges", 2, 1, 1),

    ("bulgarian", "leg_press", 1, 1, 1),
    ("bulgarian", "lunges", 1, 1, 1),

    ("lunges", "bulgarian", 1, 1, 1),
    ("lunges", "leg_press", 2, 1, 1),

    ("bench", "incline_press", 1, 1, 1),
    ("incline_press", "bench", 1, 1, 1),

    ("chest_row", "unilateral_row", 1, 1, 1),
    ("chest_row", "pulldown", 3, 1, 0),

    ("unilateral_row", "chest_row", 1, 1, 1),
    ("unilateral_row", "pulldown", 3, 1, 0),

    ("pulldown", "chest_row", 2, 1, 0),

    ("leg_curl", "hip_thrust", 3, 0, 0),
    ("hip_thrust", "leg_curl", 3, 0, 0),

    ("lateral_raise", "shoulder_press", 2, 1, 0),
    ("shoulder_press", "lateral_raise", 2, 1, 0),

    ("biceps", "pulldown", 3, 1, 0),
    ("triceps", "bench", 3, 1, 0),

    ("face_pull", "lateral_raise", 2, 1, 0),
]


# =========================================================
# Fixture
# =========================================================

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """
    SQLite temporal completamente aislada de la BD real.
    """

    db_path = tmp_path / "test_entrenamiento.db"

    monkeypatch.setattr(database, "DB_PATH", db_path)

    database.init_db()

    conn = database.get_connection()

    # -----------------------------------------------------
    # Usuarios
    # -----------------------------------------------------

    conn.executemany(
        """
        INSERT INTO users (id, name, email, role)
        VALUES (?, ?, ?, ?)
        """,
        [
            (PABLO_ID, "Pablo", "pablo@test.local", "admin"),
            (ESTEFI_ID, "Estefi", "estefi@test.local", "user"),
        ],
    )

    # -----------------------------------------------------
    # Credenciales de prueba
    # -----------------------------------------------------

    conn.executemany(
        """
        INSERT INTO user_credentials (
            user_id,
            password_hash,
            updated_at,
            must_change_password
        )
        VALUES (?, ?, datetime('now'), 0)
        """,
        [
            (PABLO_ID, create_password_hash("test-pablo-password")),
            (ESTEFI_ID, create_password_hash("test-estefi-password")),
        ],
    )

    # -----------------------------------------------------
    # Ejercicios
    # -----------------------------------------------------

    for (
        key,
        (
            exercise_id,
            name,
            target_muscle,
            category,
            equipment,
            increment,
        ),
    ) in EXERCISES.items():

        conn.execute(
            """
            INSERT INTO exercises (
                id,
                name,
                target_muscle,
                category,
                equipment,
                safety_notes,
                is_active,
                instructions,
                contraindications,
                weight_increment_kg,
                progression_type,
                rep_progression_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 'reps_then_weight', 1)
            """,
            (
                exercise_id,
                name,
                target_muscle,
                category,
                equipment,
                None,
                None,
                None,
                increment,
            ),
        )

    # -----------------------------------------------------
    # Rutinas
    # -----------------------------------------------------

    routine_ids = {
        "A": ROUTINE_A_ID,
        "B": ROUTINE_B_ID,
        "C": ROUTINE_C_ID,
    }

    for day_order, routine_name in enumerate(("A", "B", "C"), start=1):

        routine_id = routine_ids[routine_name]

        conn.execute(
            """
            INSERT INTO routines (
                id,
                user_id,
                name,
                day_order,
                is_active
            )
            VALUES (?, ?, ?, ?, 1)
            """,
            (
                routine_id,
                PABLO_ID,
                routine_name,
                day_order,
            ),
        )

        for (
            exercise_key,
            exercise_order,
            target_sets,
            rep_min,
            rep_max,
            target_rir,
            rest_seconds,
        ) in ROUTINES[routine_name]:

            exercise_id = EXERCISES[exercise_key][0]

            conn.execute(
                """
                INSERT INTO routine_exercises (
                    id,
                    routine_id,
                    exercise_id,
                    "order",
                    target_sets,
                    target_rep_min,
                    target_rep_max,
                    target_rir,
                    rest_seconds,
                    is_optional
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                """,
                (
                    str(uuid.uuid4()),
                    routine_id,
                    exercise_id,
                    exercise_order,
                    target_sets,
                    rep_min,
                    rep_max,
                    target_rir,
                    rest_seconds,
                ),
            )

    # -----------------------------------------------------
    # Sustituciones
    # -----------------------------------------------------

    for (
        source,
        alternative,
        priority,
        same_muscle,
        same_pattern,
    ) in SUBSTITUTIONS:

        conn.execute(
            """
            INSERT INTO exercise_substitutions (
                id,
                exercise_id,
                alternative_exercise_id,
                priority,
                reason,
                same_muscle,
                same_movement_pattern,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                str(uuid.uuid4()),
                EXERCISES[source][0],
                EXERCISES[alternative][0],
                priority,
                "Alternativa de prueba",
                same_muscle,
                same_pattern,
            ),
        )

    # -----------------------------------------------------
    # Histórico real de Pablo
    # -----------------------------------------------------

    workout_id = "677cd2fc-bf08-40f7-b890-4398b229abbc"

    conn.execute(
        """
        INSERT INTO workout_logs (
            id,
            user_id,
            routine_id,
            date,
            duration_minutes,
            notes,
            status
        )
        VALUES (?, ?, NULL, ?, NULL, ?, 'completed')
        """,
        (
            workout_id,
            PABLO_ID,
            "2026-09-03T18:00:00",
            "Sesión de vuelta al entrenamiento. Histórico inicial.",
        ),
    )

    historical_sets = [
        (1, BENCH_ID, 35.0, 8, 2, 0, None),
        (2, BENCH_ID, 35.0, 8, 2, 0, None),
        (3, BENCH_ID, 35.0, 8, 2, 0, None),

        (4, EXERCISES["chest_row"][0], 45.0, 8, 3, 0, None),
        (5, EXERCISES["chest_row"][0], 45.0, 8, 3, 0, None),
        (6, EXERCISES["chest_row"][0], 45.0, 8, 3, 0, None),

        (1, EXERCISES["lateral_raise"][0], 10.0, 12, None, 0,
         "15 kg generaba mucha tensión cervical; 10 kg fue mucho más cómodo."),
        (2, EXERCISES["lateral_raise"][0], 10.0, 12, None, 0, None),
        (3, EXERCISES["lateral_raise"][0], 10.0, 12, None, 0, None),

        (1, EXERCISES["biceps"][0], 15.0, 15, None, 1, None),
        (2, EXERCISES["biceps"][0], 17.5, 12, 2, 0, None),

        (1, EXERCISES["triceps"][0], 11.25, 15, None, 1, None),
        (2, EXERCISES["triceps"][0], 13.75, 12, 2, 0, None),

        (1, EXERCISES["plank"][0], 0.0, 60, None, 0, "60 segundos"),
        (2, EXERCISES["plank"][0], 0.0, 45, None, 0, "45 segundos"),
    ]

    for (
        set_number,
        exercise_id,
        weight,
        reps,
        rir,
        is_warmup,
        notes,
    ) in historical_sets:

        conn.execute(
            """
            INSERT INTO workout_sets (
                id,
                workout_log_id,
                exercise_id,
                set_number,
                weight_kg,
                reps,
                rir,
                is_warmup,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                workout_id,
                exercise_id,
                set_number,
                weight,
                reps,
                rir,
                is_warmup,
                notes,
            ),
        )

    conn.commit()
    conn.close()

    return db_path


def _login_client(test_client, name, password):
    response = test_client.post(
        "/api/auth/login",
        json={
            "name": name,
            "password": password,
        },
    )

    assert response.status_code == 200, response.text

    data = response.json()
    assert data["must_change_password"] is False

    csrf_token = test_client.cookies.get("entrenamiento_csrf")
    assert csrf_token, "El login no creó la cookie CSRF"

    test_client.headers.update({
        "X-CSRF-Token": csrf_token,
    })

    return test_client


@pytest.fixture
def client_pablo(test_db):
    """
    Cliente autenticado como Pablo (admin).
    """
    with TestClient(app) as test_client:
        yield _login_client(
            test_client,
            "Pablo",
            "test-pablo-password",
        )


@pytest.fixture
def client_estefi(test_db):
    """
    Cliente autenticado como Estefi (user).
    """
    with TestClient(app) as test_client:
        yield _login_client(
            test_client,
            "Estefi",
            "test-estefi-password",
        )


@pytest.fixture
def client(client_pablo):
    """
    Compatibilidad: los tests existentes utilizan Pablo.
    """
    return client_pablo


@pytest.fixture
def real_db_path():
    """
    Ruta de la BD real, solo para el smoke test de lectura.
    """
    candidates = [
        Path("/opt/entrenamiento/data/entrenamiento.db"),
        Path("/opt/entrenamiento/entrenamiento.db"),
        Path("/opt/entrenamiento/app/entrenamiento.db"),
    ]

    for path in candidates:
        if path.exists():
            return path

    return None
