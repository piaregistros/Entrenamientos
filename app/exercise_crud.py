"""Fase 7: CRUD de ejercicios y rutinas (admin y propietario) + migraciones de datos idempotentes.

Permisos
* Ejercicios del catálogo (``is_custom = 0``): solo admin edita/borra y no se pueden renombrar
  (las fichas, vídeos y sustituciones se enlazan por nombre).
* Ejercicios propios (``is_custom = 1``): admin o su creador (``created_by``).
* Rutinas: admin o dueño (``routines.user_id``).

Borrado
* Ejercicio con historial / rutinas / sustituciones guardadas → borrado lógico (``is_active = 0``).
* Sin ninguna referencia → se borra de verdad (junto con sus parejas de sustitución, vídeos y progresión).
* Rutina con entrenos registrados → ``is_active = 0``; sin entrenos → se borra de verdad.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user, resolve_target_user
from .database import get_connection
from .exercise_sheets import normalize_name
from .progression import MEASURE_TYPES, default_increment, infer_measure_type

logger = logging.getLogger(__name__)
router = APIRouter()

TEST_EXERCISE_NAMES = ("TEST-BOT sentadilla",)  # migración por nombre EXACTO
# Filas que se borran solas al borrar de verdad un ejercicio (no cuentan como «historial»).
AUTO_CLEAN = {
    "exercise_substitutions": ("exercise_id", "alternative_exercise_id"),
    "exercise_media": ("exercise_id",),
    "exercise_progress": ("exercise_id",),
    "exercise_flags": ("exercise_id",),
    "user_substitution_prefs": ("original_exercise_id", "substitute_exercise_id"),
}


def _columns(conn, table) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def ensure_crud_schema(conn: sqlite3.Connection) -> None:
    """Columnas aditivas: exercises.created_by / is_custom."""
    cols = _columns(conn, "exercises")
    if "created_by" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN created_by TEXT")
    if "is_custom" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN is_custom INTEGER NOT NULL DEFAULT 0")
        # Primera vez: lo que no es del catálogo de 59 es un ejercicio propio (sin dueño → solo admin).
        from .seed_exercises_v2 import EXERCISES as CATALOG

        names = {normalize_name(e["name"]) for e in CATALOG}
        for row in conn.execute("SELECT id, name FROM exercises").fetchall():
            if normalize_name(row["name"]) not in names:
                conn.execute("UPDATE exercises SET is_custom = 1 WHERE id = ?", (row["id"],))
    conn.commit()


def exercise_references(conn, exercise_id: str) -> dict[str, int]:
    """Filas que referencian el ejercicio y que cuentan como historial (bloquean el borrado real)."""
    found: dict[str, int] = {}
    for table in sorted(_tables(conn)):
        if table in AUTO_CLEAN or table == "exercises" or table.startswith("sqlite_"):
            continue
        cols = {fk["from"] for fk in conn.execute(f"PRAGMA foreign_key_list({table})")
                if fk["table"] == "exercises"}
        for col in cols:
            n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (exercise_id,)).fetchone()[0]
            if n:
                found[f"{table}.{col}"] = n
    return found


def delete_or_deactivate_exercise(conn, exercise_id: str) -> str:
    """'deleted' o 'deactivated'. No hace commit."""
    if exercise_references(conn, exercise_id):
        conn.execute("UPDATE exercises SET is_active = 0 WHERE id = ?", (exercise_id,))
        return "deactivated"
    existing = _tables(conn)
    for table, cols in AUTO_CLEAN.items():
        if table not in existing:
            continue
        for col in cols:
            conn.execute(f"DELETE FROM {table} WHERE {col} = ?", (exercise_id,))
    conn.execute("DELETE FROM exercises WHERE id = ?", (exercise_id,))
    return "deleted"


def apply_data_migrations(conn: sqlite3.Connection) -> dict:
    """Migraciones de datos idempotentes (por nombre exacto)."""
    report = {"test_exercises": []}
    for name in TEST_EXERCISE_NAMES:
        for row in conn.execute("SELECT id, is_active FROM exercises WHERE name = ?", (name,)).fetchall():
            if not row["is_active"] and exercise_references(conn, row["id"]):
                continue  # ya desactivado y con historial: nada que hacer
            outcome = delete_or_deactivate_exercise(conn, row["id"])
            report["test_exercises"].append((name, outcome))
            logger.warning("MIGRACIÓN Fase 7: %r → %s", name, outcome)
    conn.commit()
    return report


# ------------------------------------------------------------------ permisos
def _can_edit_exercise(user, ex) -> bool:
    if user["role"] == "admin":
        return True
    return bool(ex["is_custom"]) and ex["created_by"] is not None and ex["created_by"] == user["id"]


def exercise_can_edit(user, ex_row) -> bool:
    return _can_edit_exercise(user, ex_row)


def _get_exercise_or_404(conn, exercise_id):
    ex = conn.execute("SELECT * FROM exercises WHERE id = ?", (exercise_id,)).fetchone()
    if ex is None:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
    return ex


# ------------------------------------------------------------------ ejercicios
class ExerciseUpdateIn(BaseModel):
    name: str | None = None
    target_muscle: str | None = None
    category: str | None = None
    equipment: str | None = None
    instructions: str | None = None
    safety_notes: str | None = None
    contraindications: str | None = None
    steps: list[str] | None = None
    technical_cues: list[str] | None = None
    common_mistakes: list[str] | None = None
    weight_increment_kg: float | None = Field(default=None, ge=0, le=100)
    measure_type: str | None = None
    movement_pattern: str | None = None
    secondary_muscles: str | None = None
    exercise_type: str | None = None
    difficulty: str | None = None
    laterality: str | None = None
    is_active: bool | None = None


JSON_FIELDS = ("steps", "technical_cues", "common_mistakes")
TEXT_FIELDS = ("target_muscle", "category", "equipment", "instructions", "safety_notes", "contraindications",
               "movement_pattern", "secondary_muscles", "exercise_type", "difficulty", "laterality")


@router.put("/api/exercises/{exercise_id}")
def update_exercise(exercise_id: str, body: ExerciseUpdateIn, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        ex = _get_exercise_or_404(conn, exercise_id)
        if not _can_edit_exercise(current_user, ex):
            raise HTTPException(status_code=403, detail="No puedes editar este ejercicio")
        data = body.model_dump(exclude_unset=True)
        cols = _columns(conn, "exercises")
        sets: list[str] = []
        params: list = []

        if "name" in data and data["name"] is not None:
            name = " ".join(data["name"].split())
            if len(name) < 2:
                raise HTTPException(status_code=400, detail="Nombre demasiado corto")
            if name != ex["name"]:
                if not ex["is_custom"]:
                    raise HTTPException(status_code=400, detail="Los ejercicios del catálogo no se pueden renombrar")
                dup = conn.execute("SELECT id FROM exercises WHERE lower(name) = lower(?) AND id <> ?",
                                   (name, exercise_id)).fetchone()
                if dup:
                    raise HTTPException(status_code=409, detail="Ya existe un ejercicio con ese nombre")
                sets.append("name = ?")
                params.append(name)
        for field in TEXT_FIELDS:
            if field in data and data[field] is not None and field in cols:
                sets.append(f"{field} = ?")
                params.append(data[field])
        for field in JSON_FIELDS:
            if field in data and data[field] is not None and field in cols:
                sets.append(f"{field} = ?")
                params.append(json.dumps([x for x in data[field] if str(x).strip()], ensure_ascii=False))
        if "weight_increment_kg" in data and data["weight_increment_kg"] is not None:
            sets.append("weight_increment_kg = ?")
            params.append(data["weight_increment_kg"])
        if "measure_type" in data and data["measure_type"] is not None:
            if data["measure_type"] not in MEASURE_TYPES:
                raise HTTPException(status_code=400, detail="measure_type debe ser: " + ", ".join(MEASURE_TYPES))
            if "measure_type" in cols:
                sets.append("measure_type = ?")
                params.append(data["measure_type"])
        if "is_active" in data and data["is_active"] is not None:
            sets.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)
        # Si cambia el equipo y no se fija el incremento, se deduce del nuevo equipo (solo ejercicios propios).
        if ("equipment" in data and ex["is_custom"] and "weight_increment_kg" not in data
                and data["equipment"] is not None):
            mt = data.get("measure_type") or (ex["measure_type"] if "measure_type" in ex.keys() else None) \
                or infer_measure_type(ex["name"], data["equipment"])
            sets.append("weight_increment_kg = ?")
            params.append(default_increment(data["equipment"], ex["exercise_type"] if "exercise_type" in ex.keys() else None, mt))
        if not sets:
            return {"id": exercise_id, "updated": False}
        conn.execute(f"UPDATE exercises SET {', '.join(sets)} WHERE id = ?", params + [exercise_id])
        conn.commit()
        row = conn.execute("SELECT id, name, is_active, is_custom, created_by FROM exercises WHERE id = ?",
                           (exercise_id,)).fetchone()
        return {"updated": True, **dict(row)}
    finally:
        conn.close()


@router.delete("/api/exercises/{exercise_id}")
def delete_exercise(exercise_id: str, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        ex = _get_exercise_or_404(conn, exercise_id)
        if not _can_edit_exercise(current_user, ex):
            raise HTTPException(status_code=403, detail="No puedes borrar este ejercicio")
        refs = exercise_references(conn, exercise_id)
        outcome = delete_or_deactivate_exercise(conn, exercise_id)
        conn.commit()
        return {
            "id": exercise_id,
            "result": outcome,
            "deleted": outcome == "deleted",
            "deactivated": outcome == "deactivated",
            "references": refs,
        }
    finally:
        conn.close()


# ------------------------------------------------------------------ rutinas
class RoutineExerciseIn(BaseModel):
    exercise_id: str
    target_sets: int = Field(default=3, ge=1, le=20)
    target_rep_min: int = Field(default=8, ge=1, le=100)
    target_rep_max: int = Field(default=12, ge=1, le=300)
    target_rir: int | None = Field(default=2, ge=0, le=10)
    rest_seconds: int | None = Field(default=90, ge=0, le=900)
    is_optional: bool = False


class RoutineExerciseUpdateIn(BaseModel):
    target_sets: int | None = Field(default=None, ge=1, le=20)
    target_rep_min: int | None = Field(default=None, ge=1, le=100)
    target_rep_max: int | None = Field(default=None, ge=1, le=300)
    target_rir: int | None = Field(default=None, ge=0, le=10)
    rest_seconds: int | None = Field(default=None, ge=0, le=900)
    is_optional: bool | None = None


class RoutineCreateIn(BaseModel):
    name: str
    user_id: str | None = None
    day_order: int | None = Field(default=None, ge=1, le=99)
    session_label: str | None = None
    exercises: list[RoutineExerciseIn] = []


class RoutineUpdateIn(BaseModel):
    name: str | None = None
    day_order: int | None = Field(default=None, ge=1, le=99)
    session_label: str | None = None
    is_active: bool | None = None


class ReorderIn(BaseModel):
    routine_exercise_ids: list[str]


def _routine_for_edit(conn, routine_id, user):
    r = conn.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
    if r is None or (user["role"] != "admin" and r["user_id"] != user["id"]):
        raise HTTPException(status_code=404, detail="Rutina no encontrada")
    return r


def _check_range(rep_min, rep_max):
    if rep_min is not None and rep_max is not None and rep_max < rep_min:
        raise HTTPException(status_code=400, detail="El máximo de repeticiones no puede ser menor que el mínimo")


def _active_exercise_or_404(conn, exercise_id):
    ex = conn.execute("SELECT id FROM exercises WHERE id = ? AND is_active = 1", (exercise_id,)).fetchone()
    if ex is None:
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")


def _routine_payload(conn, routine_id) -> dict:
    r = conn.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
    exercises = conn.execute(
        """
        SELECT re.id, re.exercise_id, e.name, e.target_muscle, e.equipment, e.is_active,
               re."order", re.target_sets, re.target_rep_min, re.target_rep_max, re.target_rir,
               re.rest_seconds, re.is_optional
        FROM routine_exercises re JOIN exercises e ON e.id = re.exercise_id
        WHERE re.routine_id = ? ORDER BY re."order"
        """,
        (routine_id,),
    ).fetchall()
    out = dict(r)
    out["exercises"] = [dict(x) for x in exercises]
    return out


def _next_order(conn, routine_id) -> int:
    return conn.execute('SELECT COALESCE(MAX("order"), 0) + 1 FROM routine_exercises WHERE routine_id = ?',
                        (routine_id,)).fetchone()[0]


def _insert_routine_exercise(conn, routine_id, item: RoutineExerciseIn):
    _check_range(item.target_rep_min, item.target_rep_max)
    _active_exercise_or_404(conn, item.exercise_id)
    if conn.execute("SELECT 1 FROM routine_exercises WHERE routine_id = ? AND exercise_id = ?",
                    (routine_id, item.exercise_id)).fetchone():
        raise HTTPException(status_code=409, detail="Ese ejercicio ya está en la rutina")
    rid = str(uuid.uuid4())
    conn.execute(
        """INSERT INTO routine_exercises
           (id, routine_id, exercise_id, "order", target_sets, target_rep_min, target_rep_max,
            target_rir, rest_seconds, is_optional)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (rid, routine_id, item.exercise_id, _next_order(conn, routine_id), item.target_sets,
         item.target_rep_min, item.target_rep_max, item.target_rir, item.rest_seconds, int(item.is_optional)),
    )
    return rid


