"""Avisos Web Push (Fase 10): suscripciones, temporizador de descanso y envío.

Las claves VAPID viven fuera del repo (por defecto data/vapid.json, o la ruta
de ENTRENAMIENTO_VAPID_FILE). Se generan en el despliegue, no en el arranque.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .database import DATA_DIR, get_connection

logger = logging.getLogger(__name__)

DEFAULT_MAILTO = "mailto:noreply@entrenos.cainca.ovh"
SCHEDULER_INTERVAL_SEC = 1.5
REST_KIND = "rest-timer"
TEST_KIND = "test"
MAX_REST_SECONDS = 600
MIN_REST_SECONDS = 1
DEFAULT_TEST_SECONDS = 5
MAX_TEST_SECONDS = 30
PUSH_TTL_SEC = 120

_VAPID_CACHE: dict[str, Any] | None = None
_SEND_PUSH: Callable[..., Any] | None = None  # inyectable en tests


def vapid_path() -> Path:
    env = os.environ.get("ENTRENAMIENTO_VAPID_FILE", "").strip()
    if env:
        return Path(env)
    return DATA_DIR / "vapid.json"


def clear_vapid_cache() -> None:
    global _VAPID_CACHE
    _VAPID_CACHE = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().strftime("%Y-%m-%dT%H:%M:%SZ")


def fire_at_iso(seconds: float) -> str:
    when = utc_now() + timedelta(seconds=max(0, seconds))
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def _public_key_b64(vapid) -> str:
    import base64

    from cryptography.hazmat.primitives import serialization

    raw = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def generate_vapid_file(path: Path, mailto: str = DEFAULT_MAILTO, overwrite: bool = False) -> dict[str, str]:
    """Crea un fichero de claves VAPID. No lo pisa a menos que overwrite=True."""
    path = Path(path)
    if path.exists() and not overwrite:
        raise FileExistsError(f"Ya existen claves VAPID en {path}")
    from py_vapid import Vapid

    vapid = Vapid()
    vapid.generate_keys()
    private_pem = vapid.private_pem()
    if isinstance(private_pem, bytes):
        private_pem = private_pem.decode("ascii")
    data = {
        "public_key": _public_key_b64(vapid),
        "private_key_pem": private_pem,
        "mailto": mailto,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    clear_vapid_cache()
    return data


def load_vapid() -> dict[str, str] | None:
    """Devuelve {public_key, private_key_pem, mailto} o None si no hay claves."""
    global _VAPID_CACHE
    if _VAPID_CACHE is not None:
        return _VAPID_CACHE
    path = vapid_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("No se pudieron leer las claves VAPID en %s: %s", path, exc)
        return None
    public_key = (data.get("public_key") or "").strip()
    private_pem = (data.get("private_key_pem") or data.get("private_key") or "").strip()
    mailto = (data.get("mailto") or DEFAULT_MAILTO).strip()
    if not mailto.startswith("mailto:") and not mailto.startswith("https:"):
        mailto = f"mailto:{mailto}"
    if not public_key or not private_pem:
        logger.error("El fichero VAPID %s no tiene public_key o private_key_pem", path)
        return None
    _VAPID_CACHE = {
        "public_key": public_key,
        "private_key_pem": private_pem,
        "mailto": mailto,
    }
    return _VAPID_CACHE


def public_key() -> str | None:
    data = load_vapid()
    return data["public_key"] if data else None


def init_push_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS push_subscriptions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                endpoint TEXT NOT NULL UNIQUE,
                p256dh TEXT NOT NULL,
                auth TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_ok_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_push_subscriptions_user
                ON push_subscriptions(user_id);

            CREATE TABLE IF NOT EXISTS scheduled_pushes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                fire_at TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS idx_scheduled_pushes_user_kind
                ON scheduled_pushes(user_id, kind);
            CREATE INDEX IF NOT EXISTS idx_scheduled_pushes_fire
                ON scheduled_pushes(fire_at);
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_subscription(user_id: str, endpoint: str, p256dh: str, auth: str) -> dict[str, Any]:
    endpoint = (endpoint or "").strip()
    p256dh = (p256dh or "").strip()
    auth = (auth or "").strip()
    if not endpoint or not endpoint.startswith("https://"):
        raise ValueError("El endpoint de la suscripción no es válido")
    if not p256dh or not auth:
        raise ValueError("Faltan las claves p256dh o auth de la suscripción")
    now = utc_now_iso()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, user_id FROM push_subscriptions WHERE endpoint = ?",
            (endpoint,),
        ).fetchone()
        if row:
            conn.execute(
                """
                UPDATE push_subscriptions
                SET user_id = ?, p256dh = ?, auth = ?, last_ok_at = ?
                WHERE endpoint = ?
                """,
                (user_id, p256dh, auth, now, endpoint),
            )
            sub_id = row["id"]
        else:
            sub_id = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO push_subscriptions
                    (id, user_id, endpoint, p256dh, auth, created_at, last_ok_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (sub_id, user_id, endpoint, p256dh, auth, now, now),
            )
        conn.commit()
        return {"id": sub_id, "endpoint": endpoint}
    finally:
        conn.close()


def delete_subscription(user_id: str, endpoint: str) -> bool:
    endpoint = (endpoint or "").strip()
    if not endpoint:
        return False
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM push_subscriptions WHERE user_id = ? AND endpoint = ?",
            (user_id, endpoint),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_subscription_by_endpoint(endpoint: str) -> None:
    conn = get_connection()
    try:
        conn.execute("DELETE FROM push_subscriptions WHERE endpoint = ?", (endpoint,))
        conn.commit()
    finally:
        conn.close()


def list_subscriptions(user_id: str) -> list[dict[str, Any]]:
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, endpoint, p256dh, auth, created_at, last_ok_at
            FROM push_subscriptions
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def cancel_scheduled(user_id: str, kind: str = REST_KIND) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM scheduled_pushes WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def schedule_push(
    user_id: str,
    seconds: float,
    payload: dict[str, Any],
    kind: str = REST_KIND,
) -> dict[str, Any]:
    """Programa un aviso. Si ya hay uno del mismo tipo para el usuario, lo sustituye."""
    fire_at = fire_at_iso(seconds)
    now = utc_now_iso()
    item_id = str(uuid.uuid4())
    body = json.dumps(payload, ensure_ascii=False)
    conn = get_connection()
    try:
        conn.execute(
            "DELETE FROM scheduled_pushes WHERE user_id = ? AND kind = ?",
            (user_id, kind),
        )
        conn.execute(
            """
            INSERT INTO scheduled_pushes (id, user_id, kind, fire_at, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (item_id, user_id, kind, fire_at, body, now),
        )
        conn.commit()
        return {"id": item_id, "fire_at": fire_at, "kind": kind}
    finally:
        conn.close()


