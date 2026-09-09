from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .auth import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    create_session,
    get_current_user,
    set_session_cookie,
    verify_password,
    create_password_hash,
    utc_now,
    hash_session_token,
    revoke_session,
    create_csrf_token,
    set_csrf_cookie,
    clear_csrf_cookie,
)
from .database import get_connection


router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    name: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    new_password_confirmation: str


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    name = payload.name.strip()

    if not name or not payload.password:
        raise HTTPException(
            status_code=400,
            detail="Nombre y contraseña son obligatorios",
        )

    conn = get_connection()

    try:
        user = conn.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE lower(name) = lower(?)
            """,
            (name,),
        ).fetchone()

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Credenciales incorrectas",
            )

        credentials = conn.execute(
            """
            SELECT password_hash, must_change_password
            FROM user_credentials
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()

        if credentials is None or not verify_password(
            payload.password,
            credentials["password_hash"],
        ):
            raise HTTPException(
                status_code=401,
                detail="Credenciales incorrectas",
            )

        token = create_session(conn, user["id"])
        conn.commit()

        set_session_cookie(response, token)
        csrf_token = create_csrf_token()
        set_csrf_cookie(response, csrf_token)

        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "must_change_password": bool(credentials["must_change_password"]),
        }

    finally:
        conn.close()


@router.get("/me")
def me(request: Request):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        user = get_current_user(conn, session_token)

        credentials = conn.execute(
            """
            SELECT must_change_password
            FROM user_credentials
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()

        return {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
            "role": user["role"],
            "must_change_password": bool(
                credentials["must_change_password"]
            ) if credentials else True,
        }
    finally:
        conn.close()


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
):
    if len(payload.new_password) < 10:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe tener al menos 10 caracteres",
        )

    if payload.new_password != payload.new_password_confirmation:
        raise HTTPException(
            status_code=400,
            detail="Las nuevas contraseñas no coinciden",
        )

    if payload.new_password == payload.current_password:
        raise HTTPException(
            status_code=400,
            detail="La nueva contraseña debe ser diferente",
        )

    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        user = get_current_user(conn, session_token)

        credentials = conn.execute(
            """
            SELECT password_hash
            FROM user_credentials
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchone()

        if credentials is None or not verify_password(
            payload.current_password,
            credentials["password_hash"],
        ):
            raise HTTPException(
                status_code=401,
                detail="La contraseña actual es incorrecta",
            )

        new_hash = create_password_hash(payload.new_password)

        conn.execute(
            """
            UPDATE user_credentials
            SET password_hash = ?,
                updated_at = ?,
                must_change_password = 0
            WHERE user_id = ?
            """,
            (
                new_hash,
                utc_now().isoformat(),
                user["id"],
            ),
        )

        # Revocar todas las sesiones excepto la que estamos utilizando.
        current_hash = hash_session_token(session_token)

        conn.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE user_id = ?
              AND token_hash != ?
              AND revoked_at IS NULL
            """,
            (
                utc_now().isoformat(),
                user["id"],
                current_hash,
            ),
        )

        conn.commit()

        return {
            "status": "ok",
            "message": "Contraseña cambiada correctamente",
            "must_change_password": False,
        }

    finally:
        conn.close()


@router.post("/logout")
def logout(request: Request, response: Response):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        if session_token:
            from .auth import revoke_session

            revoke_session(conn, session_token)
            conn.commit()

        clear_session_cookie(response)
        clear_csrf_cookie(response)

        return {"status": "ok"}
    finally:
        conn.close()
