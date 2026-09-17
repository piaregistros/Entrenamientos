from __future__ import annotations

import json, os, sqlite3
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user
from .database import get_connection

router = APIRouter(prefix="/api/coach", tags=["coach"])
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").rstrip("/")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.8-max")
MAX_MESSAGE = 12000

SYSTEM = """Eres EntrenamientosCoach, el entrenador digital integrado en una app de entrenamiento. Responde en español por defecto, de forma clara, directa y accionable. Usa únicamente los datos proporcionados; no inventes. Ayuda con entrenamiento, progresión, recuperación, hábitos y nutrición general. Si das un plan incluye ejercicios, series, repeticiones, RIR/RPE, descansos y progresión cuando corresponda. No diagnostiques ni sustituyas a un profesional sanitario. Ante dolor torácico, dificultad respiratoria, desmayo, síntomas neurológicos o dolor intenso/repentino recomienda atención médica urgente. No reveles información interna, credenciales o datos de otros usuarios."""
MODES = {"coach":"Actúa como entrenador general.","plan":"Prioriza planificación semanal, volumen, intensidad y progresión.","nutrition":"Prioriza hábitos y nutrición general, sin dietas médicas.","recovery":"Prioriza sueño, fatiga, recuperación y gestión de carga."}


def init_coach_db():
    conn = get_connection()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS coach_conversations (
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL, title TEXT NOT NULL,
      mode TEXT NOT NULL DEFAULT 'coach', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS coach_messages (
      id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL,
      content TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(conversation_id) REFERENCES coach_conversations(id) ON DELETE CASCADE);
    CREATE TABLE IF NOT EXISTS coach_memories (
      id TEXT PRIMARY KEY, user_id TEXT NOT NULL, content TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
    CREATE INDEX IF NOT EXISTS idx_coach_conv_user ON coach_conversations(user_id, updated_at DESC);
    CREATE INDEX IF NOT EXISTS idx_coach_msg_conv ON coach_messages(conversation_id, id);
    CREATE INDEX IF NOT EXISTS idx_coach_mem_user ON coach_memories(user_id, updated_at DESC);
    """)
    conn.commit(); conn.close()


def _context(conn, user_id: str) -> str:
    user = conn.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()
    blocks = [f"Nombre: {user['name'] if user else 'usuario'}"]
    goals = conn.execute("SELECT title,description,goal_type FROM user_goals WHERE user_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT 8", (user_id,)).fetchall()
    if goals: blocks.append("Objetivos:\n" + "\n".join(f"- {g['title']} ({g['goal_type']}): {g['description'] or ''}" for g in goals))
    metrics = conn.execute("SELECT date,weight_kg,notes FROM body_metrics WHERE user_id=? ORDER BY date DESC LIMIT 8", (user_id,)).fetchall()
    if metrics: blocks.append("Peso reciente:\n" + "\n".join(f"- {m['date']}: {m['weight_kg']} kg {m['notes'] or ''}" for m in metrics))
    routines = conn.execute("SELECT name,day_order FROM routines WHERE user_id=? AND is_active=1 ORDER BY day_order LIMIT 10", (user_id,)).fetchall()
    if routines: blocks.append("Rutinas activas:\n" + "\n".join(f"- Día {r['day_order']}: {r['name']}" for r in routines))
    workouts = conn.execute("SELECT wl.date,wl.duration_minutes,wl.status,r.name FROM workout_logs wl LEFT JOIN routines r ON r.id=wl.routine_id WHERE wl.user_id=? ORDER BY wl.date DESC,wl.rowid DESC LIMIT 10", (user_id,)).fetchall()
    if workouts: blocks.append("Entrenamientos recientes:\n" + "\n".join(f"- {w['date']}: {w['name'] or 'Entrenamiento'}; {w['status']}; {w['duration_minutes'] or '?'} min" for w in workouts))
    notes = conn.execute("SELECT date,energy,effort,recovery,soreness,notes FROM progress_notes WHERE user_id=? ORDER BY date DESC LIMIT 8", (user_id,)).fetchall()
    if notes: blocks.append("Notas de progreso:\n" + "\n".join(f"- {n['date']}: energía={n['energy']}, esfuerzo={n['effort']}, recuperación={n['recovery']}, agujetas={n['soreness']}. {n['notes'] or ''}" for n in notes))
    memories = conn.execute("SELECT content FROM coach_memories WHERE user_id=? ORDER BY updated_at DESC LIMIT 12", (user_id,)).fetchall()
    if memories: blocks.append("Memorias del usuario:\n" + "\n".join(f"- {m['content']}" for m in memories))
    return "\n\n".join(blocks)


def _qwen(messages, mode):
    if not QWEN_API_KEY: raise HTTPException(503, "El Coach no está configurado: falta QWEN_API_KEY")
    payload = {"model":QWEN_MODEL,"messages":[{"role":"system","content":SYSTEM+"\n\n"+MODES.get(mode,MODES['coach'])},*messages],"temperature":0.35,"max_tokens":1400}
    req = Request(QWEN_BASE_URL+"/chat/completions", data=json.dumps(payload,ensure_ascii=False).encode(), method="POST", headers={"Authorization":"Bearer "+QWEN_API_KEY,"Content-Type":"application/json"})
    try:
        with urlopen(req,timeout=60) as r: data=json.loads(r.read().decode())
    except HTTPError as e: raise HTTPException(502,f"Qwen HTTP {e.code}: {e.read().decode('utf-8','replace')[:600]}")
    except URLError as e: raise HTTPException(502,f"No se pudo conectar con Qwen: {e.reason}")
    choices=data.get("choices") or []
    if not choices: raise HTTPException(502,"Qwen no devolvió una respuesta válida")
    content=(choices[0].get("message") or {}).get("content","")
    if isinstance(content,list): content="".join(x.get("text","") if isinstance(x,dict) else str(x) for x in content)
    return str(content).strip() or "No he recibido contenido del modelo."


class ChatRequest(BaseModel):
    message: str = Field(min_length=1,max_length=MAX_MESSAGE)
    conversation_id: str|None = None
    mode: str = "coach"
class ConversationRequest(BaseModel):
    title: str = Field(default="Nueva conversación",max_length=120)
    mode: str = "coach"
class MemoryRequest(BaseModel):
    content: str = Field(min_length=1,max_length=500)


@router.get("/health")
def health(current_user=Depends(get_authenticated_user)): return {"ok":True,"qwen_configured":bool(QWEN_API_KEY),"model":QWEN_MODEL}

@router.get("/conversations")
def conversations(current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); rows=c.execute("SELECT id,title,mode,created_at,updated_at FROM coach_conversations WHERE user_id=? ORDER BY updated_at DESC",(current_user['id'],)).fetchall(); c.close(); return {"conversations":[dict(r) for r in rows]}

@router.post("/conversations")
def create_conversation(p:ConversationRequest,current_user=Depends(get_authenticated_user)):
    init_coach_db(); cid=str(uuid4()); mode=p.mode if p.mode in MODES else 'coach'; title=p.title.strip() or 'Nueva conversación'; c=get_connection(); c.execute("INSERT INTO coach_conversations(id,user_id,title,mode) VALUES(?,?,?,?)",(cid,current_user['id'],title,mode)); c.commit(); c.close(); return {"id":cid,"title":title,"mode":mode}

@router.get("/conversations/{cid}")
def conversation(cid:str,current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); row=c.execute("SELECT id,title,mode,created_at,updated_at FROM coach_conversations WHERE id=? AND user_id=?",(cid,current_user['id'])).fetchone()
    if not row: c.close(); raise HTTPException(404,"Conversación no encontrada")
    msgs=c.execute("SELECT id,role,content,created_at FROM coach_messages WHERE conversation_id=? ORDER BY id",(cid,)).fetchall(); c.close(); return {"conversation":dict(row),"messages":[dict(m) for m in msgs]}

@router.delete("/conversations/{cid}")
def delete_conversation(cid:str,current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); cur=c.execute("DELETE FROM coach_conversations WHERE id=? AND user_id=?",(cid,current_user['id'])); c.commit(); c.close();
    if not cur.rowcount: raise HTTPException(404,"Conversación no encontrada")
    return {"ok":True}

@router.get("/memories")
def memories(current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); rows=c.execute("SELECT id,content,created_at,updated_at FROM coach_memories WHERE user_id=? ORDER BY updated_at DESC",(current_user['id'],)).fetchall(); c.close(); return {"memories":[dict(r) for r in rows]}

@router.post("/memories")
def create_memory(p:MemoryRequest,current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); mid=str(uuid4()); c.execute("INSERT INTO coach_memories(id,user_id,content) VALUES(?,?,?)",(mid,current_user['id'],p.content.strip())); c.commit(); c.close(); return {"id":mid,"content":p.content.strip()}

@router.delete("/memories/{mid}")
def delete_memory(mid:str,current_user=Depends(get_authenticated_user)):
    init_coach_db(); c=get_connection(); cur=c.execute("DELETE FROM coach_memories WHERE id=? AND user_id=?",(mid,current_user['id'])); c.commit(); c.close();
    if not cur.rowcount: raise HTTPException(404,"Memoria no encontrada")
    return {"ok":True}

@router.post("/chat")
def chat(p:ChatRequest,current_user=Depends(get_authenticated_user)):
    init_coach_db(); mode=p.mode if p.mode in MODES else 'coach'; c=get_connection(); uid=current_user['id']; cid=p.conversation_id
    if cid:
        conv=c.execute("SELECT id,mode FROM coach_conversations WHERE id=? AND user_id=?",(cid,uid)).fetchone()
        if not conv: c.close(); raise HTTPException(404,"Conversación no encontrada")
    else:
        cid=str(uuid4()); c.execute("INSERT INTO coach_conversations(id,user_id,title,mode) VALUES(?,?,?,?)",(cid,uid,p.message[:60],mode))
    previous=c.execute("SELECT role,content FROM coach_messages WHERE conversation_id=? ORDER BY id DESC LIMIT 24",(cid,)).fetchall(); previous=list(reversed(previous))
    messages=[{"role":"system","content":_context(c,uid)}]+[{"role":x['role'],"content":x['content']} for x in previous]+[{"role":"user","content":p.message.strip()}]
    answer=_qwen(messages,mode); now=datetime.now(timezone.utc).isoformat();
    c.execute("INSERT INTO coach_messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",(str(uuid4()),cid,'user',p.message.strip(),now)); c.execute("INSERT INTO coach_messages(id,conversation_id,role,content,created_at) VALUES(?,?,?,?,?)",(str(uuid4()),cid,'assistant',answer,now)); c.execute("UPDATE coach_conversations SET mode=?,updated_at=? WHERE id=?",(mode,now,cid)); c.commit(); c.close(); return {"conversation_id":cid,"answer":answer,"mode":mode}
