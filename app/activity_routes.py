"""Registro de clases Enjoy. No toca series ni rutinas A/B/C."""
from __future__ import annotations

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user
from .database import get_connection
from .enjoy_classes import CLASSES, GYM, class_by_id

router = APIRouter(prefix="/api/activities", tags=["activities"])


def init_activity_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS activity_logs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            class_id TEXT NOT NULL,
            class_name TEXT NOT NULL,
            date TEXT NOT NULL,
            duration_minutes INTEGER,
            rpe INTEGER,
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_activity_logs_user_date
            ON activity_logs(user_id, date DESC);
        """
    )
    conn.commit()
    conn.close()


class LogIn(BaseModel):
    class_id: str
    date: str | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
    rpe: int | None = Field(default=None, ge=1, le=10)
    notes: str | None = None


@router.get("/gym")
def gym_info(current_user=Depends(get_authenticated_user)):
    return GYM


@router.get("/classes")
def list_classes(current_user=Depends(get_authenticated_user)):
    return {"gym": GYM, "classes": CLASSES}


@router.post("/log")
def log_activity(body: LogIn, current_user=Depends(get_authenticated_user)):
    init_activity_db()
    spec = class_by_id(body.class_id)
    if not spec:
        raise HTTPException(400, "Clase no reconocida")
    day = body.date or date.today().isoformat()
    try:
        date.fromisoformat(day)
    except ValueError:
        raise HTTPException(400, "Fecha inválida")
    log_id = str(uuid4())
    minutes = body.duration_minutes or spec["minutes"]
    conn = get_connection()
    try:
        conn.execute(
            """INSERT INTO activity_logs(id, user_id, class_id, class_name, date, duration_minutes, rpe, notes)
               VALUES(?,?,?,?,?,?,?,?)""",
            (log_id, current_user["id"], spec["id"], spec["name"], day, minutes, body.rpe, body.notes),
        )
        conn.commit()
        return {"id": log_id, "ok": True, "class_name": spec["name"], "date": day, "duration_minutes": minutes}
    finally:
        conn.close()


@router.get("/log")
def list_logs(limit: int = 30, current_user=Depends(get_authenticated_user)):
    init_activity_db()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT id, class_id, class_name, date, duration_minutes, rpe, notes, created_at
               FROM activity_logs WHERE user_id=? ORDER BY date DESC, created_at DESC LIMIT ?""",
            (current_user["id"], max(1, min(limit, 100))),
        ).fetchall()
        return {"logs": [dict(r) for r in rows]}
    finally:
        conn.close()


@router.delete("/log/{log_id}")
def delete_log(log_id: str, current_user=Depends(get_authenticated_user)):
    init_activity_db()
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM activity_logs WHERE id=? AND user_id=?", (log_id, current_user["id"])
        )
        conn.commit()
        if cur.rowcount == 0:
            raise HTTPException(404, "No encontrado")
        return {"ok": True}
    finally:
        conn.close()
