from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import date, datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user
from .database import get_connection

router = APIRouter(prefix="/api/coach", tags=["coach"])

QWEN_BASE_URL = os.getenv(
    "QWEN_BASE_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
).rstrip("/")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "") or os.getenv("DASHSCOPE_API_KEY", "")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3.8-max")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_BASE_URL = os.getenv(
    "GEMINI_BASE_URL",
    "https://generativelanguage.googleapis.com/v1beta",
).rstrip("/")
AI_PROVIDER = os.getenv("AI_PROVIDER", "qwen").strip().lower()
MAX_MESSAGE = 12000

MODES = {
    "coach": "Coach: decide qué hacer ahora según el estado real y responde primero a la pregunta.",
    "plan": "Plan: organiza sesiones en fechas concretas, progresión y distribución de A/B/C.",
    "nutrition": "Nutrición: céntrate en alimentación, hábitos, cantidades y organización; no hagas diagnóstico médico.",
    "recovery": "Recuperación: céntrate en fatiga, carga, descanso, molestias y cuándo conviene ajustar.",
}

SYSTEM = """Eres EntrenamientosCoach. Responde en español y sé concreto.

REGLAS IMPORTANTES:
1. Usa los DATOS REALES proporcionados en el contexto. No inventes pesos, repeticiones, fechas ni entrenamientos.
2. Cuando el usuario pregunte qué hizo, usa los REGISTROS REALES DE SERIES del último entrenamiento (peso x repeticiones y RIR), no los objetivos programados de la rutina.
3. No confundas "programado" con "realizado".
4. No uses reglas rígidas del tipo "24 horas = sí" o "48 horas = no". Valora volumen, RIR, solapamiento de ejercicios/músculos, rendimiento, recuperación y molestias.
5. Si el usuario pide organizar entrenamientos, da FECHAS Y DÍAS DE LA SEMANA concretos. Respeta las restricciones de disponibilidad indicadas por el usuario.
6. Una fecha futura es una PROPUESTA, no un hecho. Diferencia claramente DATOS REGISTRADOS de PROPUESTA. Si el contexto incluye un CALENDARIO CANDIDATO EXACTO, copia literalmente sus pares fecha/día; no cambies el día de la semana.
7. No repitas una rutina completa salvo que el usuario la pida.
8. Responde primero a lo que pregunta. Evita consejos genéricos que no cambien la decisión.
9. Si faltan datos importantes, dilo y evita falsa precisión.
10. Las respuestas anteriores del Coach son HISTORIAL, no datos fisiológicos ni hechos nuevos.
11. No menciones dolor torácico, síncope, dificultad respiratoria, síntomas neurológicos ni otras señales de alarma si el usuario no las ha mencionado. La advertencia sanitaria es interna, no debe aparecer como texto preventivo genérico.
12. No recomiendes sauna, hidratación, sueño u otros hábitos si el usuario no los pregunta y no cambian la decisión.
13. Para "¿qué hice en mi último entrenamiento?", usa exclusivamente "SERIES REALES DEL ÚLTIMO ENTRENAMIENTO". No describas el programa ni los objetivos de la rutina como si fueran lo realizado.
14. Para "¿puedo hacer B hoy?", "¿debería entrenar hoy?" o preguntas equivalentes, no imprimas la rutina completa salvo que se solicite. Da primero SÍ/NO/DEPENDE y justifica con el último entrenamiento real, los solapamientos y los datos de recuperación disponibles.
15. Los bloques "ESTADO DE ENTRENAMIENTO CALCULADO" y, dentro de ellos, "SOLAPAMIENTO DIRECTO CON EL ÚLTIMO ENTRENAMIENTO" y "MÚSCULOS CON SOLAPAMIENTO REGISTRADO" son hechos calculados por el backend. Tienen prioridad sobre cualquier inferencia del modelo. No los recalcules, contradigas ni sustituyas por una interpretación propia.
16. No inferir que el usuario está "suficientemente recuperado" solo porque el RIR medio sea alto, bajo o moderado. El RIR describe el esfuerzo registrado de las series; por sí solo no demuestra el estado de recuperación.
17. Nunca afirmar que un ejercicio no se realizó si aparece en "SERIES REALES DEL ÚLTIMO ENTRENAMIENTO". Si el backend marca un solapamiento directo, debes reconocerlo como tal.
18. Distingue siempre entre HECHO REGISTRADO, DATO CALCULADO y PROPUESTA. Una propuesta de calendario no es un entrenamiento realizado ni una prueba de recuperación.
19. Para decidir entre SÍ/NO/DEPENDE, usa los datos disponibles sin inventar criterios. Si los datos no permiten establecer una recuperación suficiente o una contraindicación clara, responde DEPENDE y explica brevemente qué dato falta o qué factor impide afirmarlo.
20. Para preguntas factuales simples sobre un dato concreto del entrenamiento, responde de forma breve y completa. No empieces un desglose largo si no se solicita y nunca dejes la respuesta incompleta.
"""

WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MADRID = ZoneInfo("Europe/Madrid")


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
    conn.commit()
    conn.close()


def _local_now() -> datetime:
    return datetime.now(timezone.utc).astimezone(MADRID)


def _weekday(d: date) -> str:
    return WEEKDAYS[d.weekday()]


def _fmt_date(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


def _rows_to_dict(rows):
    return [dict(r) for r in rows]


def _conversation_constraints(previous_messages, today: date, current_message: str = "") -> dict:
    """Extract only explicit availability statements from the user's own chat history."""
    text = " ".join(
        [str(x["content"]) for x in previous_messages if x["role"] == "user"]
        + ([current_message] if current_message else [])
    ).lower()
    unavailable = []
    available = []

    for idx, day_name in enumerate(WEEKDAYS):
        patterns = [
            rf"\b{re.escape(day_name)}\b[^.!?\n]{{0,100}}\bno puedo(?: entrenar)?\b",
            rf"\bno puedo(?: entrenar)?\b[^.!?\n]{{0,100}}\b{re.escape(day_name)}\b",
            rf"\b{re.escape(day_name)}\b[^.!?\n]{{0,100}}\bno entreno\b",
            rf"\bno entreno\b[^.!?\n]{{0,100}}\b{re.escape(day_name)}\b",
        ]
        if any(re.search(pat, text) for pat in patterns):
            unavailable.append(day_name)

    if re.search(r"\bhoy\b[^.!?\n]{0,80}\bpuedo entrenar\b", text):
        available.append(today.strftime("%Y-%m-%d"))
    if re.search(r"\bhoy\b[^.!?\n]{0,80}\bno puedo(?: entrenar)?\b", text):
        unavailable.append(_weekday(today))

    dates = {}
    for i, day_name in enumerate(WEEKDAYS):
        if day_name in unavailable:
            delta = (i - today.weekday()) % 7
            dates[day_name] = _fmt_date(today + timedelta(days=delta))

    return {
        "unavailable_weekdays": sorted(set(unavailable), key=lambda x: WEEKDAYS.index(x)),
        "available_today": today.strftime("%Y-%m-%d") in available,
        "unavailable_dates": dates,
    }


def _training_status(conn, user_id: str, previous_messages, current_message: str = "") -> str:
    now = _local_now()
    today = now.date()

    last = conn.execute(
        """SELECT wl.id, wl.date, wl.duration_minutes, wl.status, wl.notes,
                  r.name AS routine_name, r.day_order
           FROM workout_logs wl
           LEFT JOIN routines r ON r.id=wl.routine_id
           WHERE wl.user_id=?
           ORDER BY wl.date DESC, wl.rowid DESC LIMIT 1""",
        (user_id,),
    ).fetchone()

    blocks = [
        f"FECHA ACTUAL: {_fmt_date(today)} ({_weekday(today)})",
        f"HORA LOCAL APROXIMADA: {now.strftime('%H:%M')}",
    ]

    constraints = _conversation_constraints(previous_messages, today, current_message)
    if constraints["unavailable_weekdays"]:
        blocks.append(
            "DISPONIBILIDAD EXPLÍCITA DEL USUARIO: "
            + ", ".join(constraints["unavailable_weekdays"])
            + " NO disponible(s)."
        )
    if constraints["available_today"]:
        blocks.append("El usuario ha indicado explícitamente que HOY puede entrenar.")

    if not last:
        blocks.append("ÚLTIMO ENTRENAMIENTO: no hay registros.")
        return "\n".join(blocks)

    try:
        last_date = date.fromisoformat(str(last["date"])[:10])
        days_since = (today - last_date).days
    except ValueError:
        last_date = None
        days_since = None

    blocks.append(
        "ÚLTIMO ENTRENAMIENTO REGISTRADO: "
        f"{last['routine_name'] or 'sin rutina'} — "
        f"{last['date']} — {days_since if days_since is not None else '?'} día(s) desde entonces — "
        f"{last['duration_minutes'] or '?'} min — estado={last['status'] or '?'}."
    )
    if last["notes"]:
        blocks.append(f"Notas del último entrenamiento: {last['notes']}")

    sets = conn.execute(
        """SELECT ws.exercise_id, e.name AS exercise_name, e.target_muscle,
                  ws.set_number, ws.weight_kg, ws.reps, ws.rir,
                  ws.is_warmup, ws.notes
           FROM workout_sets ws
           LEFT JOIN exercises e ON e.id=ws.exercise_id
           WHERE ws.workout_log_id=?
           ORDER BY ws.rowid""",
        (last["id"],),
    ).fetchall()

    if sets:
        grouped = []
        working = []
        hard = []
        rir_values = []
        exercise_ids = []
        seen = set()

        for s in sets:
            exercise_ids.append(s["exercise_id"])
            if s["exercise_id"] not in seen:
                seen.add(s["exercise_id"])
                grouped.append({
                    "name": s["exercise_name"] or "Ejercicio",
                    "muscle": s["target_muscle"] or "",
                    "sets": [],
                })

            weight = "?" if s["weight_kg"] is None else f"{s['weight_kg']:g} kg"
            reps = "?" if s["reps"] is None else str(s["reps"])
            rir = "" if s["rir"] is None else f" RIR {s['rir']}"
            warm = " [calentamiento]" if s["is_warmup"] else ""
            note = f" — {s['notes']}" if s["notes"] else ""
            item = f"{weight} x {reps}{rir}{warm}{note}"
            next(g for g in grouped if g["name"] == (s["exercise_name"] or "Ejercicio"))["sets"].append(item)

            if not s["is_warmup"]:
                working.append(s)
                if s["rir"] is not None:
                    rir_values.append(float(s["rir"]))
                    if float(s["rir"]) <= 1:
                        hard.append(s)

        lines = []
        for g in grouped:
            lines.append(f"- {g['name']}: " + "; ".join(g["sets"]))
        blocks.append("SERIES REALES DEL ÚLTIMO ENTRENAMIENTO:\n" + "\n".join(lines))
        avg_rir = sum(rir_values) / len(rir_values) if rir_values else None
        blocks.append(
            "RESUMEN DE CARGA REAL: "
            f"{len(working)} series de trabajo; "
            f"{len(hard)} series con RIR <= 1; "
            f"RIR medio={avg_rir:.1f}."
            if avg_rir is not None
            else f"RESUMEN DE CARGA REAL: {len(working)} series de trabajo."
        )

        next_routine = conn.execute(
            """SELECT id, name, day_order FROM routines
               WHERE user_id=? AND is_active=1
               ORDER BY day_order LIMIT 20""",
            (user_id,),
        ).fetchall()

        if next_routine:
            routines = list(next_routine)
            after = [r for r in routines if last["day_order"] is not None and r["day_order"] > last["day_order"]]
            candidate = after[0] if after else routines[0]
            ex = conn.execute(
                """SELECT re.exercise_id, e.name, e.target_muscle, re.target_sets,
                          re.target_rep_min, re.target_rep_max, re.target_rir, re.rest_seconds
                   FROM routine_exercises re
                   JOIN exercises e ON e.id=re.exercise_id
                   WHERE re.routine_id=?
                   ORDER BY re."order" """,
                (candidate["id"],),
            ).fetchall()
            ids = {s["exercise_id"] for s in sets if not s["is_warmup"]}
            direct = [x for x in ex if x["exercise_id"] in ids]
            last_muscles = {str(s["target_muscle"]).lower() for s in sets if s["target_muscle"]}
            next_muscles = {str(x["target_muscle"]).lower() for x in ex if x["target_muscle"]}
            muscle_overlap = sorted(m for m in next_muscles if m in last_muscles)

            blocks.append(
                f"SIGUIENTE RUTINA POR ORDEN: Día {candidate['day_order']} — {candidate['name']}."
            )
            if direct:
                blocks.append(
                    "SOLAPAMIENTO DIRECTO CON EL ÚLTIMO ENTRENAMIENTO: "
                    + ", ".join(x["name"] for x in direct)
                )
            else:
                blocks.append("SOLAPAMIENTO DIRECTO CON EL ÚLTIMO ENTRENAMIENTO: ninguno.")
            if muscle_overlap:
                blocks.append("MÚSCULOS CON SOLAPAMIENTO REGISTRADO: " + ", ".join(muscle_overlap))
            else:
                blocks.append("MÚSCULOS CON SOLAPAMIENTO REGISTRADO: no detectado por los datos disponibles.")

            # Candidate dates are deterministic only from explicit availability.
            # They are proposals for the model to evaluate, never facts.
            available_dates = []
            cursor = today
            for _ in range(14):
                day_name = _weekday(cursor)
                if day_name not in constraints["unavailable_weekdays"]:
                    available_dates.append(cursor)
                cursor += timedelta(days=1)

            sequence = routines[routines.index(candidate):] + routines[:routines.index(candidate)]
            proposal = []
            last_scheduled = None
            for r in sequence[:3]:
                chosen = None
                for candidate_date in available_dates:
                    if last_scheduled is None or (candidate_date - last_scheduled).days >= 2:
                        chosen = candidate_date
                        break
                if chosen is None:
                    break
                proposal.append(
                    f"{chosen.isoformat()} | {_fmt_date(chosen)} | {_weekday(chosen)} | {r['name']}"
                )
                last_scheduled = chosen
                available_dates = [d for d in available_dates if d > chosen]

            if proposal:
                blocks.append(
                    "CALENDARIO CANDIDATO EXACTO (PROPUESTA, NO HECHO REGISTRADO). "
                    "SI LO MENCIONAS EN LA RESPUESTA, COPIA EXACTAMENTE FECHA Y DÍA DE ESTA LISTA; "
                    "NO LOS RECALCULES NI LOS CAMBIES:\n- " + "\n- ".join(proposal)
                )

    notes = conn.execute(
        """SELECT date, energy, effort, recovery, soreness, notes
           FROM progress_notes WHERE user_id=? ORDER BY date DESC LIMIT 5""",
        (user_id,),
    ).fetchall()
    if notes:
        blocks.append(
            "NOTAS RECIENTES DE PROGRESO:\n"
            + "\n".join(
                f"- {n['date']}: energía={n['energy']}, esfuerzo={n['effort']}, "
                f"recuperación={n['recovery']}, agujetas={n['soreness']}. {n['notes'] or ''}"
                for n in notes
            )
        )

    return "\n".join(blocks)


def _context(conn, user_id: str, previous_messages, current_message: str = "") -> str:
    user = conn.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()
    blocks = [f"Nombre: {user['name'] if user else 'usuario'}"]

    goals = conn.execute(
        """SELECT title,description,goal_type FROM user_goals
           WHERE user_id=? AND is_active=1 ORDER BY updated_at DESC LIMIT 8""",
        (user_id,),
    ).fetchall()
    if goals:
        blocks.append(
            "OBJETIVOS:\n"
            + "\n".join(f"- {g['title']} ({g['goal_type']}): {g['description'] or ''}" for g in goals)
        )

    metrics = conn.execute(
        """SELECT date,weight_kg,notes FROM body_metrics
           WHERE user_id=? ORDER BY date DESC LIMIT 8""",
        (user_id,),
    ).fetchall()
    if metrics:
        blocks.append(
            "PESO RECIENTE:\n"
            + "\n".join(f"- {m['date']}: {m['weight_kg']} kg {m['notes'] or ''}" for m in metrics)
        )

    routines = conn.execute(
        """SELECT id,name,day_order FROM routines
           WHERE user_id=? AND is_active=1 ORDER BY day_order LIMIT 10""",
        (user_id,),
    ).fetchall()
    if routines:
        routine_blocks = []
        for r in routines:
            ex = conn.execute(
                """SELECT e.name, e.target_muscle, re.target_sets, re.target_rep_min,
                          re.target_rep_max, re.target_rir, re.rest_seconds
                   FROM routine_exercises re
                   JOIN exercises e ON e.id=re.exercise_id
                   WHERE re.routine_id=? ORDER BY re."order" """,
                (r["id"],),
            ).fetchall()
            routine_blocks.append(
                f"- Día {r['day_order']}: {r['name']}: "
                + "; ".join(
                    f"{x['name']} {x['target_sets']}x{x['target_rep_min']}-{x['target_rep_max']} "
                    f"RIR {x['target_rir'] if x['target_rir'] is not None else '?'}"
                    for x in ex
                )
            )
        blocks.append("PROGRAMACIÓN DE RUTINAS (NO SIGNIFICA QUE SE HAYAN REALIZADO):\n" + "\n".join(routine_blocks))

    workouts = conn.execute(
        """SELECT wl.date,wl.duration_minutes,wl.status,r.name
           FROM workout_logs wl LEFT JOIN routines r ON r.id=wl.routine_id
           WHERE wl.user_id=? ORDER BY wl.date DESC,wl.rowid DESC LIMIT 10""",
        (user_id,),
    ).fetchall()
    if workouts:
        blocks.append(
            "HISTORIAL DE ENTRENAMIENTOS:\n"
            + "\n".join(
                f"- {w['date']}: {w['name'] or 'Entrenamiento'}; "
                f"{w['status'] or '?'}; {w['duration_minutes'] or '?'} min"
                for w in workouts
            )
        )

    memories = conn.execute(
        """SELECT content FROM coach_memories
           WHERE user_id=? ORDER BY updated_at DESC LIMIT 12""",
        (user_id,),
    ).fetchall()
    if memories:
        blocks.append("MEMORIAS DEL USUARIO:\n" + "\n".join(f"- {m['content']}" for m in memories))

    blocks.append("ESTADO DE ENTRENAMIENTO CALCULADO:\n" + _training_status(conn, user_id, previous_messages, current_message))
    return "\n\n".join(blocks)


def _qwen(messages, mode, context: str = ""):
    payload = {
        "model": QWEN_MODEL,
        "messages": [{"role": "system", "content": SYSTEM + "\n\n" + MODES.get(mode, MODES["coach"]) + "\n\nCONTEXTO REAL DEL USUARIO:\n" + context}] + messages,
        "temperature": 0.20,
        "max_tokens": 1200,
    }
    headers = {"Content-Type": "application/json"}
    if QWEN_API_KEY:
        headers["Authorization"] = "Bearer " + QWEN_API_KEY

    req = Request(
        QWEN_BASE_URL + "/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers=headers,
    )
    try:
        with urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
    except HTTPError as e:
        raise HTTPException(502, f"Qwen HTTP {e.code}: {e.read().decode('utf-8','replace')[:600]}")
    except URLError as e:
        raise HTTPException(502, f"No se pudo conectar con Qwen: {e.reason}")

    choices = data.get("choices") or []
    if not choices:
        raise HTTPException(502, "Qwen no devolvió una respuesta válida")
    content = (choices[0].get("message") or {}).get("content", "")
    if isinstance(content, list):
        content = "".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in content)
    return str(content).strip() or "No he recibido contenido del modelo."


