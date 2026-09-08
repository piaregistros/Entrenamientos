import uuid

from database import get_connection


PABLO_ID = "1effca7d-97cf-41f2-a930-9ce482972f02"


ROUTINES = {
    "A": [
        ("Prensa de piernas", 1, 3, 8, 10, 2, 150, 0),
        ("Press banca plano", 2, 3, 6, 8, 2, 150, 0),
        ("Remo con pecho apoyado", 3, 3, 8, 10, 2, 120, 0),
        ("Curl femoral", 4, 2, 10, 12, 2, 90, 0),
        ("Elevaciones laterales en máquina", 5, 3, 12, 15, 2, 75, 0),
        ("Curl de bíceps en máquina", 6, 2, 10, 12, 2, 75, 0),
        ("Extensión de tríceps en polea", 7, 2, 10, 12, 2, 75, 0),
    ],
    "B": [
        ("Press de hombro con mancuernas agarre neutro", 1, 3, 8, 10, 2, 120, 0),
        ("Prensa de piernas", 2, 3, 8, 10, 2, 150, 0),
        ("Jalón al pecho agarre neutro", 3, 3, 8, 10, 2, 120, 0),
        ("Hip thrust", 4, 3, 8, 10, 2, 120, 0),
        ("Face pull", 5, 3, 12, 15, 2, 75, 0),
        ("Elevaciones laterales en máquina", 6, 2, 12, 15, 2, 75, 0),
        ("Plancha", 7, 2, 30, 60, 2, 60, 0),
    ],
    "C": [
        ("Press inclinado con mancuernas 30 grados", 1, 3, 8, 10, 2, 120, 0),
        ("Sentadilla búlgara", 2, 3, 8, 10, 2, 120, 0),
        ("Remo unilateral con mancuerna", 3, 3, 10, 12, 2, 90, 0),
        ("Curl femoral", 4, 2, 10, 12, 2, 90, 0),
        ("Elevaciones laterales en máquina", 5, 3, 12, 15, 2, 75, 0),
        ("Curl de bíceps en máquina", 6, 2, 10, 12, 2, 75, 0),
        ("Extensión de tríceps en polea", 7, 2, 10, 12, 2, 75, 0),
    ],
}


def get_exercise_ids(conn):
    rows = conn.execute(
        "SELECT id, name FROM exercises"
    ).fetchall()

    return {row["name"]: row["id"] for row in rows}


def routine_exists(conn, name):
    return conn.execute(
        """
        SELECT id
        FROM routines
        WHERE user_id = ? AND name = ?
        """,
        (PABLO_ID, name),
    ).fetchone()


def seed_routine(conn, name, day_order, exercises, exercise_ids):
    existing = routine_exists(conn, name)

    if existing:
        routine_id = existing["id"]
        print(f"Rutina {name}: ya existe ({routine_id})")
        return

    routine_id = str(uuid.uuid4())

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
            name,
            day_order,
        ),
    )

    for (
        exercise_name,
        order,
        target_sets,
        rep_min,
        rep_max,
        target_rir,
        rest_seconds,
        is_optional,
    ) in exercises:

        exercise_id = exercise_ids.get(exercise_name)

        if exercise_id is None:
            raise ValueError(
                f"No se encontró el ejercicio: {exercise_name}"
            )

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
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                routine_id,
                exercise_id,
                order,
                target_sets,
                rep_min,
                rep_max,
                target_rir,
                rest_seconds,
                is_optional,
            ),
        )

    print(f"Rutina {name}: creada ({routine_id})")


def main():
    conn = get_connection()

    user = conn.execute(
        "SELECT id, name FROM users WHERE id = ?",
        (PABLO_ID,),
    ).fetchone()

    if user is None:
        raise ValueError("No se encontró el usuario Pablo.")

    exercise_ids = get_exercise_ids(conn)

    for day_order, name in enumerate(("A", "B", "C"), start=1):
        seed_routine(
            conn,
            name,
            day_order,
            ROUTINES[name],
            exercise_ids,
        )

    conn.commit()

    print("\nRutinas de Pablo:")
    rows = conn.execute(
        """
        SELECT
            r.name AS routine,
            re."order" AS exercise_order,
            e.name AS exercise,
            re.target_sets,
            re.target_rep_min,
            re.target_rep_max,
            re.target_rir,
            re.rest_seconds
        FROM routines r
        JOIN routine_exercises re
            ON re.routine_id = r.id
        JOIN exercises e
            ON e.id = re.exercise_id
        WHERE r.user_id = ?
          AND r.is_active = 1
        ORDER BY r.day_order, re."order"
        """,
        (PABLO_ID,),
    ).fetchall()

    current = None

    for row in rows:
        if row["routine"] != current:
            current = row["routine"]
            print(f"\n--- Rutina {current} ---")

        print(
            f"{row['exercise_order']}. "
            f"{row['exercise']} | "
            f"{row['target_sets']}x"
            f"{row['target_rep_min']}-"
            f"{row['target_rep_max']} | "
            f"RIR {row['target_rir']} | "
            f"descanso {row['rest_seconds']}s"
        )

    conn.close()


if __name__ == "__main__":
    main()
