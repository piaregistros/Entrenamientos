"""Coach Qwen: hechos en entrenos; conversación normal en el resto."""
from __future__ import annotations

import json
import os
import re
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import get_authenticated_user
from .database import get_connection
from .coach_facts import build_facts, fallback_answer

router = APIRouter(prefix="/api/coach", tags=["coach-qwen"])

QWEN_BASE = os.environ.get("QWEN_BASE_URL", "http://100.68.49.74:1234/v1")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen2.5-coder-7b-instruct")
QWEN_KEY = os.environ.get("QWEN_API_KEY", "not-needed")


def init_coach_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS coach_v2_conversations (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, mode TEXT NOT NULL DEFAULT 'coach',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS coach_v2_messages (
            id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL,
            content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        """
    )
    conn.commit()
    conn.close()


class ChatIn(BaseModel):
    message: str
    conversation_id: str | None = None
    mode: str = "coach"


def _qwen(messages: list[dict]) -> str:
    import urllib.request
    payload = json.dumps({"model": QWEN_MODEL, "messages": messages, "temperature": 0.45, "max_tokens": 700}).encode()
    req = urllib.request.Request(
        f"{QWEN_BASE}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {QWEN_KEY}"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"].strip()


def _is_training_q(text: str) -> bool:
    t = text.lower()
    return any(w in t for w in (
        "solap", "entren", "rutina", "día 1", "dia 1", "día 2", "dia 2", "día 3", "dia 3",
        "puedo hacer", "debo entren", "qué me toca", "que me toca", "mañana qué", "mañana que",
        "hice la", "hice el", "prensa", "ejercicio",
    ))


def _next_letter(facts: dict) -> str:
    name = ((facts.get("next_routine") or {}).get("name") or "").upper()
    m = re.search(r"\b([ABC])\b", name)
    return m.group(1) if m else ""


def _violates(answer: str, facts: dict, user_msg: str) -> bool:
    if not _is_training_q(user_msg):
        return False
    t = answer.lower()
    if facts.get("direct_overlap") and re.search(r"no hay solap", t):
        return True
    if "buena recuperaci" in t and "rir" in t:
        return True
    nxt = _next_letter(facts)
    if nxt == "C" and "c" in t and "no está programada" in t:
        return True
    return False


SYSTEM = """Eres un compañero de gym que habla claro, en español, sin relleno corporativo.

ENTRENOS (A/B/C, solape, qué toca mañana): obedece HECHOS. No inventes un entreno que no esté ahí.
Orden A→B→C→A. Si el usuario dice que hizo B y no está en la app, créele en este chat.

TODO LO DEMÁS (suplementos, sueño, hambre, motivación, técnica general): conversa con naturalidad.
Puedes opinar con lo que se suele considerar razonable (p. ej. proteína, creatina, omega-3, magnesio,
sueño, no milagros). Una frase de cautela basta; no bloquee la charla ni repitas "consulta a un profesional"
en cada mensaje. No vendas marcas. No des dosis de receta médica.

Nada de "como modelo de IA no puedo". Sé útil y directo.
"""


@router.get("/health")
def coach_health():
    return {"ok": True, "provider": "qwen", "model": QWEN_MODEL, "base": QWEN_BASE}


@router.post("/chat")
def chat(body: ChatIn, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    msg = (body.message or "").strip()
    if not msg:
        raise HTTPException(400, "Mensaje vacío")
    conn = get_connection()
    try:
        cid = body.conversation_id
        if cid:
            row = conn.execute("SELECT id, mode FROM coach_v2_conversations WHERE id=? AND user_id=?", (cid, current_user["id"])).fetchone()
            if not row:
                raise HTTPException(404, "Conversación no encontrada")
            if row["mode"] != body.mode:
                raise HTTPException(409, "Esta conversación es de otro modo")
        else:
            cid = str(uuid4())
            conn.execute("INSERT INTO coach_v2_conversations(id, user_id, mode) VALUES(?,?,?)", (cid, current_user["id"], body.mode))
        history = conn.execute(
            "SELECT role, content FROM coach_v2_messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 12",
            (cid,),
        ).fetchall()
        history = list(reversed([dict(h) for h in history]))
        hist_txt = "\n".join(h["content"] for h in history if h["role"] == "user")
        facts = build_facts(conn, current_user["id"], msg, hist_txt)
        conn.execute("INSERT INTO coach_v2_messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
                     (str(uuid4()), cid, "user", msg))
        conn.commit()
    finally:
        conn.close()

    fallback = fallback_answer(facts, msg)
    messages = [{"role": "system", "content": SYSTEM + "\nHECHOS:\n" + json.dumps(facts, ensure_ascii=False, default=str)}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": msg})
    try:
        answer = _qwen(messages)
        if _is_training_q(msg) and (not answer or _violates(answer, facts, msg)):
            answer = fallback
        if not answer:
            answer = fallback
    except Exception:
        answer = fallback if _is_training_q(msg) else "Ahora mismo no llego a Qwen. Prueba de nuevo."

    conn = get_connection()
    try:
        conn.execute("INSERT INTO coach_v2_messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
                     (str(uuid4()), cid, "assistant", answer))
        conn.commit()
    finally:
        conn.close()
    return {"conversation_id": cid, "answer": answer, "facts": facts, "provider": "qwen"}
