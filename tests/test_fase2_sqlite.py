"""Fase 2: SQLite estable (WAL, busy_timeout, sin DDL en GET) y migración de 'expired'."""
import sqlite3
import threading
import time

import pytest

from conftest import PABLO_ID
from app import database
from app.database import (
    get_connection,
    init_db,
    migrate_workout_logs_allow_expired,
    workout_logs_needs_expired_migration,
)

LEGACY_WORKOUT_LOGS = """
CREATE TABLE workout_logs (
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
)
"""


def _legacy_db(path, rows=3):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(
        "CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT, "
        "role TEXT NOT NULL DEFAULT 'user', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE routines (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, name TEXT NOT NULL, "
        "day_order INTEGER NOT NULL, is_active INTEGER NOT NULL DEFAULT 1, "
        "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(LEGACY_WORKOUT_LOGS)
    # columnas añadidas por ALTER en producción
    conn.execute("ALTER TABLE workout_logs ADD COLUMN current_exercise_id TEXT")
    conn.execute("ALTER TABLE workout_logs ADD COLUMN is_deload INTEGER NOT NULL DEFAULT 0")
    conn.execute("CREATE INDEX idx_workout_logs_user_date ON workout_logs(user_id, date DESC)")
    conn.execute(
        """CREATE TABLE workout_sets (
            id TEXT PRIMARY KEY,
            workout_log_id TEXT NOT NULL REFERENCES workout_logs(id),
            exercise_id TEXT NOT NULL DEFAULT 'e',
            set_number INTEGER NOT NULL DEFAULT 1,
            weight_kg REAL NOT NULL DEFAULT 0,
            reps INTEGER NOT NULL DEFAULT 1,
            rir INTEGER, is_warmup INTEGER NOT NULL DEFAULT 0, notes TEXT)"""
    )
    conn.execute("INSERT INTO users (id, name) VALUES ('u1','Pablo')")
    for i in range(rows):
        conn.execute(
            "INSERT INTO workout_logs (id,user_id,date,status,current_exercise_id,is_deload) VALUES (?,?,?,?,?,?)",
            (f"w{i}", "u1", f"2026-11-0{i+1}T10:00:00", "completed", f"ex{i}", i % 2),
        )
        conn.execute("INSERT INTO workout_sets (id, workout_log_id) VALUES (?,?)", (f"s{i}", f"w{i}"))
    conn.commit()
    return conn


# ---------------------------------------------------------------- conexión

def test_get_connection_wal_y_busy_timeout(test_db):
    conn = get_connection()
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 15000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        conn.close()


# ---------------------------------------------------------------- migración expired

def test_esquema_nuevo_ya_admite_expired(test_db):
    conn = get_connection()
    try:
        assert not workout_logs_needs_expired_migration(conn)
        conn.execute(
            "INSERT INTO workout_logs (id,user_id,date,status) VALUES ('x',?,?, 'expired')",
            (PABLO_ID, "2026-11-01T10:00:00"),
        )
    finally:
        conn.close()


def test_migracion_legacy_conserva_datos_indices_y_fk(tmp_path):
    path = tmp_path / "legacy.db"
    conn = _legacy_db(path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO workout_logs (id,user_id,date,status) VALUES ('e','u1','2026-11-09','expired')")
    conn.rollback()
    assert workout_logs_needs_expired_migration(conn)

    assert migrate_workout_logs_allow_expired(conn) is True

    assert not workout_logs_needs_expired_migration(conn)
    rows = conn.execute("SELECT id,status,current_exercise_id,is_deload FROM workout_logs ORDER BY id").fetchall()
    assert [tuple(r) for r in rows] == [("w0", "completed", "ex0", 0), ("w1", "completed", "ex1", 1), ("w2", "completed", "ex2", 0)]
    # ahora 'expired' es válido y otros valores siguen rechazados
    conn.execute("INSERT INTO workout_logs (id,user_id,date,status) VALUES ('e','u1','2026-11-09','expired')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO workout_logs (id,user_id,date,status) VALUES ('z','u1','2026-11-09','otro')")
    conn.rollback()
    # índice recreado, sin tabla temporal residual y workout_sets sigue apuntando a workout_logs
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert "idx_workout_logs_user_date" in names
    assert "workout_logs__new" not in names
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.execute("PRAGMA foreign_keys = ON")
    with pytest.raises(sqlite3.IntegrityError):  # FK de workout_sets sigue activa
        conn.execute("INSERT INTO workout_sets (id, workout_log_id) VALUES ('bad','no-existe')")
    conn.rollback()
    # idempotente
    assert migrate_workout_logs_allow_expired(conn) is False
    conn.close()


class _FailOnDrop:
    """Proxy de conexión que falla al borrar la tabla original."""

    def __init__(self, conn):
        object.__setattr__(self, "_c", conn)

    def execute(self, sql, *a):
        if sql.strip() == "DROP TABLE workout_logs":
            raise sqlite3.OperationalError("fallo simulado")
        return self._c.execute(sql, *a)

    def __getattr__(self, name):
        return getattr(self._c, name)

    def __setattr__(self, name, value):
        setattr(self._c, name, value)


def test_migracion_con_fallo_hace_rollback(tmp_path):
    path = tmp_path / "legacy.db"
    conn = _legacy_db(path)
    assert migrate_workout_logs_allow_expired(_FailOnDrop(conn)) is False
    # la tabla original queda intacta, sin residuos
    assert workout_logs_needs_expired_migration(conn)
    assert conn.execute("SELECT COUNT(*) FROM workout_logs").fetchone()[0] == 3
    assert "workout_logs__new" not in {r[0] for r in conn.execute("SELECT name FROM sqlite_master")}
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()


def test_init_db_migra_bd_legacy(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    conn = _legacy_db(path)
    conn.close()
    monkeypatch.setattr(database, "DB_PATH", path)
    init_db()
    init_db()  # idempotente
    conn = get_connection()
    try:
        assert not workout_logs_needs_expired_migration(conn)
        assert conn.execute("SELECT COUNT(*) FROM workout_logs").fetchone()[0] == 3
    finally:
        conn.close()


# ---------------------------------------------------------------- sin DDL en GET

def test_endpoints_get_no_ejecutan_ddl(client, monkeypatch):
    statements = []
    real_connect = sqlite3.connect

    def spy_connect(*args, **kwargs):
        c = real_connect(*args, **kwargs)
        c.set_trace_callback(statements.append)
        return c

    monkeypatch.setattr(sqlite3, "connect", spy_connect)

    urls = [
        "/api/routines",
        f"/api/progress/home?user_id={PABLO_ID}",
        f"/api/progress/stats?user_id={PABLO_ID}",
        "/api/activities/classes",
        "/api/activities/log",
        "/api/diet/week",
        "/api/diet/profile",
        "/api/workouts/in-progress",
        f"/api/workouts?user_id={PABLO_ID}",
        f"/api/body-metrics?user_id={PABLO_ID}",
    ]
    for url in urls:
        r = client.get(url)
        assert r.status_code < 500, (url, r.status_code, r.text[:200])

    ddl = [
        s for s in statements
        if s.lstrip().upper().startswith(("CREATE", "ALTER", "DROP"))
    ]
    assert ddl == [], ddl


# ---------------------------------------------------------------- concurrencia

def test_peticiones_durante_escritura_larga_no_dan_500(client):
    locked = threading.Event()

    def hold_write_lock():
        holder = get_connection()
        holder.execute("BEGIN IMMEDIATE")  # bloqueo de escritura
        locked.set()
        time.sleep(1.0)
        holder.rollback()
        holder.close()

    t = threading.Thread(target=hold_write_lock)
    t.start()
    assert locked.wait(5)
    try:
        started = time.time()
        for url in ("/api/routines", f"/api/progress/home?user_id={PABLO_ID}", "/api/activities/log"):
            r = client.get(url)
            assert r.status_code == 200, (url, r.status_code, r.text[:200])
        # una escritura espera al desbloqueo en vez de fallar con 'database is locked'
        r = client.post(
            "/api/body-metrics",
            json={"user_id": PABLO_ID, "date": "2026-11-12", "weight_kg": 80.0},
        )
        assert r.status_code in (200, 201), r.text[:200]
        assert time.time() - started < 10
    finally:
        t.join()
