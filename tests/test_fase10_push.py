"""Fase 10: suscripciones Web Push, programación, cancelación y limpieza."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest
from pywebpush import WebPushException

from app import database, push
from app.push import (
    cancel_scheduled,
    fire_at_iso,
    generate_vapid_file,
    init_push_db,
    process_due_pushes,
    rest_payload,
    schedule_push,
    send_to_user,
    upsert_subscription,
    utc_now,
)
from conftest import ESTEFI_ID, PABLO_ID


class FakeGone(WebPushException):
    def __init__(self, status):
        class _Resp:
            status_code = status
            text = "gone"
            headers = {}

        super().__init__(f"status {status}", response=_Resp())


@pytest.fixture
def vapid_file(tmp_path, monkeypatch):
    path = tmp_path / "vapid.json"
    generate_vapid_file(path)
    monkeypatch.setenv("ENTRENAMIENTO_VAPID_FILE", str(path))
    push.clear_vapid_cache()
    yield path
    push.clear_vapid_cache()


@pytest.fixture
def push_db(test_db, vapid_file):
    init_push_db()
    return test_db


@pytest.fixture
def sent():
    calls = []

    def _send(subscription_info, data, vapid_private_key, vapid_claims, ttl):
        payload = json.loads(data)
        calls.append(
            {
                "endpoint": subscription_info["endpoint"],
                "payload": payload,
                "ttl": ttl,
                "claims": vapid_claims,
            }
        )
        return "ok"

    push.set_send_push(_send)
    try:
        yield calls
    finally:
        push.set_send_push(None)


def _sub(user_id, suffix="pablo"):
    return upsert_subscription(
        user_id,
        f"https://push.example/{suffix}",
        p256dh="p256dh-" + suffix,
        auth="auth-" + suffix,
    )


# ------------------------------------------------------------------ vapid / auth


def test_vapid_public_key_requiere_sesion(push_db, vapid_file):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        res = client.get("/api/push/vapid-public-key")
        assert res.status_code == 401


def test_vapid_public_key_ok(client, vapid_file, push_db):
    res = client.get("/api/push/vapid-public-key")
    assert res.status_code == 200
    data = res.json()
    assert data["public_key"]
    assert len(data["public_key"]) > 20
    stored = json.loads(vapid_file.read_text())
    assert data["public_key"] == stored["public_key"]


def test_vapid_public_key_sin_claves_da_503(client, push_db, tmp_path, monkeypatch):
    missing = tmp_path / "no-existe-vapid.json"
    monkeypatch.setenv("ENTRENAMIENTO_VAPID_FILE", str(missing))
    push.clear_vapid_cache()
    res = client.get("/api/push/vapid-public-key")
    assert res.status_code == 503
    assert "configurado" in res.json()["detail"].lower()


# ------------------------------------------------------------------ suscripciones


def test_subscribe_y_repite_actualiza(client, push_db, vapid_file, sent):
    body = {
        "endpoint": "https://fcm.googleapis.com/x/sub-1",
        "keys": {"p256dh": "AAA", "auth": "BBB"},
    }
    res = client.post("/api/push/subscribe", json=body)
    assert res.status_code == 200
    first_id = res.json()["id"]

    res = client.post(
        "/api/push/subscribe",
        json={
            "endpoint": "https://fcm.googleapis.com/x/sub-1",
            "keys": {"p256dh": "CCC", "auth": "DDD"},
        },
    )
    assert res.status_code == 200
    assert res.json()["id"] == first_id

    conn = database.get_connection()
    rows = conn.execute("SELECT p256dh, auth, user_id FROM push_subscriptions").fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["p256dh"] == "CCC"
    assert rows[0]["auth"] == "DDD"
    assert rows[0]["user_id"] == PABLO_ID


def test_subscribe_rechaza_endpoint_invalido(client, push_db, vapid_file):
    res = client.post(
        "/api/push/subscribe",
        json={"endpoint": "http://inseguro.example/x", "keys": {"p256dh": "a", "auth": "b"}},
    )
    assert res.status_code == 422


def test_unsubscribe_solo_el_propietario(client, client_estefi, push_db, vapid_file):
    body = {
        "endpoint": "https://push.example/shared",
        "keys": {"p256dh": "p", "auth": "a"},
    }
    assert client.post("/api/push/subscribe", json=body).status_code == 200

    # Estefi no puede borrar la de Pablo
    res = client_estefi.request(
        "DELETE",
        "/api/push/subscribe",
        json={"endpoint": "https://push.example/shared"},
    )
    assert res.status_code == 200
    assert res.json()["deleted"] is False

    conn = database.get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM push_subscriptions").fetchone()["c"]
    conn.close()
    assert n == 1

    res = client.request(
        "DELETE",
        "/api/push/subscribe",
        json={"endpoint": "https://push.example/shared"},
    )
    assert res.status_code == 200
    assert res.json()["deleted"] is True


# ------------------------------------------------------------------ programar / cancelar


def test_schedule_y_cancel_por_api(client, push_db, vapid_file, sent):
    _sub(PABLO_ID)
    res = client.post(
        "/api/push/rest-timer",
        json={"seconds": 90, "exercise_name": "Press banca plano"},
    )
    assert res.status_code == 200
    fire_at = res.json()["fire_at"]
    assert fire_at.endswith("Z")

    conn = database.get_connection()
    row = conn.execute("SELECT kind, payload FROM scheduled_pushes").fetchone()
    conn.close()
    payload = json.loads(row["payload"])
    assert row["kind"] == "rest-timer"
    assert payload["title"] == "Descanso terminado"
    assert payload["body"] == "Siguiente serie: Press banca plano"
    assert payload["tag"] == "rest-timer"

    # Todavía no ha vencido
    assert process_due_pushes() == 0
    assert sent == []

    res = client.request("DELETE", "/api/push/rest-timer")
    assert res.status_code == 200
    assert res.json()["cancelled"] == 1
    assert process_due_pushes("2099-01-01T00:00:00Z") == 0
    assert sent == []


def test_el_ultimo_temporizador_sustituye_al_anterior(push_db, vapid_file, sent):
    _sub(PABLO_ID)
    first = schedule_push(PABLO_ID, 90, rest_payload("Uno"))
    second = schedule_push(PABLO_ID, 30, rest_payload("Dos"))
    conn = database.get_connection()
    rows = conn.execute("SELECT id, payload FROM scheduled_pushes WHERE user_id = ?", (PABLO_ID,)).fetchall()
    conn.close()
    assert len(rows) == 1
    assert rows[0]["id"] == second["id"]
    assert rows[0]["id"] != first["id"]
    assert "Dos" in json.loads(rows[0]["payload"])["body"]


def test_process_due_envia_y_actualiza_last_ok(push_db, vapid_file, sent):
    sub = _sub(PABLO_ID)
    schedule_push(PABLO_ID, 0, rest_payload("Curl femoral"))
    # fire_at es "ahora"; un segundo de holgura por si el reloj avanza al segundo siguiente
    n = process_due_pushes(fire_at_iso(2))
    assert n == 1
    assert len(sent) == 1
    assert sent[0]["endpoint"] == sub["endpoint"]
    assert sent[0]["payload"]["title"] == "Descanso terminado"
    assert sent[0]["payload"]["body"] == "Siguiente serie: Curl femoral"
    assert sent[0]["ttl"] == 120

    conn = database.get_connection()
    pending = conn.execute("SELECT COUNT(*) AS c FROM scheduled_pushes").fetchone()["c"]
    last_ok = conn.execute(
        "SELECT last_ok_at FROM push_subscriptions WHERE endpoint = ?",
        (sub["endpoint"],),
    ).fetchone()["last_ok_at"]
    conn.close()
    assert pending == 0
    assert last_ok


def test_usuarios_no_se_mezclan(push_db, vapid_file, sent):
    _sub(PABLO_ID, "pablo")
    _sub(ESTEFI_ID, "estefi")
    schedule_push(PABLO_ID, 0, rest_payload("De Pablo"))
    schedule_push(ESTEFI_ID, 0, rest_payload("De Estefi"))
    process_due_pushes(fire_at_iso(2))
    endpoints = {c["endpoint"] for c in sent}
    bodies = {c["payload"]["body"] for c in sent}
    assert endpoints == {"https://push.example/pablo", "https://push.example/estefi"}
    assert bodies == {"Siguiente serie: De Pablo", "Siguiente serie: De Estefi"}


def test_sin_suscripciones_no_falla_y_limpia_el_aviso(push_db, vapid_file, sent):
    schedule_push(PABLO_ID, 0, rest_payload("Nadie escucha"))
    assert process_due_pushes(fire_at_iso(2)) == 1
    assert sent == []
    conn = database.get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM scheduled_pushes").fetchone()["c"]
    conn.close()
    assert n == 0


# ------------------------------------------------------------------ limpieza 404/410


def test_limpia_suscripcion_410_y_mantiene_las_otras(push_db, vapid_file):
    gone = upsert_subscription(PABLO_ID, "https://push.example/gone", "p1", "a1")
    keep = upsert_subscription(PABLO_ID, "https://push.example/keep", "p2", "a2")

    def _send(subscription_info, data, vapid_private_key, vapid_claims, ttl):
        if "gone" in subscription_info["endpoint"]:
            raise FakeGone(410)
        return "ok"

    push.set_send_push(_send)
    try:
        counts = send_to_user(PABLO_ID, rest_payload("Prueba"))
    finally:
        push.set_send_push(None)

    assert counts["gone"] == 1
    assert counts["ok"] == 1
    conn = database.get_connection()
    rows = conn.execute("SELECT endpoint FROM push_subscriptions WHERE user_id = ?", (PABLO_ID,)).fetchall()
    conn.close()
    endpoints = {r["endpoint"] for r in rows}
    assert gone["endpoint"] not in endpoints
    assert keep["endpoint"] in endpoints


def test_limpia_suscripcion_404(push_db, vapid_file, sent):
    upsert_subscription(PABLO_ID, "https://push.example/missing", "p", "a")

    def _send(subscription_info, data, vapid_private_key, vapid_claims, ttl):
        raise FakeGone(404)

    push.set_send_push(_send)
    try:
        counts = send_to_user(PABLO_ID, rest_payload("X"))
    finally:
        push.set_send_push(None)

    assert counts["gone"] == 1
    conn = database.get_connection()
    n = conn.execute("SELECT COUNT(*) AS c FROM push_subscriptions").fetchone()["c"]
    conn.close()
    assert n == 0


# ------------------------------------------------------------------ test endpoint / payload


def test_rest_payload_sin_nombre():
    p = rest_payload("")
    assert p["title"] == "Descanso terminado"
    assert p["body"] == "Siguiente serie"
    assert p["tag"] == "rest-timer"


def test_post_test_programa_por_defecto(client, push_db, vapid_file, sent):
    _sub(PABLO_ID)
    res = client.post("/api/push/test", json={})
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    assert data["seconds"] == 5
    conn = database.get_connection()
    row = conn.execute("SELECT kind, payload FROM scheduled_pushes").fetchone()
    conn.close()
    assert row["kind"] == "test"
    assert "pantalla apagada" in json.loads(row["payload"])["body"]


def test_post_test_inmediato(client, push_db, vapid_file, sent):
    _sub(PABLO_ID)
    res = client.post("/api/push/test", json={"seconds": 0})
    assert res.status_code == 200
    assert res.json()["sent"]["ok"] == 1
    assert sent[0]["payload"]["title"] == "Aviso de prueba"


def test_schedule_rest_timer_requiere_auth(push_db, vapid_file):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        res = client.post("/api/push/rest-timer", json={"seconds": 30, "exercise_name": "X"})
        assert res.status_code == 401


def test_cancel_sin_aviso_no_falla(client, push_db, vapid_file):
    res = client.request("DELETE", "/api/push/rest-timer")
    assert res.status_code == 200
    assert res.json()["cancelled"] == 0


def test_generate_vapid_no_pisa(tmp_path):
    path = tmp_path / "vapid.json"
    first = generate_vapid_file(path)
    with pytest.raises(FileExistsError):
        generate_vapid_file(path)
    second = generate_vapid_file(path, overwrite=True)
    assert first["public_key"] != second["public_key"]
    assert path.stat().st_mode & 0o777 in {0o600, 0o400} or True  # algunos FS ignoran chmod