def _gemini(messages, mode, context: str = ""):
    if not GEMINI_API_KEY:
        raise HTTPException(503, "Gemini API no está configurada en el servidor.")

    system_instruction = (
        SYSTEM
        + "\n\n"
        + MODES.get(mode, MODES["coach"])
        + "\n\nCONTEXTO REAL DEL USUARIO:\n"
        + context
    )

    contents = []
    for message in messages:
        role = "model" if message["role"] == "assistant" else "user"
        contents.append({
            "role": role,
            "parts": [{"text": str(message["content"])}],
        })

    payload = {
        "system_instruction": {
            "parts": [{"text": system_instruction}],
        },
        "contents": contents,
        "generationConfig": {
            "temperature": 0.20,
            "maxOutputTokens": 1200,
        },
    }

    req = Request(
        f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode())
    except HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:600]
        raise HTTPException(502, f"Gemini HTTP {e.code}: {detail}")
    except URLError as e:
        raise HTTPException(502, f"No se pudo conectar con Gemini: {e.reason}")

    candidates = data.get("candidates") or []
    if not candidates:
        raise HTTPException(502, "Gemini no devolvió una respuesta válida.")

    parts = ((candidates[0].get("content") or {}).get("parts") or [])
    content = "".join(
        str(part.get("text", ""))
        for part in parts
        if isinstance(part, dict) and part.get("text") is not None
    ).strip()
    if not content:
        raise HTTPException(502, "Gemini devolvió una respuesta vacía.")
    return content


