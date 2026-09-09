from pathlib import Path
import sqlite3


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "entrenamiento.db"


def column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def migrate() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        # ============================================================
        # 1. AMPLIAR body_metrics EXISTENTE
        # ============================================================
        body_metric_columns = [
            ("body_fat_pct", "REAL"),
            ("muscle_mass_kg", "REAL"),
            ("water_pct", "REAL"),
            ("visceral_fat", "REAL"),
            ("basal_metabolic_rate_kcal", "REAL"),
            ("bone_mass_kg", "REAL"),
        ]

        for column_name, column_type in body_metric_columns:
            if not column_exists(conn, "body_metrics", column_name):
                conn.execute(
                    f"ALTER TABLE body_metrics ADD COLUMN "
                    f"{column_name} {column_type}"
                )

        # ============================================================
        # 2. MEDICIONES CORPORALES MANUALES
        # ============================================================
        conn.execute(
            """
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
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_body_measurements_user_date
            ON body_measurements(user_id, date DESC)
            """
        )

        # ============================================================
        # 3. FOTOS DE EVOLUCIÓN CORPORAL
        # ============================================================
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS body_photos (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                date TEXT NOT NULL,
                month_key TEXT NOT NULL,
                angle TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                UNIQUE (user_id, month_key, angle),
                CHECK (angle IN ('front', 'side', 'back'))
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_body_photos_user_month
            ON body_photos(user_id, month_key DESC)
            """
        )

        # ============================================================
        # 4. OBJETIVOS
        # ============================================================
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_goals (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                start_date TEXT NOT NULL,
                target_date TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                CHECK (
                    goal_type IN (
                        'muscle_gain',
                        'strength',
                        'fat_loss',
                        'maintenance',
                        'other'
                    )
                )
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_goals_user_active
            ON user_goals(user_id, is_active, start_date DESC)
            """
        )

        # ============================================================
        # 5. DIARIO FLEXIBLE DE PROGRESO
        # ============================================================
        conn.execute(
            """
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
                    ON DELETE SET NULL,
                CHECK (energy IS NULL OR energy BETWEEN 1 AND 5),
                CHECK (satisfaction IS NULL OR satisfaction BETWEEN 1 AND 5),
                CHECK (effort IS NULL OR effort BETWEEN 1 AND 5),
                CHECK (motivation IS NULL OR motivation BETWEEN 1 AND 5),
                CHECK (recovery IS NULL OR recovery BETWEEN 1 AND 5),
                CHECK (soreness IS NULL OR soreness BETWEEN 1 AND 5)
            )
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_progress_notes_user_date
            ON progress_notes(user_id, date DESC)
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_progress_notes_workout
            ON progress_notes(workout_log_id)
            """
        )

        # Una sola nota por entrenamiento.
        # Las notas independientes (workout_log_id NULL) pueden coexistir.
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_progress_notes_workout_unique
            ON progress_notes(user_id, workout_log_id)
            WHERE workout_log_id IS NOT NULL
            """
        )

        conn.commit()

        print(f"Migración completada correctamente: {DB_PATH}")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
