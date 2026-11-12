"""Ejercicios extra y sustituciones persistentes de una sesión en curso.

Antes el ejercicio extra solo vivía en el estado de React y las sustituciones
se escribían pero nunca se leían al reanudar la sesión. Aquí se guardan en
`workout_extra_exercises` y se devuelven (junto con las sustituciones) en
`GET /api/workouts/{id}` para que recargar o "Salir + Continuar" los conserve.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth import get_authenticated_user, resolve_target_user
from app.database import get_connection

router = APIRouter()

EXERCISE_COLUMNS = """
    e.id, e.name, e.target_muscle, e.category, e.equipment, e.safety_notes,
    e.instructions, e.contraindications, e.weight_increment_kg,
    e.progression_type, e.rep_progression_enabled, e.is_active
"""


class ExtraExerciseIn(BaseModel):
    exercise_id: str
    target_sets: int = Field(default=3, ge=1, le=20)
    target_rep_min: int = Field(default=8, ge=1, le=100)
    target_rep_max: int = Field(default=12, ge=1, le=300)
    target_rir: int | None = Field(default=2, ge=0, le=10)
    rest_seconds: int | None = Field(default=90, ge=0, le=900)


def _exercise_dict(row, prefix: str = "") -> dict:
    keys = (
        "id", "name", "target_muscle", "category", "equipment", "safety_notes",
        "instructions", "contraindications", "weight_increment_kg",
        "progression_type", "rep_progression_enabled", "is_active",
    )
    out = {k: row[f"{prefix}{k}"] for k in keys}
    out["rep_progression_enabled"] = bool(out["rep_progression_enabled"])
    out["is_active"] = bool(out["is_active"])
    return out


def load_extra_exercises(conn, workout_id: str) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT x.exercise_id, x.position, x.target_sets, x.target_rep_min,
               x.target_rep_max, x.target_rir, x.rest_seconds, {EXERCISE_COLUMNS}
        FROM workout_extra_exercises x
        JOIN exercises e ON e.id = x.exercise_id
        WHERE x.workout_log_id = ?
        ORDER BY x.position, x.created_at
        """,
        (workout_id,),
    ).fetchall()
    return [
        {
            "exercise_id": r["exercise_id"],
            "position": r["position"],
            "target_sets": r["target_sets"],
            "target_rep_min": r["target_rep_min"],
            "target_rep_max": r["target_rep_max"],
            "target_rir": r["target_rir"],
            "rest_seconds": r["rest_seconds"],
            "exercise": _exercise_dict(r),
        }
        for r in rows
    ]


def load_substitutions(conn, workout_id: str) -> list[dict]:
    rows = conn.execute(
        f"""
        SELECT s.original_exercise_id, s.substitute_exercise_id, s.reason,
               {EXERCISE_COLUMNS}
        FROM workout_exercise_substitutions s
        JOIN exercises e ON e.id = s.substitute_exercise_id
        WHERE s.workout_log_id = ?
        ORDER BY s.created_at
        """,
        (workout_id,),
    ).fetchall()
    return [
        {
            "original_exercise_id": r["original_exercise_id"],
            "substitute_exercise_id": r["substitute_exercise_id"],
            "reason": r["reason"],
            "substitute_exercise": _exercise_dict(r),
        }
        for r in rows
    ]


@router.post("/api/workouts/{workout_id}/extra-exercises")
def add_extra_exercise(
    workout_id: str,
    body: ExtraExerciseIn,
    user_id: str | None = None,
    current_user=Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
    if body.target_rep_max < body.target_rep_min:
        raise HTTPException(status_code=400, detail="El máximo de repeticiones no puede ser menor que el mínimo")

    conn = get_connection()
    try:
        workout = conn.execute(
            "SELECT id, routine_id, status FROM workout_logs WHERE id = ? AND user_id = ?",
            (workout_id, user_id),
        ).fetchone()
        if workout is None:
            raise HTTPException(status_code=404, detail="Entrenamiento no encontrado")
        if workout["status"] != "in_progress":
            raise HTTPException(status_code=409, detail="La sesión no está en curso")

        exercise = conn.execute(
            f"SELECT {EXERCISE_COLUMNS} FROM exercises e WHERE e.id = ? AND e.is_active = 1",
            (body.exercise_id,),
        ).fetchone()
        if exercise is None:
            raise HTTPException(status_code=404, detail="Ejercicio no encontrado")

        if workout["routine_id"]:
            in_routine = conn.execute(
                "SELECT 1 FROM routine_exercises WHERE routine_id = ? AND exercise_id = ?",
                (workout["routine_id"], body.exercise_id),
            ).fetchone()
            if in_routine:
                raise HTTPException(status_code=409, detail="Ese ejercicio ya forma parte de la rutina")

        existing = conn.execute(
            "SELECT position FROM workout_extra_exercises WHERE workout_log_id = ? AND exercise_id = ?",
            (workout_id, body.exercise_id),
        ).fetchone()
        if existing:  # idempotente: reintentos / doble toque
            created = False
            position = existing["position"]
        else:
            position = conn.execute(
                "SELECT COALESCE(MAX(position), 0) + 1 FROM workout_extra_exercises WHERE workout_log_id = ?",
                (workout_id,),
            ).fetchone()[0]
            conn.execute(
                """
                INSERT INTO workout_extra_exercises
                    (id, workout_log_id, exercise_id, position, target_sets,
                     target_rep_min, target_rep_max, target_rir, rest_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()), workout_id, body.exercise_id, position,
                    body.target_sets, body.target_rep_min, body.target_rep_max,
                    body.target_rir, body.rest_seconds,
                ),
            )
            conn.commit()
            created = True

        extra = next(x for x in load_extra_exercises(conn, workout_id) if x["exercise_id"] == body.exercise_id)
        return {"ok": True, "created": created, "extra_exercise": extra}
    finally:
        conn.close()
