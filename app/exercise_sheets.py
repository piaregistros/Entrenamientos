"""Fichas de ejercicio y medios (vídeos) — Fase 5.

* ``ensure_exercise_sheets(conn)``: se llama UNA vez en el arranque. Crea las
  columnas/tabla que falten, rellena las fichas del catálogo (por nombre
  normalizado, nunca por id, nunca borra ni inserta ejercicios) y siembra
  ``exercise_media``. Es idempotente.
* ``attach_sheet_fields(conn, items)``: añade a los dicts de ejercicio los campos
  que consume el frontend (steps, technical_cues, common_mistakes, video_url,
  músculos, equipo, media), ya parseados.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import unicodedata
import uuid

from .exercise_sheets_data import SHEET_VERSION, SHEETS
from .exercise_videos_data import VERIFIED_AT, VIDEOS

logger = logging.getLogger(__name__)

TEXT_COLUMNS = (
    "movement_pattern", "secondary_muscles", "exercise_type", "difficulty", "laterality",
    "steps", "technical_cues", "common_mistakes", "video_url",
)
JSON_FIELDS = ("steps", "technical_cues", "common_mistakes")
# Columnas opcionales que, si existen en la tabla, se exponen en la API.
OPTIONAL_API_COLUMNS = (
    "movement_pattern", "secondary_muscles", "exercise_type", "difficulty", "laterality",
    "steps", "technical_cues", "common_mistakes", "video_url", "measure_type",
)

YOUTUBE_WATCH = "https://www.youtube.com/watch?v="


def normalize_name(value: str | None) -> str:
    """Minúsculas, sin tildes y con espacios colapsados."""
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_exercise_sheet_schema(conn: sqlite3.Connection) -> None:
    cols = _columns(conn, "exercises")
    for col in TEXT_COLUMNS:
        if col not in cols:
            conn.execute(f"ALTER TABLE exercises ADD COLUMN {col} TEXT")
    if "sheet_version" not in cols:
        conn.execute("ALTER TABLE exercises ADD COLUMN sheet_version INTEGER NOT NULL DEFAULT 0")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS exercise_media (
            id TEXT PRIMARY KEY,
            exercise_id TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'video' CHECK (type IN ('video', 'image')),
            url TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'youtube',
            title TEXT,
            channel TEXT,
            verified_at TEXT,
            is_primary INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (exercise_id) REFERENCES exercises(id) ON DELETE CASCADE,
            UNIQUE (exercise_id, url)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_exercise_media_exercise "
        "ON exercise_media(exercise_id, is_primary DESC)"
    )
    # Como mucho un medio principal por ejercicio y tipo.
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_exercise_media_primary "
        "ON exercise_media(exercise_id, type) WHERE is_primary = 1"
    )


def _rows_by_normalized_name(conn: sqlite3.Connection) -> dict[str, list[sqlite3.Row]]:
    index: dict[str, list] = {}
    for row in conn.execute("SELECT * FROM exercises"):
        index.setdefault(normalize_name(row["name"]), []).append(row)
    return index


def apply_exercise_sheets(conn: sqlite3.Connection) -> dict:
    """Rellena/corrige las fichas del catálogo. Solo actúa si sheet_version < SHEET_VERSION."""
    from .seed_exercises_v2 import EXERCISES as CATALOG

    conn.row_factory = sqlite3.Row
    index = _rows_by_normalized_name(conn)
    catalog_meta = {normalize_name(e["name"]): e for e in CATALOG}
    report = {"updated": 0, "already_current": 0, "missing": []}

    for name, sheet in SHEETS.items():
        rows = index.get(normalize_name(name), [])
        if not rows:
            report["missing"].append(name)
            continue
        meta = catalog_meta.get(normalize_name(name), {})
        for row in rows:
            # Metadatos del catálogo: solo se rellenan si están vacíos.
            for col in ("movement_pattern", "secondary_muscles", "exercise_type", "difficulty", "laterality"):
                if meta.get(col) and not (row[col] or "").strip():
                    conn.execute(f"UPDATE exercises SET {col} = ? WHERE id = ?", (meta[col], row["id"]))
            if (row["sheet_version"] or 0) >= SHEET_VERSION:
                report["already_current"] += 1
                continue
            conn.execute(
                """
                UPDATE exercises
                SET instructions = ?, safety_notes = ?, contraindications = ?,
                    steps = ?, technical_cues = ?, common_mistakes = ?, sheet_version = ?
                WHERE id = ?
                """,
                (
                    sheet["instructions"], sheet["safety_notes"], sheet["contraindications"],
                    json.dumps(sheet["steps"], ensure_ascii=False),
                    json.dumps(sheet["technical_cues"], ensure_ascii=False),
                    json.dumps(sheet["common_mistakes"], ensure_ascii=False),
                    SHEET_VERSION, row["id"],
                ),
            )
            report["updated"] += 1
    return report


def apply_exercise_media(conn: sqlite3.Connection) -> dict:
    """Siembra exercise_media con los vídeos verificados (INSERT OR IGNORE, un principal por ejercicio)."""
    conn.row_factory = sqlite3.Row
    index = _rows_by_normalized_name(conn)
    report = {"inserted": 0, "missing": []}
    for name, video in VIDEOS.items():
        rows = index.get(normalize_name(name), [])
        if not rows:
            report["missing"].append(name)
            continue
        url = YOUTUBE_WATCH + video["video_id"]
        for row in rows:
            has_primary = conn.execute(
                "SELECT 1 FROM exercise_media WHERE exercise_id = ? AND type = 'video' AND is_primary = 1",
                (row["id"],),
            ).fetchone()
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO exercise_media
                    (id, exercise_id, type, url, source, title, channel, verified_at, is_primary)
                VALUES (?, ?, 'video', ?, 'youtube', ?, ?, ?, ?)
                """,
                (str(uuid.uuid4()), row["id"], url, video["title"], video["channel"],
                 VERIFIED_AT, 0 if has_primary else 1),
            )
            report["inserted"] += cur.rowcount
            if not (row["video_url"] or "").strip():
                conn.execute("UPDATE exercises SET video_url = ? WHERE id = ?", (url, row["id"]))
    return report


