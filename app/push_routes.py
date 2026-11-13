"""Rutas de Web Push (Fase 10)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user
from . import push

router = APIRouter(prefix="/api/push", tags=["push"])


class SubscribeBody(BaseModel):
    endpoint: str
    keys: dict[str, str] | None = None
    p256dh: str | None = None
    auth: str | None = None


class UnsubscribeBody(BaseModel):
    endpoint: str


class RestTimerBody(BaseModel):
    seconds: int = Field(..., ge=1, le=push.MAX_REST_SECONDS)
    exercise_name: str | None = None


class TestPushBody(BaseModel):
    seconds: int | None = Field(default=None, ge=0, le=push.MAX_TEST_SECONDS)


def _require_vapid() -> dict:
    data = push.load_vapid()
    if not data:
        raise HTTPException(
            status_code=503,
            detail="Los avisos push no están configurados en el servidor",
        )
    return data


def _keys_from_body(body: SubscribeBody) -> tuple[str, str]:
    keys = body.keys or {}
    p256dh = (body.p256dh or keys.get("p256dh") or "").strip()
    auth = (body.auth or keys.get("auth") or "").strip()
    return p256dh, auth


@router.get("/vapid-public-key")
def get_vapid_public_key(current_user=Depends(get_authenticated_user)):
    _ = current_user
    data = _require_vapid()
    return {"public_key": data["public_key"]}


@router.post("/subscribe")
def subscribe(body: SubscribeBody, current_user=Depends(get_authenticated_user)):
    _require_vapid()
    p256dh, auth = _keys_from_body(body)
    try:
        result = push.upsert_subscription(current_user["id"], body.endpoint, p256dh, auth)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"ok": True, **result}


@router.delete("/subscribe")
def unsubscribe(body: UnsubscribeBody, current_user=Depends(get_authenticated_user)):
    deleted = push.delete_subscription(current_user["id"], body.endpoint)
    return {"ok": True, "deleted": deleted}


@router.post("/rest-timer")
def schedule_rest_timer(body: RestTimerBody, current_user=Depends(get_authenticated_user)):
    _require_vapid()
    payload = push.rest_payload(body.exercise_name)
    scheduled = push.schedule_push(
        current_user["id"], body.seconds, payload, kind=push.REST_KIND
    )
    return {"ok": True, **scheduled}


@router.delete("/rest-timer")
def cancel_rest_timer(current_user=Depends(get_authenticated_user)):
    cancelled = push.cancel_scheduled(current_user["id"], kind=push.REST_KIND)
    return {"ok": True, "cancelled": cancelled}


@router.post("/test")
def test_push(body: TestPushBody | None = None, current_user=Depends(get_authenticated_user)):
    _require_vapid()
    seconds = push.DEFAULT_TEST_SECONDS
    if body is not None and body.seconds is not None:
        seconds = body.seconds
    payload = push.test_payload()
    if seconds <= 0:
        counts = push.send_to_user(current_user["id"], payload)
        return {"ok": True, "sent": counts}
    scheduled = push.schedule_push(
        current_user["id"], seconds, payload, kind=push.TEST_KIND
    )
    return {"ok": True, "seconds": seconds, **scheduled}