def rest_payload(exercise_name: str | None) -> dict[str, Any]:
    name = (exercise_name or "").strip()
    if len(name) > 200:
        name = name[:200]
    body = f"Siguiente serie: {name}" if name else "Siguiente serie"
    return {
        "title": "Descanso terminado",
        "body": body,
        "tag": "rest-timer",
        "url": "/",
        "exercise_name": name,
    }


def test_payload() -> dict[str, Any]:
    return {
        "title": "Aviso de prueba",
        "body": "Si ves esto con la pantalla apagada, los avisos de descanso están listos.",
        "tag": "rest-timer-test",
        "url": "/",
    }


def _default_send(subscription_info: dict, data: str, vapid_private_key: str, vapid_claims: dict, ttl: int):
    from pywebpush import webpush

    return webpush(
        subscription_info=subscription_info,
        data=data,
        vapid_private_key=vapid_private_key,
        vapid_claims=vapid_claims,
        ttl=ttl,
        timeout=10,
    )


def get_send_push():
    return _SEND_PUSH or _default_send


def set_send_push(fn: Callable[..., Any] | None) -> None:
    global _SEND_PUSH
    _SEND_PUSH = fn


def _gone_status(status: int | None) -> bool:
    return status in {404, 410}


def send_to_subscription(sub: dict[str, Any], payload: dict[str, Any]) -> str:
    """Envía un aviso a una suscripción. Devuelve 'ok', 'gone' o 'error'."""
    vapid = load_vapid()
    if not vapid:
        logger.warning("No hay claves VAPID; no se envía el aviso")
        return "error"
    subscription_info = {
        "endpoint": sub["endpoint"],
        "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]},
    }
    try:
        get_send_push()(
            subscription_info,
            json.dumps(payload, ensure_ascii=False),
            vapid["private_key_pem"],
            {"sub": vapid["mailto"]},
            PUSH_TTL_SEC,
        )
        conn = get_connection()
        try:
            conn.execute(
                "UPDATE push_subscriptions SET last_ok_at = ? WHERE id = ?",
                (utc_now_iso(), sub["id"]),
            )
            conn.commit()
        finally:
            conn.close()
        return "ok"
    except Exception as exc:
        status = getattr(exc, "status_code", None)
        if _gone_status(status):
            logger.info("Suscripción caducada (%s): se elimina %s", status, sub.get("endpoint"))
            delete_subscription_by_endpoint(sub["endpoint"])
            return "gone"
        logger.warning("Fallo al enviar push a %s: %s", sub.get("endpoint"), exc)
        return "error"