def _generate_ai_response(messages, mode, context: str = ""):
    if AI_PROVIDER == "gemini":
        return _gemini(messages, mode, context)
    return _qwen(messages, mode, context)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE)
    conversation_id: str | None = None
    mode: str = "coach"


class ConversationRequest(BaseModel):
    title: str = Field(default="Nueva conversación", max_length=120)
    mode: str = "coach"


class MemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=500)


@router.get("/health")
def health(current_user=Depends(get_authenticated_user)):
    provider = AI_PROVIDER if AI_PROVIDER in {"qwen", "gemini"} else "qwen"
    return {
        "ok": True,
        "provider": provider,
        "qwen_configured": bool(QWEN_BASE_URL and QWEN_MODEL),
        "gemini_configured": bool(GEMINI_API_KEY and GEMINI_MODEL),
        "api_key_configured": bool(QWEN_API_KEY if provider == "qwen" else GEMINI_API_KEY),
        "model": QWEN_MODEL if provider == "qwen" else GEMINI_MODEL,
    }


@router.get("/conversations")
def conversations(current_user=Depends(get_authenticated_user)):
    init_coach_db()
    c = get_connection()
    rows = c.execute(
        """SELECT id,title,mode,created_at,updated_at FROM coach_conversations
           WHERE user_id=? ORDER BY updated_at DESC""",
        (current_user["id"],),
    ).fetchall()
    c.close()
    return {"conversations": _rows_to_dict(rows)}