def ensure_exercise_sheets(conn: sqlite3.Connection) -> dict:
    """Punto de entrada para el arranque: esquema + fichas + vídeos, en una transacción."""
    previous_factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    try:
        ensure_exercise_sheet_schema(conn)
        sheets = apply_exercise_sheets(conn)
        media = apply_exercise_media(conn)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.row_factory = previous_factory
    if sheets["updated"] or media["inserted"]:
        logger.warning(
            "FICHAS OK: %d fichas actualizadas, %d vídeos añadidos", sheets["updated"], media["inserted"]
        )
    return {"sheets": sheets, "media": media}


# ----------------------------------------------------------------- lectura
def parse_json_list(value) -> list[str]:
    """Convierte el contenido de una columna JSON/TEXT en lista de str (nunca falla)."""
    if value is None:
        return []
    data = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            data = json.loads(text)
        except (ValueError, TypeError):
            return [text]
    if isinstance(data, list):
        return [str(x).strip() for x in data if str(x).strip()]
    if isinstance(data, str):
        return [data.strip()] if data.strip() else []
    return []


def split_muscles(value) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in str(value).split(",") if p.strip()]


def load_media(conn: sqlite3.Connection, exercise_ids: list[str]) -> dict[str, list[dict]]:
    if not exercise_ids:
        return {}
    exists = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='exercise_media'"
    ).fetchone()
    if not exists:
        return {}
    media: dict[str, list[dict]] = {}
    for start in range(0, len(exercise_ids), 500):
        chunk = exercise_ids[start:start + 500]
        marks = ",".join("?" * len(chunk))
        for row in conn.execute(
            f"""SELECT id, exercise_id, type, url, source, title, channel, verified_at, is_primary
                FROM exercise_media WHERE exercise_id IN ({marks})
                ORDER BY is_primary DESC, created_at, id""",
            chunk,
        ):
            media.setdefault(row[1], []).append({
                "id": row[0], "type": row[2], "url": row[3], "source": row[4],
                "title": row[5], "channel": row[6], "verified_at": row[7],
                "is_primary": bool(row[8]),
            })
    return media


def attach_sheet_fields(conn: sqlite3.Connection, items: list[dict]) -> list[dict]:
    """Añade a cada dict (con clave ``id``) steps/technical_cues/common_mistakes/video_url,
    músculos, equipo y media. No toca el SELECT original: hace una consulta aparte."""
    ids = [item["id"] for item in items if item.get("id")]
    if not ids:
        return items
    available = _columns(conn, "exercises")
    wanted = [c for c in OPTIONAL_API_COLUMNS if c in available]
    extra: dict[str, dict] = {}
    if wanted:
        select = "id, target_muscle, equipment, " + ", ".join(wanted)
        for start in range(0, len(ids), 500):
            chunk = ids[start:start + 500]
            marks = ",".join("?" * len(chunk))
            for row in conn.execute(f"SELECT {select} FROM exercises WHERE id IN ({marks})", chunk):
                extra[row[0]] = dict(zip(["id", "target_muscle", "equipment"] + wanted, row))
    media = load_media(conn, ids)
    for item in items:
        data = extra.get(item.get("id"), {})
        item["target_muscle"] = item.get("target_muscle", data.get("target_muscle"))
        item["equipment"] = item.get("equipment", data.get("equipment"))
        item["secondary_muscles"] = split_muscles(data.get("secondary_muscles"))
        for field in JSON_FIELDS:
            item[field] = parse_json_list(data.get(field))
        for field in ("movement_pattern", "exercise_type", "difficulty", "laterality", "measure_type"):
            if field in data:
                item[field] = data[field]
        item_media = media.get(item["id"], [])
        item["media"] = item_media
        primary = next((m for m in item_media if m["type"] == "video" and m["is_primary"]), None)
        if primary is None:
            primary = next((m for m in item_media if m["type"] == "video"), None)
        item["video_url"] = primary["url"] if primary else ((data.get("video_url") or "").strip() or None)
    return items
