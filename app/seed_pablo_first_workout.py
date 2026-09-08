import uuid

from database import get_connection


PABLO_ID = "1effca7d-97cf-41f2-a930-9ce482972f02"
WORKOUT_DATE = "2026-09-03T18:00:00"


EXERCISES = {
    "press_banca": "0dc86cc8-8e33-47e5-adf5-f7f768f50be3",
    "remo_pecho": "6f1e755d-9874-4c61-a1e8-ef6a0417ac53",
    "elevaciones": "06a20e79-4dbe-42c5-a689-25a36c6aa224",
    "biceps": "0ea08a73-7904-4237-a0f1-2128800c9343",
    "triceps": "b6eeeb90-d0b9-4ef0-acab-f19e2f4983e0",
    "plancha": "0bedcc23-a4ca-4245-89f6-74935f100b46",
}


SETS = [
    # Press banca: 35 kg x 8 x 3, RIR 2
    ("press_banca", 1, 35.0, 8, 2, 0, None),
    ("press_banca", 2, 35.0, 8, 2, 0, None),
    ("press_banca", 3, 35.0, 8, 2, 0, None),

    # Remo pecho apoyado: 45 kg x 8 x 3, RIR 3
    ("remo_pecho", 1, 45.0, 8, 3, 0, None),
    ("remo_pecho", 2, 45.0, 8, 3, 0, None),
    ("remo_pecho", 3, 45.0, 8, 3, 0, None),

    # Elevaciones laterales: 10 kg x 12 x 3
    ("elevaciones", 1, 10.0, 12, None, 0,
     "15 kg generaba mucha tensión cervical; 10 kg fue mucho más cómodo."),
    ("elevaciones", 2, 10.0, 12, None, 0, None),
    ("elevaciones", 3, 10.0, 12, None, 0, None),

    # Bíceps: datos conocidos
    ("biceps", 1, 15.0, 15, None, 0, None),
    ("biceps", 2, 17.5, 12, 2, 0, None),

    # Tríceps: datos conocidos
    ("triceps", 1, 11.25, 15, None, 0, None),
    ("triceps", 2, 13.75, 12, 2, 0, None),

    # Plancha: 60 s + 45 s
    ("plancha", 1, 0.0, 60, None, 0, "60 segundos"),
    ("plancha", 2, 0.0, 45, None, 0, "45 segundos"),
]


def main():
    conn = get_connection()

    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (PABLO_ID,),
    ).fetchone()

    if user is None:
        raise ValueError("No se encontró a Pablo.")

    # Evitar crear el histórico dos veces si se ejecuta accidentalmente.
    existing = conn.execute(
        """
        SELECT id
        FROM workout_logs
        WHERE user_id = ?
          AND date = ?
          AND notes = ?
        """,
        (
            PABLO_ID,
            WORKOUT_DATE,
            "Sesión de vuelta al entrenamiento. Histórico inicial.",
        ),
    ).fetchone()

    if existing:
        print(f"La sesión ya existe: {existing['id']}")
        conn.close()
        return

    workout_id = str(uuid.uuid4())

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
        VALUES (?, ?, NULL, ?, ?, ?, 'completed')
        """,
        (
            workout_id,
            PABLO_ID,
            WORKOUT_DATE,
            None,
            "Sesión de vuelta al entrenamiento. Histórico inicial.",
        ),
    )

    for (
        exercise_key,
        set_number,
        weight_kg,
        reps,
        rir,
        is_warmup,
        notes,
    ) in SETS:
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
                EXERCISES[exercise_key],
                set_number,
                weight_kg,
                reps,
                rir,
                is_warmup,
                notes,
            ),
        )

    conn.commit()

    print(f"Entrenamiento creado: {workout_id}")
    print(f"Fecha: {WORKOUT_DATE}")
    print(f"Series registradas: {len(SETS)}")

    conn.close()


if __name__ == "__main__":
    main()
