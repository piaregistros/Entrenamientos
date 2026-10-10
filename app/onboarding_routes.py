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
    conn = get_connection()

    try:
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
