import sqlite3
from pathlib import Path
import uuid

DB_PATH = Path("data/entrenamiento.db")

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA foreign_keys = ON")

# ---------------------------------------------------------
# 1. Crear tabla de sustituciones
# ---------------------------------------------------------

conn.execute("""
CREATE TABLE IF NOT EXISTS exercise_substitutions (
    id UUID PRIMARY KEY,
    exercise_id UUID NOT NULL,
    alternative_exercise_id UUID NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    same_muscle BOOLEAN NOT NULL DEFAULT 0,
    same_movement_pattern BOOLEAN NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exercise_id) REFERENCES exercises(id),
    FOREIGN KEY (alternative_exercise_id) REFERENCES exercises(id),
    UNIQUE (exercise_id, alternative_exercise_id)
)
""")

# ---------------------------------------------------------
# 2. IDs de ejercicios
# ---------------------------------------------------------

EX = {
    "biceps": "0ea08a73-7904-4237-a0f1-2128800c9343",
    "leg_curl": "8ec812d8-af2a-4ca0-975f-553ff3ddfe71",
    "lateral_raise": "06a20e79-4dbe-42c5-a689-25a36c6aa224",
    "triceps": "b6eeeb90-d0b9-4ef0-acab-f19e2f4983e0",
    "face_pull": "TODO_FACE_PULL",
    "hip_thrust": "TODO_HIP_THRUST",
    "pulldown": "TODO_PULLDOWN",
    "plank": "0bedcc23-a4ca-4245-89f6-74935f100b46",
    "leg_press": "f7b355b1-4b00-46b7-b768-57d11637e6cc",
    "bench": "0dc86cc8-8e33-47e5-adf5-f7f768f50be3",
    "shoulder_press": "TODO_SHOULDER_PRESS",
    "incline_press": "TODO_INCLINE_PRESS",
    "chest_row": "6f1e755d-9874-4c61-a1e8-ef6a0417ac53",
    "unilateral_row": "TODO_UNILATERAL_ROW",
    "bulgarian": "TODO_BULGARIAN",
    "lunges": "TODO_LUNGES",
}

# ---------------------------------------------------------
# 3. Resolver automáticamente los IDs que no tenemos
# ---------------------------------------------------------

names = {
    "face_pull": "Face pull",
    "hip_thrust": "Hip thrust",
    "pulldown": "Jalón al pecho agarre neutro",
    "shoulder_press": "Press de hombro con mancuernas agarre neutro",
    "incline_press": "Press inclinado con mancuernas 30 grados",
    "unilateral_row": "Remo unilateral con mancuerna",
    "bulgarian": "Sentadilla búlgara",
    "lunges": "Zancadas",
}

for key, name in names.items():
    row = conn.execute(
        "SELECT id FROM exercises WHERE name = ?",
        (name,)
    ).fetchone()

    if not row:
        raise RuntimeError(f"No se encontró el ejercicio: {name}")

    EX[key] = row[0]

# ---------------------------------------------------------
# 4. Sustituciones
#
# priority 1 = alternativa más parecida
# priority 2 = buena alternativa
# priority 3 = alternativa más alejada
# ---------------------------------------------------------

substitutions = [

    # PRENSA
    ("leg_press", "bulgarian", 1,
     "Mismo énfasis principal en cuádriceps y glúteos; alternativa unilateral.",
     1, 1),

    ("leg_press", "lunges", 2,
     "Alternativa unilateral para cuádriceps y glúteos.",
     1, 1),

    # SENTADILLA BÚLGARA
    ("bulgarian", "leg_press", 1,
     "Mismo énfasis principal en cuádriceps y glúteos.",
     1, 1),

    ("bulgarian", "lunges", 1,
     "Mismo patrón unilateral y musculatura principal.",
     1, 1),

    # ZANCADAS
    ("lunges", "bulgarian", 1,
     "Mismo patrón unilateral y musculatura principal.",
     1, 1),

    ("lunges", "leg_press", 2,
     "Alternativa bilateral para cuádriceps y glúteos.",
     1, 1),

    # PRESS BANCA
    ("bench", "incline_press", 1,
     "Mismo patrón de empuje y musculatura principal; cambia el ángulo.",
     1, 1),

    # PRESS INCLINADO
    ("incline_press", "bench", 1,
     "Mismo patrón de empuje y musculatura principal.",
     1, 1),

    # REMO PECHO APOYADO
    ("chest_row", "unilateral_row", 1,
     "Mismo patrón de tirón horizontal y musculatura principal.",
     1, 1),

    ("chest_row", "pulldown", 3,
     "Alternativa de tirón para espalda, aunque cambia a tirón vertical.",
     1, 0),

    # REMO UNILATERAL
    ("unilateral_row", "chest_row", 1,
     "Mismo patrón de tirón horizontal y musculatura principal.",
     1, 1),

    ("unilateral_row", "pulldown", 3,
     "Alternativa de tirón para espalda, aunque cambia a tirón vertical.",
     1, 0),

    # JALÓN
    ("pulldown", "chest_row", 2,
     "Alternativa de tirón para dorsal y espalda, aunque cambia el patrón.",
     1, 0),

    # CURL FEMORAL
    ("leg_curl", "hip_thrust", 3,
     "Alternativa para cadena posterior, aunque cambia el énfasis hacia glúteos.",
     0, 0),

    # HIP THRUST
    ("hip_thrust", "leg_curl", 3,
     "Alternativa para cadena posterior, aunque cambia el énfasis hacia isquiosurales.",
     0, 0),

    # ELEVACIONES LATERALES
    ("lateral_raise", "shoulder_press", 2,
     "Alternativa para deltoides, aunque incorpora más deltoides anterior y tríceps.",
     1, 0),

    # PRESS HOMBRO
    ("shoulder_press", "lateral_raise", 2,
     "Alternativa para deltoides, aunque con menor componente de empuje.",
     1, 0),

    # BÍCEPS
    ("biceps", "pulldown", 3,
     "El jalón también implica fuertemente el bíceps, aunque no es un aislamiento.",
     1, 0),

    # TRÍCEPS
    ("triceps", "bench", 3,
     "El press banca implica fuertemente el tríceps, aunque no es un aislamiento.",
     1, 0),

    # FACE PULL
    ("face_pull", "lateral_raise", 2,
     "Alternativa para trabajo del hombro, aunque cambia el énfasis muscular.",
     1, 0),
]

for source, alternative, priority, reason, same_muscle, same_pattern in substitutions:
    conn.execute("""
        INSERT OR IGNORE INTO exercise_substitutions (
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
    """, (
        str(uuid.uuid4()),
        EX[source],
        EX[alternative],
        priority,
        reason,
        same_muscle,
        same_pattern,
    ))

conn.commit()

print("Tabla exercise_substitutions creada/configurada.")
print(
    "Sustituciones activas:",
    conn.execute(
        "SELECT COUNT(*) FROM exercise_substitutions WHERE is_active = 1"
    ).fetchone()[0]
)

conn.close()