@router.post("/api/routines")
def create_routine(body: RoutineCreateIn, current_user=Depends(get_authenticated_user)):
    owner = resolve_target_user(current_user, body.user_id)
    name = " ".join(body.name.split())
    if len(name) < 1:
        raise HTTPException(status_code=400, detail="La rutina necesita un nombre")
    conn = get_connection()
    try:
        if not conn.execute("SELECT 1 FROM users WHERE id = ?", (owner,)).fetchone():
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        day_order = body.day_order or conn.execute(
            "SELECT COALESCE(MAX(day_order), 0) + 1 FROM routines WHERE user_id = ?", (owner,)).fetchone()[0]
        rid = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO routines (id, user_id, name, day_order, is_active, session_label) VALUES (?, ?, ?, ?, 1, ?)",
            (rid, owner, name, day_order, body.session_label),
        )
        seen = set()
        for item in body.exercises:
            if item.exercise_id in seen:
                raise HTTPException(status_code=409, detail="Ejercicio repetido en la rutina")
            seen.add(item.exercise_id)
            _insert_routine_exercise(conn, rid, item)
        conn.commit()
        return _routine_payload(conn, rid)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.put("/api/routines/{routine_id}")
def update_routine(routine_id: str, body: RoutineUpdateIn, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        data = body.model_dump(exclude_unset=True)
        sets, params = [], []
        if data.get("name") is not None:
            name = " ".join(data["name"].split())
            if not name:
                raise HTTPException(status_code=400, detail="La rutina necesita un nombre")
            sets.append("name = ?")
            params.append(name)
        if data.get("day_order") is not None:
            sets.append("day_order = ?")
            params.append(data["day_order"])
        if "session_label" in data:
            sets.append("session_label = ?")
            params.append(data["session_label"])
        if data.get("is_active") is not None:
            sets.append("is_active = ?")
            params.append(1 if data["is_active"] else 0)
        if sets:
            conn.execute(f"UPDATE routines SET {', '.join(sets)} WHERE id = ?", params + [routine_id])
            conn.commit()
        return _routine_payload(conn, routine_id)
    finally:
        conn.close()


@router.delete("/api/routines/{routine_id}")
def delete_routine(routine_id: str, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        used = conn.execute("SELECT COUNT(*) FROM workout_logs WHERE routine_id = ?", (routine_id,)).fetchone()[0]
        if used:
            conn.execute("UPDATE routines SET is_active = 0 WHERE id = ?", (routine_id,))
            result = "deactivated"
        else:
            if "user_substitution_prefs" in _tables(conn):
                conn.execute("DELETE FROM user_substitution_prefs WHERE routine_id = ?", (routine_id,))
            conn.execute("DELETE FROM routine_exercises WHERE routine_id = ?", (routine_id,))
            conn.execute("DELETE FROM routines WHERE id = ?", (routine_id,))
            result = "deleted"
        conn.commit()
        return {"id": routine_id, "result": result, "deleted": result == "deleted",
                "deactivated": result == "deactivated", "workouts": used}
    finally:
        conn.close()


@router.post("/api/routines/{routine_id}/exercises")
def add_routine_exercise(routine_id: str, body: RoutineExerciseIn, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        _insert_routine_exercise(conn, routine_id, body)
        conn.commit()
        return _routine_payload(conn, routine_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.put("/api/routines/{routine_id}/exercises/order")
def reorder_routine_exercises(routine_id: str, body: ReorderIn, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        current = [r["id"] for r in conn.execute(
            'SELECT id FROM routine_exercises WHERE routine_id = ? ORDER BY "order"', (routine_id,))]
        if sorted(current) != sorted(body.routine_exercise_ids) or len(set(body.routine_exercise_ids)) != len(current):
            raise HTTPException(status_code=400, detail="La lista debe contener exactamente los ejercicios de la rutina")
        # Dos fases por la restricción UNIQUE (routine_id, exercise_id, "order").
        for i, rid in enumerate(body.routine_exercise_ids):
            conn.execute('UPDATE routine_exercises SET "order" = ? WHERE id = ?', (-(i + 1), rid))
        for i, rid in enumerate(body.routine_exercise_ids):
            conn.execute('UPDATE routine_exercises SET "order" = ? WHERE id = ?', (i + 1, rid))
        conn.commit()
        return _routine_payload(conn, routine_id)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.put("/api/routines/{routine_id}/exercises/{routine_exercise_id}")
def update_routine_exercise(routine_id: str, routine_exercise_id: str, body: RoutineExerciseUpdateIn,
                            current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        re = conn.execute("SELECT * FROM routine_exercises WHERE id = ? AND routine_id = ?",
                          (routine_exercise_id, routine_id)).fetchone()
        if re is None:
            raise HTTPException(status_code=404, detail="Ejercicio de rutina no encontrado")
        data = body.model_dump(exclude_unset=True)
        rep_min = data.get("target_rep_min", re["target_rep_min"])
        rep_max = data.get("target_rep_max", re["target_rep_max"])
        _check_range(rep_min, rep_max)
        sets, params = [], []
        for field in ("target_sets", "target_rep_min", "target_rep_max", "target_rir", "rest_seconds"):
            if field in data:
                sets.append(f"{field} = ?")
                params.append(data[field])
        if data.get("is_optional") is not None:
            sets.append("is_optional = ?")
            params.append(int(data["is_optional"]))
        if sets:
            conn.execute(f"UPDATE routine_exercises SET {', '.join(sets)} WHERE id = ?", params + [routine_exercise_id])
            conn.commit()
        return _routine_payload(conn, routine_id)
    finally:
        conn.close()


@router.delete("/api/routines/{routine_id}/exercises/{routine_exercise_id}")
def delete_routine_exercise(routine_id: str, routine_exercise_id: str, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        _routine_for_edit(conn, routine_id, current_user)
        cur = conn.execute("DELETE FROM routine_exercises WHERE id = ? AND routine_id = ?",
                           (routine_exercise_id, routine_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Ejercicio de rutina no encontrado")
        # Compactar el orden (1..n) en dos fases por la restricción UNIQUE.
        ids = [r["id"] for r in conn.execute(
            'SELECT id FROM routine_exercises WHERE routine_id = ? ORDER BY "order"', (routine_id,))]
        for i, rid in enumerate(ids):
            conn.execute('UPDATE routine_exercises SET "order" = ? WHERE id = ?', (-(i + 1), rid))
        for i, rid in enumerate(ids):
            conn.execute('UPDATE routine_exercises SET "order" = ? WHERE id = ?', (i + 1, rid))
        conn.commit()
        return _routine_payload(conn, routine_id)
    finally:
        conn.close()
