from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "entrenamiento.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS exercises (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_muscle TEXT,
            category TEXT,
            equipment TEXT,
            safety_notes TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS routines (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            day_order INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS routine_exercises (
            id TEXT PRIMARY KEY,
            routine_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            "order" INTEGER NOT NULL,
            target_sets INTEGER NOT NULL,
            target_rep_min INTEGER NOT NULL,
            target_rep_max INTEGER NOT NULL,
            target_rir INTEGER,
            rest_seconds INTEGER,
            is_optional INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (routine_id) REFERENCES routines(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id),
            UNIQUE (routine_id, exercise_id, "order")
        );

        CREATE TABLE IF NOT EXISTS workout_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            routine_id TEXT,
            date TEXT NOT NULL,
            duration_minutes INTEGER,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress',
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (routine_id) REFERENCES routines(id),
            CHECK (status IN ('in_progress', 'completed', 'cancelled'))
        );

        CREATE TABLE IF NOT EXISTS workout_sets (
            id TEXT PRIMARY KEY,
            workout_log_id TEXT NOT NULL,
            exercise_id TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            weight_kg REAL NOT NULL,
            reps INTEGER NOT NULL,
            rir INTEGER,
            is_warmup INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            FOREIGN KEY (workout_log_id) REFERENCES workout_logs(id),
            FOREIGN KEY (exercise_id) REFERENCES exercises(id),
            UNIQUE (workout_log_id, exercise_id, set_number)
        );

        CREATE TABLE IF NOT EXISTS body_metrics (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            weight_kg REAL NOT NULL,
            notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (user_id, date)
        );

        CREATE INDEX IF NOT EXISTS idx_routines_user
            ON routines(user_id);

        CREATE INDEX IF NOT EXISTS idx_routine_exercises_routine
            ON routine_exercises(routine_id, "order");

        CREATE INDEX IF NOT EXISTS idx_workout_logs_user_date
            ON workout_logs(user_id, date DESC);

        CREATE INDEX IF NOT EXISTS idx_workout_sets_exercise
            ON workout_sets(exercise_id, workout_log_id);

        CREATE INDEX IF NOT EXISTS idx_body_metrics_user_date
            ON body_metrics(user_id, date DESC);
        """
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada: {DB_PATH}")
