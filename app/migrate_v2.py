from database import get_connection


def migrate() -> None:
    conn = get_connection()

    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(exercises)").fetchall()
    }

    if "instructions" not in columns:
        conn.execute(
            "ALTER TABLE exercises ADD COLUMN instructions TEXT"
        )
        print("Añadida columna: instructions")

    if "contraindications" not in columns:
        conn.execute(
            "ALTER TABLE exercises ADD COLUMN contraindications TEXT"
        )
        print("Añadida columna: contraindications")

    conn.commit()

    print("\nEstructura actual de exercises:")
    rows = conn.execute(
        "PRAGMA table_info(exercises)"
    ).fetchall()

    for row in rows:
        print(f"  {row['name']} | {row['type']}")

    conn.close()


if __name__ == "__main__":
    migrate()
