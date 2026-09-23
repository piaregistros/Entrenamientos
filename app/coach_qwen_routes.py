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
QWEN_MODEL = os.environ.get("QWEN_MODEL", "qwen3.5-9b-mlx")
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


def _extract_text(data: dict) -> str:
    choice = (data.get("choices") or [{}])[0]
    msg = choice.get("message") or {}
    for key in ("content", "reasoning_content", "reasoning"):
        val = msg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
        if isinstance(val, list):
            parts = []
            for p in val:
                if isinstance(p, str):
                    parts.append(p)
                elif isinstance(p, dict) and p.get("text"):
                    parts.append(str(p["text"]))
            if parts:
                return "".join(parts).strip()
    if isinstance(choice.get("text"), str) and choice["text"].strip():
        return choice["text"].strip()
    return ""


def _qwen(messages: list[dict]) -> str:
    import urllib.request
    payload = json.dumps({
        "model": QWEN_MODEL,
        "messages": messages,
        "temperature": 0.5,
        "max_tokens": 900,
    }).encode()
    req = urllib.request.Request(
        f"{QWEN_BASE}/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {QWEN_KEY}"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    return _extract_text(data)


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


def _facts_block(facts: dict) -> str:
    last = facts.get("last_logged") or {}
    nxt = facts.get("next_routine") or {}
    declared = facts.get("user_declared")
    overlap = facts.get("direct_overlap") or []
    lines = [
        f"Hoy: {facts.get('today')}",
        f"Último en la app: {last.get('routine_name')} ({last.get('date')})" if last else "Sin entreno registrado.",
        f"El usuario ha dicho que hizo: {declared.get('routine_name')}" if declared else "Sin declaración extra.",
        f"Siguiente por orden: {nxt.get('name')}",
        f"Rutinas: {', '.join(str(x) for x in (facts.get('available_routines') or []))}",
        f"Solape directo: {', '.join(overlap) if overlap else 'ninguno'}",
    ]
    for a in facts.get("adaptations") or []:
        lines.append(f"Sustitución {a['from']}: {', '.join(a['to']) or 'sin alternativa'}")
    lines.append("El RIR no demuestra recuperación.")
    return "\n".join(lines)


SYSTEM = """Eres un compañero de gym. Español natural, frases cortas, sin informe.

Si te saludan o hablan de cualquier cosa que no sea el plan A/B/C: responde como persona.
No copies la lista de hechos. No empieces por "En la app el último registrado".

Solo si preguntan qué toca, solape o si pueden entrenar: usa HECHOS y no inventes sesiones.
Orden A→B→C→A. Si dice que hizo B y no está en la app, créele en este chat.

Suplementos, sueño, hambre: opina con sentido común. Una cautela basta.
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
    if not _is_training_q(msg) and re.fullmatch(r"(hola|hey|buenas|buenos días|qué tal)[!?\s]*", msg.lower()):
        fallback = "Hola. ¿Entreno, dieta o lo que se te ocurra?"

    sys = SYSTEM
    if _is_training_q(msg):
        sys += "\nHECHOS:\n" + _facts_block(facts)
    messages = [{"role": "system", "content": sys}]
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
        answer = fallback if _is_training_q(msg) else "Ahora mismo no llego al modelo. Prueba otra vez."

    conn = get_connection()
    try:
        conn.execute("INSERT INTO coach_v2_messages(id, conversation_id, role, content) VALUES(?,?,?,?)",
                     (str(uuid4()), cid, "assistant", answer))
        conn.commit()
    finally:
        conn.close()
    return {"conversation_id": cid, "answer": answer, "provider": "qwen", "model": QWEN_MODEL}
