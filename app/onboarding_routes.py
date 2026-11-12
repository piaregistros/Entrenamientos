from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import get_authenticated_user
from .database import get_connection
from .onboarding import (
    complete_onboarding,
    get_onboarding_status,
    get_training_profile,
    save_training_profile,
)
from .training_assessment import ASSESSMENT_QUESTIONS


router = APIRouter(
    prefix="/api/onboarding",
    tags=["onboarding"],
)


class OnboardingCompleteRequest(BaseModel):
    answers: dict[str, str]
    weight_kg: float


@router.get("")
def onboarding_status(
    current_user: Any = Depends(get_authenticated_user),
):
    conn = get_connection()

    try:
        return get_onboarding_status(
            conn,
            current_user["id"],
        )
    finally:
        conn.close()


@router.get("/assessment")
def onboarding_assessment(
    current_user: Any = Depends(get_authenticated_user),
):
    return {
        "version": 2,
        "questions": ASSESSMENT_QUESTIONS,
    }


@router.get("/profile")
def onboarding_profile(
    current_user: Any = Depends(get_authenticated_user),
):
    conn = get_connection()

    try:
        profile = get_training_profile(
            conn,
            current_user["id"],
        )

        if profile is None:
            raise HTTPException(
                status_code=404,
                detail="No existe un perfil de entrenamiento.",
            )

        return profile
    finally:
        conn.close()


@router.post("/complete")
def onboarding_complete(
    request: OnboardingCompleteRequest,
    current_user: Any = Depends(get_authenticated_user),
):
    user_id = current_user["id"]
    weight = float(request.weight_kg)
    if weight < 40 or weight > 180:
        raise HTTPException(status_code=400, detail="El peso tiene que estar entre 40 y 180 kg")
    conn = get_connection()

    try:
        from datetime import date
        from uuid import uuid4

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS diet_profiles (
                user_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL DEFAULT 'recomp',
                meals_per_day INTEGER NOT NULL DEFAULT 4,
                weight_kg REAL,
                notes TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            """
            INSERT INTO diet_profiles(user_id, goal, meals_per_day, weight_kg, updated_at)
            VALUES(?, 'recomp', 4, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                weight_kg=excluded.weight_kg,
                updated_at=CURRENT_TIMESTAMP
            """,
            (user_id, weight),
        )
        tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "diet_week_plans" in tables:
            conn.execute("DELETE FROM diet_week_plans WHERE user_id=?", (user_id,))
        today = date.today().isoformat()
        row = conn.execute(
            "SELECT id FROM body_metrics WHERE user_id=? AND date=?",
            (user_id, today),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE body_metrics SET weight_kg=? WHERE id=?",
                (weight, row["id"]),
            )
        else:
            conn.execute(
                """
                INSERT INTO body_metrics (id, user_id, date, weight_kg, notes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(uuid4()), user_id, today, weight, "Peso del test inicial"),
            )
        profile = save_training_profile(
            conn,
            user_id,
            request.answers,
        )

        status = complete_onboarding(
            conn,
            user_id,
            profile,
        )

        conn.commit()

        return {
            "status": "ok",
            "profile": profile,
            "onboarding": status,
        }

    except ValueError as exc:
        conn.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()
