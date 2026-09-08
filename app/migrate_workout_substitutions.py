import sqlite3
import uuid
from pathlib import Path

DB_PATH = Path("data/entrenamiento.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

conn.execute("""
CREATE TABLE IF NOT EXISTS workout_exercise_substitutions (
    id UUID PRIMARY KEY,
    workout_log_id UUID NOT NULL,
    original_exercise_id UUID NOT NULL,
    substitute_exercise_id UUID NOT NULL,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (workout_log_id) REFERENCES workout_logs(id) ON DELETE CASCADE,
    FOREIGN KEY (original_exercise_id) REFERENCES exercises(id),
    FOREIGN KEY (substitute_exercise_id) REFERENCES exercises(id),

    UNIQUE (workout_log_id, original_exercise_id)
)
""")

conn.commit()

print("Tabla workout_exercise_substitutions creada/configurada.")
print(
    "Registros actuales:",
    conn.execute(
        "SELECT COUNT(*) FROM workout_exercise_substitutions"
    ).fetchone()[0]
)

conn.close()