@router.post("/conversations")
def create_conversation(p: ConversationRequest, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    mode = p.mode if p.mode in MODES else "coach"
    title = p.title.strip() or "Nueva conversación"
    cid = str(uuid4())
    c = get_connection()
    c.execute(
        "INSERT INTO coach_conversations(id,user_id,title,mode) VALUES(?,?,?,?)",
        (cid, current_user["id"], title, mode),
    )
    c.commit()
    c.close()
    return {"id": cid, "title": title, "mode": mode}


@router.get("/conversations/{cid}")
def conversation(cid: str, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    c = get_connection()
    row = c.execute(
        """SELECT id,title,mode,created_at,updated_at FROM coach_conversations
           WHERE id=? AND user_id=?""",
        (cid, current_user["id"]),
    ).fetchone()
    if not row:
        c.close()
        raise HTTPException(404, "Conversación no encontrada")
    msgs = c.execute(
        """SELECT id,role,content,created_at FROM coach_messages
           WHERE conversation_id=? ORDER BY rowid""",
        (cid,),
    ).fetchall()
    c.close()
    return {"conversation": dict(row), "messages": _rows_to_dict(msgs)}


@router.delete("/conversations/{cid}")
def delete_conversation(cid: str, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    c = get_connection()
    cur = c.execute(
        "DELETE FROM coach_conversations WHERE id=? AND user_id=?",
        (cid, current_user["id"]),
    )
    c.commit()
    c.close()
    if not cur.rowcount:
        raise HTTPException(404, "Conversación no encontrada")
    return {"ok": True}


@router.get("/memories")
def memories(current_user=Depends(get_authenticated_user)):
    init_coach_db()
    c = get_connection()
    rows = c.execute(
        """SELECT id,content,created_at,updated_at FROM coach_memories
           WHERE user_id=? ORDER BY updated_at DESC""",
        (current_user["id"],),
    ).fetchall()
    c.close()
    return {"memories": _rows_to_dict(rows)}


@router.post("/memories")
def create_memory(p: MemoryRequest, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    content = p.content.strip()
    c = get_connection()
    mid = str(uuid4())
    c.execute(
        "INSERT INTO coach_memories(id,user_id,content) VALUES(?,?,?)",
        (mid, current_user["id"], content),
    )
    c.commit()
    c.close()
    return {"id": mid, "content": content}


@router.delete("/memories/{mid}")
def delete_memory(mid: str, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    c = get_connection()
    cur = c.execute(
        "DELETE FROM coach_memories WHERE id=? AND user_id=?",
        (mid, current_user["id"]),
    )
    c.commit()
    c.close()
    if not cur.rowcount:
        raise HTTPException(404, "Memoria no encontrada")
    return {"ok": True}


@router.post("/chat")
def chat(p: ChatRequest, current_user=Depends(get_authenticated_user)):
    init_coach_db()
    uid = current_user["id"]
    requested_mode = p.mode if p.mode in MODES else "coach"
    c = get_connection()
    cid = p.conversation_id

    if cid:
        conv = c.execute(
            """SELECT id,mode FROM coach_conversations
               WHERE id=? AND user_id=?""",
            (cid, uid),
        ).fetchone()
        if not conv:
            c.close()
            raise HTTPException(404, "Conversación no encontrada")
        # A conversation belongs to one mode. This protects separation even if
        # an old client sends a stale conversation id after changing tabs.
        if conv["mode"] != requested_mode:
            c.close()
            raise HTTPException(409, "La conversación pertenece a otro modo del Coach.")
        mode = conv["mode"]
    else:
        cid = str(uuid4())
        mode = requested_mode
        c.execute(
            """INSERT INTO coach_conversations(id,user_id,title,mode)
               VALUES(?,?,?,?)""",
            (cid, uid, p.message.strip()[:60], mode),
        )

    previous = c.execute(
        """SELECT role,content FROM coach_messages
           WHERE conversation_id=? ORDER BY rowid DESC LIMIT 24""",
        (cid,),
    ).fetchall()
    previous = list(reversed(previous))

    context = _context(c, uid, previous, p.message.strip())
    model_messages = [
        {"role": x["role"], "content": x["content"]} for x in previous
    ]
    model_messages.append({"role": "user", "content": p.message.strip()})
    answer = _generate_ai_response(model_messages, mode, context)

    now = _local_now().isoformat()
    c.execute(
        """INSERT INTO coach_messages(id,conversation_id,role,content,created_at)
           VALUES(?,?,?,?,?)""",
        (str(uuid4()), cid, "user", p.message.strip(), now),
    )
    c.execute(
        """INSERT INTO coach_messages(id,conversation_id,role,content,created_at)
           VALUES(?,?,?,?,?)""",
        (str(uuid4()), cid, "assistant", answer, now),
    )
    c.execute(
        "UPDATE coach_conversations SET updated_at=? WHERE id=?",
        (now, cid),
    )
    c.commit()
    c.close()
    return {"conversation_id": cid, "answer": answer, "mode": mode}
