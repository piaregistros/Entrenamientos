import uuid

from database import get_connection


def seed_users() -> None:
    conn = get_connection()

    users = [
        (str(uuid.uuid4()), "Pablo", None),
        (str(uuid.uuid4()), "Estefi", None),
    ]

    for user_id, name, email in users:
        existing = conn.execute(
            "SELECT id FROM users WHERE name = ?",
            (name,),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO users (id, name, email)
                VALUES (?, ?, ?)
                """,
                (user_id, name, email),
            )

    conn.commit()

    print("Usuarios:")
    rows = conn.execute(
        "SELECT id, name, email FROM users ORDER BY name"
    ).fetchall()

    for row in rows:
        print(f"  {row['id']} | {row['name']} | {row['email']}")

    conn.close()


if __name__ == "__main__":
    seed_users()
