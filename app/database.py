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
            role TEXT NOT NULL DEFAULT 'user',
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
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            instructions TEXT,
            contraindications TEXT,
            weight_increment_kg DECIMAL,
            progression_type TEXT DEFAULT 'reps_then_weight',
            rep_progression_enabled BOOLEAN DEFAULT 1
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

        CREATE TABLE IF NOT EXISTS exercise_substitutions (
            id TEXT PRIMARY KEY,
            exercise_id TEXT NOT NULL,
            alternative_exercise_id TEXT NOT NULL,
            priority INTEGER NOT NULL DEFAULT 1,
            reason TEXT,
            same_muscle BOOLEAN NOT NULL DEFAULT 0,
            same_movement_pattern BOOLEAN NOT NULL DEFAULT 0,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id),
            FOREIGN KEY (alternative_exercise_id) REFERENCES exercises(id),
            UNIQUE (exercise_id, alternative_exercise_id)
        );

        CREATE TABLE IF NOT EXISTS workout_exercise_substitutions (
            id TEXT PRIMARY KEY,
            workout_log_id TEXT NOT NULL,
            original_exercise_id TEXT NOT NULL,
            substitute_exercise_id TEXT NOT NULL,
            reason TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (workout_log_id)
                REFERENCES workout_logs(id) ON DELETE CASCADE,
            FOREIGN KEY (original_exercise_id)
                REFERENCES exercises(id),
            FOREIGN KEY (substitute_exercise_id)
                REFERENCES exercises(id),
            UNIQUE (workout_log_id, original_exercise_id)
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

        CREATE TABLE IF NOT EXISTS body_measurements (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            waist_cm REAL,
            chest_cm REAL,
            arm_left_cm REAL,
            arm_right_cm REAL,
            thigh_left_cm REAL,
            thigh_right_cm REAL,
            hip_cm REAL,
            neck_cm REAL,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (user_id, date)
        );

        CREATE TABLE IF NOT EXISTS body_photos (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            date TEXT NOT NULL,
            month_key TEXT NOT NULL,
            angle TEXT NOT NULL,
            file_path TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE (user_id, month_key, angle)
        );

        CREATE TABLE IF NOT EXISTS user_goals (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            target_date TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS progress_notes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            workout_log_id TEXT,
            date TEXT NOT NULL,
            energy INTEGER,
            satisfaction INTEGER,
            effort INTEGER,
            motivation INTEGER,
            recovery INTEGER,
            soreness INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (workout_log_id)
                REFERENCES workout_logs(id)
                ON DELETE SET NULL
        );

        CREATE INDEX IF NOT EXISTS idx_body_measurements_user_date
            ON body_measurements(user_id, date DESC);

        CREATE INDEX IF NOT EXISTS idx_body_photos_user_month
            ON body_photos(user_id, month_key);

        CREATE INDEX IF NOT EXISTS idx_user_goals_user_active
            ON user_goals(user_id, is_active);

        CREATE UNIQUE INDEX IF NOT EXISTS idx_progress_notes_workout
            ON progress_notes(user_id, workout_log_id)
            WHERE workout_log_id IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_exercise_substitutions_exercise
            ON exercise_substitutions(exercise_id, priority);

        CREATE INDEX IF NOT EXISTS idx_workout_substitutions_workout
            ON workout_exercise_substitutions(workout_log_id);
        CREATE TABLE IF NOT EXISTS user_credentials (
            user_id TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            must_change_password INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS auth_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE INDEX IF NOT EXISTS idx_auth_sessions_token_hash
            ON auth_sessions(token_hash);

        CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id
            ON auth_sessions(user_id);

        CREATE INDEX IF NOT EXISTS idx_auth_sessions_expires_at
            ON auth_sessions(expires_at);
        """
    )

    # Compatibilidad con bases de datos creadas con versiones
    # anteriores del esquema.
    exercise_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(exercises)").fetchall()
    }

    missing_columns = [
        (
            "instructions",
            "ALTER TABLE exercises ADD COLUMN instructions TEXT",
        ),
        (
            "contraindications",
            "ALTER TABLE exercises ADD COLUMN contraindications TEXT",
        ),
        (
            "weight_increment_kg",
            "ALTER TABLE exercises ADD COLUMN weight_increment_kg DECIMAL",
        ),
        (
            "progression_type",
            "ALTER TABLE exercises ADD COLUMN progression_type TEXT",
        ),
        (
            "rep_progression_enabled",
            "ALTER TABLE exercises ADD COLUMN rep_progression_enabled BOOLEAN",
        ),
    ]

    for column_name, statement in missing_columns:
        if column_name not in exercise_columns:
            conn.execute(statement)

    # Compatibilidad con bases de datos creadas antes de
    # la ampliación de body_metrics para composición corporal.
    body_metric_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(body_metrics)").fetchall()
    }

    body_metric_missing_columns = [
        (
            "body_fat_pct",
            "ALTER TABLE body_metrics ADD COLUMN body_fat_pct REAL",
        ),
        (
            "muscle_mass_kg",
            "ALTER TABLE body_metrics ADD COLUMN muscle_mass_kg REAL",
        ),
        (
            "water_pct",
            "ALTER TABLE body_metrics ADD COLUMN water_pct REAL",
        ),
        (
            "visceral_fat",
            "ALTER TABLE body_metrics ADD COLUMN visceral_fat REAL",
        ),
        (
            "basal_metabolic_rate_kcal",
            "ALTER TABLE body_metrics ADD COLUMN basal_metabolic_rate_kcal REAL",
        ),
        (
            "bone_mass_kg",
            "ALTER TABLE body_metrics ADD COLUMN bone_mass_kg REAL",
        ),
    ]

    for column_name, statement in body_metric_missing_columns:
        if column_name not in body_metric_columns:
            conn.execute(statement)

    # Valores por defecto para ejercicios existentes.
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

    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print(f"Base de datos inicializada: {DB_PATH}")
