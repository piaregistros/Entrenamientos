from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, Request, Response, status
from pwdlib import PasswordHash
from .database import get_connection


SESSION_COOKIE_NAME = "entrenamiento_session"
CSRF_COOKIE_NAME = "entrenamiento_csrf"
CSRF_TOKEN_BYTES = 32
SESSION_TTL_HOURS = 24 * 7

password_hash = PasswordHash.recommended()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_password_hash(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)



def create_csrf_token() -> str:
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def set_csrf_cookie(response, token: str):
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=token,
        httponly=False,
        secure=False,
        samesite="lax",
        path="/",
    )


def clear_csrf_cookie(response):
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
    )


def validate_csrf_token(cookie_token: str | None, header_token: str | None) -> bool:
    if not cookie_token or not header_token:
        return False
    return secrets.compare_digest(cookie_token, header_token)


def create_session(conn: sqlite3.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(48)
    token_hash = hash_session_token(token)

    now = utc_now()
    expires = now + timedelta(hours=SESSION_TTL_HOURS)

    conn.execute(
        """
        INSERT INTO auth_sessions
        (id, user_id, token_hash, created_at, expires_at, revoked_at)
        VALUES (?, ?, ?, ?, ?, NULL)
        """,
        (
            secrets.token_hex(16),
            user_id,
            token_hash,
            now.isoformat(),
            expires.isoformat(),
        ),
    )

    return token


def revoke_session(conn: sqlite3.Connection, token: str) -> None:
    conn.execute(
        """
        UPDATE auth_sessions
        SET revoked_at = ?
        WHERE token_hash = ?
          AND revoked_at IS NULL
        """,
        (utc_now().isoformat(), hash_session_token(token)),
    )


def get_current_user(
    conn: sqlite3.Connection,
    session_token: Optional[str],
) -> sqlite3.Row:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    token_hash = hash_session_token(session_token)

    row = conn.execute(
        """
        SELECT
            s.expires_at,
            u.id,
            u.name,
            u.email,
            u.role,
            u.created_at
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.revoked_at IS NULL
        """,
        (token_hash,),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session",
        )

    if parse_datetime(row["expires_at"]) <= utc_now():
        conn.execute(
            """
            UPDATE auth_sessions
            SET revoked_at = ?
            WHERE token_hash = ?
              AND revoked_at IS NULL
            """,
            (utc_now().isoformat(), token_hash),
        )
        conn.commit()

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )

    return row


def require_admin(user: sqlite3.Row) -> None:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )


def resolve_target_user(
    current_user: sqlite3.Row,
    requested_user_id: Optional[str],
) -> str:
    if current_user["role"] == "admin":
        return requested_user_id or current_user["id"]

    if requested_user_id and requested_user_id != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another user's data",
        )

    return current_user["id"]


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_HOURS * 60 * 60,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=False,
        samesite="lax",
        path="/",
    )


def get_authenticated_user(request: Request) -> sqlite3.Row:
    """
    Dependencia FastAPI para obtener el usuario autenticado
    a partir de la sesión HttpOnly.
    """
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        return get_current_user(conn, session_token)
    finally:
        conn.close()


def require_authenticated_user(
    current_user: sqlite3.Row = Depends(get_authenticated_user),
) -> sqlite3.Row:
    """
    Dependencia explícita para endpoints privados.
    """
    return current_user
