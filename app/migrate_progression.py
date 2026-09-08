from database import get_connection


def column_exists(conn, table, column):
    row = conn.execute(
        f"PRAGMA table_info({table})"
    ).fetchall()

    return any(r["name"] == column for r in row)


def main():
    conn = get_connection()

    if not column_exists(conn, "exercises", "weight_increment_kg"):
        conn.execute(
            "ALTER TABLE exercises ADD COLUMN weight_increment_kg DECIMAL"
        )
        print("Añadida columna: weight_increment_kg")
    else:
        print("Ya existe: weight_increment_kg")

    if not column_exists(conn, "exercises", "progression_type"):
        conn.execute(
            "ALTER TABLE exercises ADD COLUMN progression_type TEXT"
        )
        print("Añadida columna: progression_type")
    else:
        print("Ya existe: progression_type")

    if not column_exists(conn, "exercises", "rep_progression_enabled"):
        conn.execute(
            "ALTER TABLE exercises ADD COLUMN rep_progression_enabled BOOLEAN"
        )
        print("Añadida columna: rep_progression_enabled")
    else:
        print("Ya existe: rep_progression_enabled")

    # Valores por defecto para los ejercicios existentes.
    conn.execute(
        """
        UPDATE exercises
        SET progression_type = 'reps_then_weight'
        WHERE progression_type IS NULL
        """
    )

    conn.execute(
        """
        UPDATE exercises
        SET rep_progression_enabled = 1
        WHERE rep_progression_enabled IS NULL
        """
    )

    # Configuración inicial específica.
    increments = {
        "Press banca plano": 2.5,
        "Remo con pecho apoyado": 2.5,
        "Prensa de piernas": 5.0,
        "Curl femoral": 2.5,
        "Elevaciones laterales en máquina": 1.0,
        "Curl de bíceps en máquina": 2.5,
        "Extensión de tríceps en polea": 2.5,
        "Press de hombro con mancuernas agarre neutro": 2.0,
        "Jalón al pecho agarre neutro": 2.5,
        "Hip thrust": 5.0,
        "Face pull": 2.5,
        "Press inclinado con mancuernas 30 grados": 2.0,
        "Remo unilateral con mancuerna": 2.0,
        "Sentadilla búlgara": 2.0,
        "Zancadas": 2.0,
        "Plancha": 0.0,
    }

    for exercise_name, increment in increments.items():
        conn.execute(
            """
            UPDATE exercises
            SET weight_increment_kg = ?
            WHERE name = ?
            """,
            (increment, exercise_name),
        )

    conn.commit()

    print("\nConfiguración de progresión:")
    rows = conn.execute(
        """
        SELECT
            name,
            equipment,
            weight_increment_kg,
            progression_type,
            rep_progression_enabled
        FROM exercises
        WHERE is_active = 1
        ORDER BY name
        """
    ).fetchall()

    for row in rows:
        print(
            f"{row['name']} | "
            f"{row['equipment']} | "
            f"+{row['weight_increment_kg']} kg | "
            f"{row['progression_type']} | "
            f"reps={row['rep_progression_enabled']}"
        )

    conn.close()


if __name__ == "__main__":
    main()