def send_to_user(user_id: str, payload: dict[str, Any]) -> dict[str, int]:
    subs = list_subscriptions(user_id)
    counts = {"ok": 0, "gone": 0, "error": 0, "total": len(subs)}
    for sub in subs:
        result = send_to_subscription(sub, payload)
        counts[result] = counts.get(result, 0) + 1
    return counts


def process_due_pushes(now_iso: str | None = None) -> int:
    """Reclama y envía los avisos vencidos. Devuelve cuántos se procesaron."""
    now = now_iso or utc_now_iso()
    conn = get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, user_id, kind, fire_at, payload
            FROM scheduled_pushes
            WHERE fire_at <= ?
            ORDER BY fire_at
            """,
            (now,),
        ).fetchall()
        due = [dict(r) for r in rows]
        if due:
            conn.executemany(
                "DELETE FROM scheduled_pushes WHERE id = ?",
                [(r["id"],) for r in due],
            )
            conn.commit()
    finally:
        conn.close()

    sent = 0
    for item in due:
        try:
            payload = json.loads(item["payload"]) if item["payload"] else {}
        except json.JSONDecodeError:
            payload = rest_payload(None)
        if not isinstance(payload, dict):
            payload = rest_payload(None)
        send_to_user(item["user_id"], payload)
        sent += 1
    return sent


def should_start_scheduler() -> bool:
    if os.environ.get("PYTEST_VERSION"):
        return False
    if os.environ.get("ENTRENAMIENTO_PUSH_SCHEDULER", "1") == "0":
        return False
    return True


_scheduler_task = None


def start_scheduler() -> None:
    """Lanza el bucle en segundo plano (solo fuera de tests)."""
    global _scheduler_task
    if not should_start_scheduler():
        logger.info("Bucle de avisos push no arrancado (tests o desactivado)")
        return
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        logger.warning("No hay bucle asyncio; no se arranca el programador de push")
        return
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _scheduler_task = loop.create_task(push_scheduler_loop())
    logger.info("Bucle de avisos push arrancado")


def stop_scheduler() -> None:
    global _scheduler_task
    if _scheduler_task is not None and not _scheduler_task.done():
        _scheduler_task.cancel()
    _scheduler_task = None


async def push_scheduler_loop() -> None:
    import asyncio

    while True:
        try:
            await asyncio.to_thread(process_due_pushes)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Error en el bucle de avisos push")
        await asyncio.sleep(SCHEDULER_INTERVAL_SEC)


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Claves VAPID para avisos de descanso")
    parser.add_argument("--generate", action="store_true", help="Genera claves si no existen")
    parser.add_argument("--force", action="store_true", help="Pisa el fichero de claves")
    parser.add_argument("--path", default="", help="Ruta del fichero (por defecto data/vapid.json)")
    parser.add_argument("--mailto", default=DEFAULT_MAILTO)
    parser.add_argument("--show-public", action="store_true", help="Muestra la clave pública")
    args = parser.parse_args(argv)
    path = Path(args.path) if args.path else vapid_path()
    if args.generate:
        try:
            data = generate_vapid_file(path, mailto=args.mailto, overwrite=args.force)
            print(f"OK claves VAPID en {path}")
            print(f"public_key={data['public_key']}")
            return 0
        except FileExistsError as exc:
            print(str(exc))
            if args.show_public:
                loaded = load_vapid()
                if loaded:
                    print(f"public_key={loaded['public_key']}")
            return 0
    if args.show_public:
        loaded = load_vapid()
        if not loaded:
            print(f"No hay claves VAPID en {path}", file=sys.stderr)
            return 1
        print(loaded["public_key"])
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
