from pathlib import Path
import sqlite3

DB_PATH = Path("data/entrenamiento.db")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")

print("Base de datos:", DB_PATH)

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS user_credentials (
        user_id TEXT PRIMARY KEY,
        password_hash TEXT NOT NULL,
        updated_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """
)

conn.execute(
    """
    CREATE TABLE IF NOT EXISTS auth_sessions (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        created_at TIMESTAMP NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        revoked_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """
)

conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
    ON auth_sessions(token_hash)
    """
)

conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
    ON auth_sessions(user_id)
    """
)

conn.execute(
    """
    CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at
    ON auth_sessions(expires_at)
    """
)

conn.execute(
    """
    UPDATE users
    SET role = "user"
    WHERE role IS NULL OR role NOT IN ("admin", "user")
    """
)

conn.execute(
    "UPDATE users SET role = ? WHERE name = ?",
    ("admin", "Pablo"),
)

conn.execute(
    "UPDATE users SET role = ? WHERE name = ?",
    ("user", "Estefi"),
)

conn.commit()

print()
print("=== USUARIOS ===")

for row in conn.execute(
    "SELECT id, name, role FROM users ORDER BY name"
):
    print(f"{row['name']} -> {row['role']}")

print()
print("=== TABLAS DE AUTENTICACIÓN ===")

for name in ("user_credentials", "auth_sessions"):
    exists = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = "table" AND name = ?
        """,
        (name,),
    ).fetchone()

    print(f"{name}: {'OK' if exists else 'ERROR'}")

print()
print("=== INTEGRIDAD ===")
print(
    "integrity_check:",
    conn.execute("PRAGMA integrity_check").fetchone()[0],
)
print(
    "foreign_key_check:",
    conn.execute("PRAGMA foreign_key_check").fetchall(),
)

conn.close()
