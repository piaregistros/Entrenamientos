from __future__ import annotations

import secrets
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from webauthn import (
    verify_registration_response,
    verify_authentication_response,
)
from webauthn.helpers import (
    bytes_to_base64url,
    base64url_to_bytes,
)
from webauthn.helpers.structs import (
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from .webauthn import (
    RP_ID,
    ORIGIN,
    create_registration_options,
    create_authentication_options,
    options_json,
    now_iso,
)

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
    CSRF_COOKIE_NAME,
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


class WebAuthnCredentialRequest(BaseModel):
    credential: dict


class WebAuthnLoginOptionsRequest(BaseModel):
    user_id: str | None = None
    name: str | None = None


def _save_webauthn_challenge(
    conn,
    *,
    challenge: bytes,
    ceremony: str,
    user_id: str | None = None,
) -> None:
    from datetime import timedelta
    from .auth import utc_now

    now = utc_now()
    expires = now + timedelta(minutes=2)

    conn.execute(
        """
        INSERT INTO webauthn_challenges
        (id, user_id, challenge, ceremony, created_at, expires_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            secrets.token_hex(16),
            user_id,
            bytes_to_base64url(challenge),
            ceremony,
            now.isoformat(),
            expires.isoformat(),
        ),
    )


def _consume_webauthn_challenge(
    conn,
    *,
    challenge: bytes,
    ceremony: str,
    user_id: str | None = None,
):
    from .auth import parse_datetime, utc_now

    encoded = bytes_to_base64url(challenge)

    query = """
        SELECT id, user_id, challenge, ceremony, expires_at
        FROM webauthn_challenges
        WHERE challenge = ?
          AND ceremony = ?
    """

    params = [encoded, ceremony]

    if user_id is not None:
        query += " AND user_id = ?"
        params.append(user_id)

    row = conn.execute(query, params).fetchone()

    if row is None:
        raise HTTPException(
            status_code=400,
            detail="WebAuthn challenge inválido",
        )

    if parse_datetime(row["expires_at"]) <= utc_now():
        conn.execute(
            "DELETE FROM webauthn_challenges WHERE id = ?",
            (row["id"],),
        )
        conn.commit()

        raise HTTPException(
            status_code=400,
            detail="WebAuthn challenge expirado",
        )

    conn.execute(
        "DELETE FROM webauthn_challenges WHERE id = ?",
        (row["id"],),
    )

    return row


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
def me(request: Request, response: Response):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        user = get_current_user(conn, session_token)

        if not request.cookies.get(CSRF_COOKIE_NAME):
            set_csrf_cookie(response, create_csrf_token())

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


# ============================================================
# WEBAUTHN / PASSKEY — REGISTRO
# ============================================================

@router.post("/webauthn/register/options")
def webauthn_register_options(
    request: Request,
):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        user = get_current_user(conn, session_token)

        credentials = conn.execute(
            """
            SELECT credential_id
            FROM webauthn_credentials
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchall()

        exclude_credentials = [
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(row["credential_id"])
            )
            for row in credentials
        ]

        options = create_registration_options(
            user_id=user["id"],
            user_name=user["email"] or user["name"],
            user_display_name=user["name"],
            exclude_credentials=exclude_credentials or None,
        )

        _save_webauthn_challenge(
            conn,
            challenge=options.challenge,
            ceremony="registration",
            user_id=user["id"],
        )

        conn.commit()

        return options_json(options)

    finally:
        conn.close()


# ============================================================
# WEBAUTHN / PASSKEY — REGISTRO VERIFY
# ============================================================

@router.post("/webauthn/register/verify")
def webauthn_register_verify(
    payload: WebAuthnCredentialRequest,
    request: Request,
):
    session_token = request.cookies.get(SESSION_COOKIE_NAME)

    conn = get_connection()

    try:
        user = get_current_user(conn, session_token)

        credential_json = payload.credential

        client_data = credential_json.get("response", {}).get(
            "clientDataJSON"
        )

        if not client_data:
            raise HTTPException(
                status_code=400,
                detail="Credencial WebAuthn inválida",
            )

        import json
        import base64

        client_data_bytes = base64.urlsafe_b64decode(
            client_data + "=" * (-len(client_data) % 4)
        )

        client_data_obj = json.loads(
            client_data_bytes.decode("utf-8")
        )

        challenge = client_data_obj.get("challenge")

        if not challenge:
            raise HTTPException(
                status_code=400,
                detail="Challenge WebAuthn ausente",
            )

        challenge_bytes = base64url_to_bytes(challenge)

        challenge_row = _consume_webauthn_challenge(
            conn,
            challenge=challenge_bytes,
            ceremony="registration",
            user_id=user["id"],
        )

        verified = verify_registration_response(
            credential=credential_json,
            expected_challenge=challenge_bytes,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            require_user_presence=True,
            require_user_verification=True,
        )

        credential_id = bytes_to_base64url(
            verified.credential_id
        )

        existing = conn.execute(
            """
            SELECT id
            FROM webauthn_credentials
            WHERE credential_id = ?
            """,
            (credential_id,),
        ).fetchone()

        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="Esta Passkey ya está registrada",
            )

        conn.execute(
            """
            INSERT INTO webauthn_credentials
            (
                id,
                user_id,
                credential_id,
                public_key,
                sign_count,
                transports,
                created_at,
                last_used_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                secrets.token_hex(16),
                user["id"],
                credential_id,
                bytes_to_base64url(
                    verified.credential_public_key
                ),
                verified.sign_count,
                None,
                now_iso(),
            ),
        )

        conn.commit()

        return {
            "status": "ok",
            "message": "Passkey registrada correctamente",
            "credential_id": credential_id,
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=400,
            detail=f"No se pudo registrar la Passkey: {exc}",
        )

    finally:
        conn.close()


# ============================================================
# WEBAUTHN / PASSKEY — LOGIN OPTIONS
# ============================================================

@router.post("/webauthn/login/options")
def webauthn_login_options(
    payload: WebAuthnLoginOptionsRequest,
):
    conn = get_connection()

    try:
        if payload.user_id:
            user = conn.execute(
                """
                SELECT id, name
                FROM users
                WHERE id = ?
                """,
                (payload.user_id,),
            ).fetchone()
        elif payload.name:
            user = conn.execute(
                """
                SELECT id, name
                FROM users
                WHERE lower(name) = lower(?)
                """,
                (payload.name,),
            ).fetchone()
        else:
            raise HTTPException(
                status_code=400,
                detail="Debe indicar user_id o name",
            )

        if user is None:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado",
            )

        credentials = conn.execute(
            """
            SELECT credential_id
            FROM webauthn_credentials
            WHERE user_id = ?
            """,
            (user["id"],),
        ).fetchall()

        if not credentials:
            raise HTTPException(
                status_code=404,
                detail="El usuario no tiene ninguna Passkey registrada",
            )

        allow_credentials = [
            PublicKeyCredentialDescriptor(
                id=base64url_to_bytes(row["credential_id"])
            )
            for row in credentials
        ]

        options = create_authentication_options(
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.REQUIRED,
        )

        _save_webauthn_challenge(
            conn,
            challenge=options.challenge,
            ceremony="authentication",
            user_id=user["id"],
        )

        conn.commit()

        return options_json(options)

    finally:
        conn.close()


# ============================================================
# WEBAUTHN / PASSKEY — LOGIN VERIFY
# ============================================================

@router.post("/webauthn/login/verify")
def webauthn_login_verify(
    payload: WebAuthnCredentialRequest,
    response: Response,
):
    credential_json = payload.credential

    credential_id = credential_json.get("id")

    if not credential_id:
        raise HTTPException(
            status_code=400,
            detail="Credential ID ausente",
        )

    conn = get_connection()

    try:
        credential_row = conn.execute(
            """
            SELECT
                id,
                user_id,
                credential_id,
                public_key,
                sign_count
            FROM webauthn_credentials
            WHERE credential_id = ?
            """,
            (credential_id,),
        ).fetchone()

        if credential_row is None:
            raise HTTPException(
                status_code=401,
                detail="PassKey no reconocida",
            )

        client_data = credential_json.get("response", {}).get(
            "clientDataJSON"
        )

        if not client_data:
            raise HTTPException(
                status_code=400,
                detail="Respuesta WebAuthn inválida",
            )

        import json
        import base64

        client_data_bytes = base64.urlsafe_b64decode(
            client_data + "=" * (-len(client_data) % 4)
        )

        client_data_obj = json.loads(
            client_data_bytes.decode("utf-8")
        )

        challenge = client_data_obj.get("challenge")

        if not challenge:
            raise HTTPException(
                status_code=400,
                detail="Challenge WebAuthn ausente",
            )

        challenge_bytes = base64url_to_bytes(challenge)

        _consume_webauthn_challenge(
            conn,
            challenge=challenge_bytes,
            ceremony="authentication",
            user_id=credential_row["user_id"],
        )

        verified = verify_authentication_response(
            credential=credential_json,
            expected_challenge=challenge_bytes,
            expected_rp_id=RP_ID,
            expected_origin=ORIGIN,
            credential_public_key=base64url_to_bytes(
                credential_row["public_key"]
            ),
            credential_current_sign_count=credential_row["sign_count"],
            require_user_verification=True,
        )

        conn.execute(
            """
            UPDATE webauthn_credentials
            SET sign_count = ?,
                last_used_at = ?
            WHERE id = ?
            """,
            (
                verified.new_sign_count,
                now_iso(),
                credential_row["id"],
            ),
        )

        user = conn.execute(
            """
            SELECT id, name, email, role
            FROM users
            WHERE id = ?
            """,
            (credential_row["user_id"],),
        ).fetchone()

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Usuario no encontrado",
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
            "must_change_password": False,
        }

    except HTTPException:
        raise

    except Exception as exc:
        conn.rollback()
        raise HTTPException(
            status_code=401,
            detail=f"No se pudo autenticar con Passkey: {exc}",
        )

    finally:
        conn.close()
