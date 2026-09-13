from __future__ import annotations

import base64
import json
import secrets
from datetime import datetime, timezone

from webauthn import (
    generate_registration_options,
    generate_authentication_options,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.cose import COSEAlgorithmIdentifier
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)


# ============================================================
# CONFIGURACIÓN DE LA APLICACIÓN
# ============================================================

RP_ID = "entrenos.cainca.ovh"
RP_NAME = "Entrenamiento"
ORIGIN = "https://entrenos.cainca.ovh"

WEBAUTHN_TIMEOUT_MS = 60_000


# ============================================================
# UTILIDADES
# ============================================================

def generate_challenge() -> bytes:
    """
    Genera un challenge criptográficamente seguro.
    """
    return secrets.token_bytes(32)


def encode_bytes(value: bytes) -> str:
    """
    Base64 URL-safe sin padding.
    """
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_bytes(value: str) -> bytes:
    """
    Decodifica Base64 URL-safe con o sin padding.
    """
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# REGISTRO DE PASSKEY
# ============================================================

def create_registration_options(
    *,
    user_id: str,
    user_name: str,
    user_display_name: str,
    exclude_credentials=None,
):
    """
    Genera las opciones que el navegador utilizará para registrar
    una nueva Passkey.
    """

    return generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_name=user_name,
        user_id=user_id.encode("utf-8"),
        user_display_name=user_display_name,
        challenge=generate_challenge(),
        timeout=WEBAUTHN_TIMEOUT_MS,
        authenticator_selection=AuthenticatorSelectionCriteria(
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
        exclude_credentials=exclude_credentials,
        supported_pub_key_algs=[
            COSEAlgorithmIdentifier.EDDSA,
            COSEAlgorithmIdentifier.ECDSA_SHA_256,
            COSEAlgorithmIdentifier.RSASSA_PKCS1_v1_5_SHA_256,
        ],
    )


# ============================================================
# AUTENTICACIÓN
# ============================================================

def create_authentication_options(
    *,
    allow_credentials=None,
    user_verification: UserVerificationRequirement = (
        UserVerificationRequirement.REQUIRED
    ),
):
    """
    Genera las opciones que el navegador utilizará para
    autenticar una Passkey.
    """

    return generate_authentication_options(
        rp_id=RP_ID,
        challenge=generate_challenge(),
        timeout=WEBAUTHN_TIMEOUT_MS,
        allow_credentials=allow_credentials,
        user_verification=user_verification,
    )


def options_json(options) -> dict:
    """
    Convierte las opciones WebAuthn al JSON que espera
    navigator.credentials.create()/get().
    """

    return json.loads(options_to_json(options))
