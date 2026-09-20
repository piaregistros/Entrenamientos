"""Coach Qwen: backend calcula hechos, Qwen redacta, validador corrige."""
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
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            mode TEXT NOT NULL DEFAULT 'coach',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS coach_v2_messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
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
    payload = json.dumps({
        "model": QWEN_MODEL,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 500,
    }).encode()
    req = urllib.request.Request(
        f"{QWEN_BASE}/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {QWEN_KEY}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode())
    return data["choices"][0]["message"]["content"].strip()


def _violates(answer: str, facts: dict) -> bool:
    t = answer.lower()
    overlap = facts.get("direct_overlap") or []
    if overlap and re.search(r"no hay solap", t):
        return True
    if not overlap and "solapamiento directo:" in t and "ninguno" not in t:
        pass
    if "buena recuperaci" in t and "rir" in t:
        return True
    last = facts.get("last_logged")
    if last and last.get("date") and last["date"][:7] not in answer and last.get("routine_name", "") not in answer:
        # no obligatorio citar fecha
        pass
    return False


SYSTEM = """Eres el Coach de Entrenamientos.
Redactas en español, breve y natural.
NO inventes entrenamientos, fechas, kilos ni ejercicios.
Usa SOLO el bloque HECHOS. Si un hecho dice que hay solapamiento, no lo niegues.
El RIR no prueba recuperación. No des consejo médico.
Si el usuario declara un entreno no guardado, úsalo solo en esta conversación.
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
        facts = build_facts(conn, current_user["id"], msg)
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
            "SELECT role, content FROM coach_v2_messages WHERE conversation_id=? ORDER BY created_at DESC LIMIT 8",
            (cid,),
        ).fetchall()
        history = list(reversed([dict(h) for h in history]))
        conn.execute("INSERT INTO coach_v2_messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
                     (str(uuid4()), cid, "user", msg))
        conn.commit()
    finally:
        conn.close()

    fallback = fallback_answer(facts, msg)
    facts_block = json.dumps(facts, ensure_ascii=False, default=str)
    messages = [{"role": "system", "content": SYSTEM + "\nHECHOS:\n" + facts_block}]
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": msg})

    try:
        answer = _qwen(messages)
        if not answer or _violates(answer, facts):
            answer = fallback
    except Exception:
        answer = fallback

    conn = get_connection()
    try:
        conn.execute("INSERT INTO coach_v2_messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
                     (str(uuid4()), cid, "assistant", answer))
        conn.commit()
    finally:
        conn.close()
    return {"conversation_id": cid, "answer": answer, "facts": facts, "provider": "qwen"}
