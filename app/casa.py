"""Fase 12: entreno en casa (esquema, material, ubicación de rutinas y ranking).

Todo es aditivo e idempotente. No borra rutinas, ejercicios ni preferencias.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import unicodedata
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .auth import get_authenticated_user, resolve_target_user
from .casa_catalog import (
    CASA_CURATED_PAIRS,
    CASA_EXERCISES,
    CASA_ROUTINES,
    CASA_ROUTINES_VERSION,
    DEFAULT_DUMBBELL_INCREMENT_KG,
    DEFAULT_KETTLEBELL_WEIGHTS,
    HOME_EQUIPMENT_ITEMS,
    HOME_EQUIPMENT_KEYS,
    TARGET_USER_IDS,
    TARGET_USER_NAMES,
)
from .database import get_connection

logger = logging.getLogger(__name__)
router = APIRouter()

LOCATIONS = ("gimnasio", "casa")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm(value) -> str:
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return " ".join(text.lower().split())


def _columns(conn, table: str) -> set[str]:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def _tables(conn) -> set[str]:
    return {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


# ------------------------------------------------------------------ esquema
def ensure_casa_schema(conn: sqlite3.Connection) -> None:
    """Columnas y tablas de la fase 12. Idempotente, nunca destructivo."""
    cols = _columns(conn, "routines")
    if "location" not in cols:
        conn.execute("ALTER TABLE routines ADD COLUMN location TEXT NOT NULL DEFAULT 'gimnasio'")
    if "session_label" not in cols:
        conn.execute("ALTER TABLE routines ADD COLUMN session_label TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_home_equipment (
            user_id TEXT NOT NULL,
            equipment_key TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT,
            PRIMARY KEY (user_id, equipment_key),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_home_settings (
            user_id TEXT PRIMARY KEY,
            kettlebell_weights TEXT,
            dumbbell_increment_kg REAL,
            updated_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS casa_routine_versions (
            user_id TEXT NOT NULL,
            routine_name TEXT NOT NULL,
            version INTEGER NOT NULL,
            applied_at TEXT,
            PRIMARY KEY (user_id, routine_name)
        )
        """
    )
    conn.commit()


# ------------------------------------------------------------------ material
# Tokens de equipo que, por sí solos, no se pueden hacer en casa (máquinas/poleas
# del gimnasio) salvo que el ejercicio declare también una alternativa de casa.
_GYM_ONLY_KEYS = ("maquina", "polea")

# Correspondencia equipo/nombre → claves de material de casa.
_KEY_RULES: list[tuple[tuple[str, ...], str]] = [
    (("landmine",), "landmine"),
    (("trap bar", "trap-bar", "hex bar", "bear bar"), "trap_bar"),
    (("kettlebell", "pesa rusa"), "kettlebells"),
    (("trx", "suspension", "suspensión"), "trx"),
    (("goma", "banda elastica", "banda elástica", "bandas"), "gomas"),
    (("cajon", "box jump", "pliometr"), "cajon"),
    (("cuerda de combate", "battle rope", "cuerda de batalla"), "cuerda"),
    (("remo ergometro", "remo ergo", "ergometro", "concept2"), "remo"),
    (("eliptica", "elíptica"), "eliptica"),
    (("dominada", "chin-up", "chin up", "colgado", "colgad"), "dominadas"),
    (("fondos en", "paralela", "dips"), "paralelas"),
    (("mancuerna",), "mancuernas"),
]


def required_home_keys(name, equipment) -> set[str]:
    """Claves de material de casa que hacen falta para este ejercicio."""
    text = norm(f"{name} {equipment}")
    keys: set[str] = set()
    for needles, key in _KEY_RULES:
        if any(n in text for n in needles):
            keys.add(key)
    # Barra (no trap bar / landmine): barra + discos; sentadilla libre también jaula.
    if "barra" in text and "trap" not in text and "landmine" not in text and "bear bar" not in text:
        keys.add("barra")
        keys.add("discos")
    if "sentadilla libre" in text or "jaula" in text or "press banca plano" in text:
        if "sentadilla libre" in text or "jaula" in text:
            keys.add("jaula")
        if "press banca" in text or "press inclinado" in text or "hip thrust" in text:
            keys.add("banco")
    if "press banca" in text or "press inclinado" in text or "hip thrust" in text or "banco" in text:
        keys.add("banco")
    if "landmine" in text:
        keys.add("landmine")
        keys.add("discos")
    if "trap" in text:
        keys.add("trap_bar")
        keys.add("discos")
    return keys


def is_gym_machine_only(name, equipment) -> bool:
    """True si el ejercicio es de máquina o polea y no tiene variante de casa en el nombre/equipo."""
    text = norm(f"{name} {equipment}")
    homeish = any(
        token in text
        for token in (
            "mancuerna", "barra", "peso corporal", "kettlebell", "pesa rusa",
            "landmine", "trap", "trx", "goma", "banda", "cajon", "cuerda",
            "remo erg", "calistenia", "dominada", "fondos", "plancha",
        )
    )
    if homeish:
        return False
    # «Barra o máquina» / «Máquina o banco» se pueden hacer en casa.
    if " o " in text and ("barra" in text or "banco" in text or "mancuerna" in text or "peso corporal" in text):
        return False
    return any(k in text for k in _GYM_ONLY_KEYS)


def is_home_doable(name, equipment, available: set[str]) -> bool:
    """Si se puede hacer en casa con el material marcado como disponible."""
    if is_gym_machine_only(name, equipment):
        return False
    needed = required_home_keys(name, equipment)
    if not needed:
        # Peso corporal puro (plancha, etc.) o equipo no clasificado: se admite
        # si no es una máquina.
        return True
    return needed <= available


def default_available_keys() -> set[str]:
    return {i["key"] for i in HOME_EQUIPMENT_ITEMS if i["default"]}


def load_home_available(conn, user_id) -> set[str]:
    """Claves disponibles. Si el usuario aún no ha guardado nada, se asume el material de Pablo."""
    if "user_home_equipment" not in _tables(conn):
        return default_available_keys()
    rows = conn.execute(
        "SELECT equipment_key, available FROM user_home_equipment WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    if not rows:
        return default_available_keys()
    return {r["equipment_key"] for r in rows if int(r["available"] or 0) == 1}


def load_home_settings(conn, user_id) -> dict:
    settings = {
        "kettlebell_weights": list(DEFAULT_KETTLEBELL_WEIGHTS),
        "dumbbell_increment_kg": DEFAULT_DUMBBELL_INCREMENT_KG,
    }
    if "user_home_settings" not in _tables(conn):
        return settings
    row = conn.execute(
        "SELECT kettlebell_weights, dumbbell_increment_kg FROM user_home_settings WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not row:
        return settings
    if row["kettlebell_weights"]:
        try:
            weights = [float(x) for x in json.loads(row["kettlebell_weights"])]
            weights = sorted({w for w in weights if w > 0})
            if weights:
                settings["kettlebell_weights"] = weights
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if row["dumbbell_increment_kg"] is not None:
        try:
            inc = float(row["dumbbell_increment_kg"])
            if inc > 0:
                settings["dumbbell_increment_kg"] = inc
        except (TypeError, ValueError):
            pass
    return settings


def routine_location(conn, routine_id) -> str:
    if not routine_id or "location" not in _columns(conn, "routines"):
        return "gimnasio"
    row = conn.execute("SELECT location FROM routines WHERE id = ?", (routine_id,)).fetchone()
    loc = (row["location"] if row else None) or "gimnasio"
    return loc if loc in LOCATIONS else "gimnasio"


# ------------------------------------------------------------------ ejercicios
def upsert_casa_exercises(conn: sqlite3.Connection) -> dict:
    """Inserta los ejercicios de casa que falten (por nombre normalizado). No pisa los existentes."""
    report = {"inserted": 0, "already": 0}
    existing = {norm(r["name"]): r for r in conn.execute("SELECT id, name FROM exercises")}
    cols = _columns(conn, "exercises")
    for ex in CASA_EXERCISES:
        row = existing.get(norm(ex["name"]))
        if row:
            report["already"] += 1
            # Rellena measure_type / increment solo si están vacíos.
            if "measure_type" in cols and ex.get("measure_type"):
                conn.execute(
                    "UPDATE exercises SET measure_type = COALESCE(NULLIF(measure_type, ''), ?) WHERE id = ? AND (measure_type IS NULL OR measure_type = '')",
                    (ex["measure_type"], row["id"]),
                )
            continue
        eid = ex.get("id") or str(uuid.uuid4())
        conn.execute(
            """
            INSERT INTO exercises (
                id, name, target_muscle, category, equipment, movement_pattern,
                secondary_muscles, exercise_type, difficulty, laterality, is_active
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                eid, ex["name"], ex["target_muscle"], ex["category"], ex["equipment"],
                ex["movement_pattern"], ex["secondary_muscles"], ex["exercise_type"],
                ex["difficulty"], ex["laterality"],
            ),
        )
        if "measure_type" in cols and ex.get("measure_type"):
            conn.execute("UPDATE exercises SET measure_type = ? WHERE id = ?", (ex["measure_type"], eid))
        if "weight_increment_kg" in cols and ex.get("weight_increment_kg") is not None:
            conn.execute(
                "UPDATE exercises SET weight_increment_kg = ? WHERE id = ?",
                (ex["weight_increment_kg"], eid),
            )
        existing[norm(ex["name"])] = {"id": eid, "name": ex["name"]}
        report["inserted"] += 1
    conn.commit()
    return report


# ------------------------------------------------------------------ rutinas y material por usuario
def find_target_users(conn) -> list[dict]:
    """Pablo (id conocido o nombre) y Pablobot, si existen. No crea usuarios."""
    found: dict[str, dict] = {}
    for uid in TARGET_USER_IDS:
        row = conn.execute("SELECT id, name FROM users WHERE id = ?", (uid,)).fetchone()
        if row:
            found[row["id"]] = dict(row)
    placeholders = ",".join("?" * len(TARGET_USER_NAMES))
    names = tuple(TARGET_USER_NAMES)
    for row in conn.execute(
        f"SELECT id, name FROM users WHERE lower(name) IN ({placeholders})",
        names,
    ):
        found[row["id"]] = dict(row)
    # Por si el login está en el email.
    for row in conn.execute(
        "SELECT id, name, email FROM users WHERE lower(COALESCE(email, '')) LIKE '%pablobot%'"
    ):
        found[row["id"]] = {"id": row["id"], "name": row["name"]}
    return list(found.values())


def seed_home_equipment_for_user(conn, user_id) -> str:
    """Prellena el material de casa si el usuario no tiene ninguna fila. No pisa lo ya guardado."""
    existing = conn.execute(
        "SELECT 1 FROM user_home_equipment WHERE user_id = ? LIMIT 1", (user_id,)
    ).fetchone()
    if existing:
        return "kept"
    ts = now_iso()
    for item in HOME_EQUIPMENT_ITEMS:
        conn.execute(
            """
            INSERT OR IGNORE INTO user_home_equipment (user_id, equipment_key, available, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, item["key"], 1 if item["default"] else 0, ts),
        )
    has_settings = conn.execute(
        "SELECT 1 FROM user_home_settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not has_settings:
        conn.execute(
            """
            INSERT INTO user_home_settings (user_id, kettlebell_weights, dumbbell_increment_kg, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                json.dumps(DEFAULT_KETTLEBELL_WEIGHTS),
                DEFAULT_DUMBBELL_INCREMENT_KG,
                ts,
            ),
        )
    return "seeded"


def _write_casa_exercises(conn, rid, spec, ids) -> None:
    for (exercise_name, order, sets, rmin, rmax, rir, rest, optional) in spec["exercises"]:
        eid = ids.get(norm(exercise_name))
        if eid is None:
            raise ValueError(f"No se encontró el ejercicio: {exercise_name}")
        conn.execute(
            """
            INSERT INTO routine_exercises (
                id, routine_id, exercise_id, "order", target_sets,
                target_rep_min, target_rep_max, target_rir, rest_seconds, is_optional
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), rid, eid, order, sets, rmin, rmax, rir, rest, optional),
        )


def seed_casa_routines_for_user(conn, user_id, force: bool = False) -> dict:
    """Crea o ACTUALIZA Casa A/B/C (espejo de A/B/C del gimnasio). Idempotente.

    - Si la rutina no existe, se crea.
    - Si existe y su versión guardada es anterior a CASA_ROUTINES_VERSION (o ``force``), se reescribe su
      lista de ejercicios (routine_exercises) y su etiqueta. Después se anota la versión: una segunda
      ejecución no vuelve a tocarla, así que lo que edites luego en «Gestionar rutinas» se respeta.
    - Nunca toca workout_logs, workout_sets ni ningún historial (las series cuelgan del ejercicio, no
      del hueco de la rutina), ni el id de la rutina.
    """
    report = {"created": [], "updated": [], "already": []}
    ids = {norm(r["name"]): r["id"] for r in conn.execute("SELECT id, name FROM exercises")}
    for name, spec in CASA_ROUTINES.items():
        row = conn.execute(
            "SELECT id FROM routines WHERE user_id = ? AND name = ?",
            (user_id, name),
        ).fetchone()
        if not row:
            rid = str(uuid.uuid4())
            conn.execute(
                """
                INSERT INTO routines (id, user_id, name, day_order, is_active, session_label, location)
                VALUES (?, ?, ?, ?, 1, ?, 'casa')
                """,
                (rid, user_id, name, spec["day_order"], spec["session_label"]),
            )
            _write_casa_exercises(conn, rid, spec, ids)
            report["created"].append(name)
        else:
            rid = row["id"]
            conn.execute(
                "UPDATE routines SET location = 'casa' WHERE id = ? AND COALESCE(location, '') != 'casa'",
                (rid,),
            )
            seen = conn.execute(
                "SELECT version FROM casa_routine_versions WHERE user_id = ? AND routine_name = ?",
                (user_id, name),
            ).fetchone()
            if force or seen is None or int(seen["version"]) < CASA_ROUTINES_VERSION:
                # Valida antes de borrar nada: si falta un ejercicio, no se toca la rutina.
                for item in spec["exercises"]:
                    if ids.get(norm(item[0])) is None:
                        raise ValueError(f"No se encontró el ejercicio: {item[0]}")
                conn.execute("DELETE FROM routine_exercises WHERE routine_id = ?", (rid,))
                _write_casa_exercises(conn, rid, spec, ids)
                conn.execute(
                    "UPDATE routines SET session_label = ?, is_active = 1 WHERE id = ?",
                    (spec["session_label"], rid),
                )
                report["updated"].append(name)
            else:
                report["already"].append(name)
        conn.execute(
            """
            INSERT INTO casa_routine_versions (user_id, routine_name, version, applied_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id, routine_name) DO UPDATE SET
                version = excluded.version, applied_at = excluded.applied_at
            """,
            (user_id, name, CASA_ROUTINES_VERSION, now_iso()),
        )
    return report


def apply_casa_seed(conn, users=None, force: bool = False) -> dict:
    """Catálogo + rutinas + material. Idempotente."""
    ensure_casa_schema(conn)
    catalog = upsert_casa_exercises(conn)
    users = users if users is not None else find_target_users(conn)
    per_user = []
    for u in users:
        eq = seed_home_equipment_for_user(conn, u["id"])
        routines = seed_casa_routines_for_user(conn, u["id"], force=force)
        per_user.append({"user_id": u["id"], "name": u.get("name"), "equipment": eq, "routines": routines})
    conn.commit()
    return {"catalog": catalog, "users": per_user}


# ------------------------------------------------------------------ API
class HomeEquipmentIn(BaseModel):
    available: list[str] = Field(default_factory=list)
    kettlebell_weights: list[float] | None = None
    dumbbell_increment_kg: float | None = Field(default=None, gt=0, le=20)


def _payload(conn, user_id) -> dict:
    rows = conn.execute(
        "SELECT equipment_key, available FROM user_home_equipment WHERE user_id = ?",
        (user_id,),
    ).fetchall()
    saved = {r["equipment_key"]: int(r["available"] or 0) for r in rows}
    items = []
    for item in HOME_EQUIPMENT_ITEMS:
        available = bool(saved[item["key"]]) if item["key"] in saved else bool(item["default"])
        items.append({"key": item["key"], "label": item["label"], "available": available})
    settings = load_home_settings(conn, user_id)
    return {
        "items": items,
        "available": [i["key"] for i in items if i["available"]],
        "kettlebell_weights": settings["kettlebell_weights"],
        "dumbbell_increment_kg": settings["dumbbell_increment_kg"],
    }


@router.get("/api/home-equipment")
def get_home_equipment(user_id: str | None = None, current_user=Depends(get_authenticated_user)):
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()
    try:
        ensure_casa_schema(conn)
        return _payload(conn, user_id)
    finally:
        conn.close()


@router.put("/api/home-equipment")
def put_home_equipment(body: HomeEquipmentIn, user_id: str | None = None,
                       current_user=Depends(get_authenticated_user)):
    user_id = resolve_target_user(current_user, user_id)
    wanted = {norm(x) for x in body.available}
    # Aceptamos las claves canónicas (jaula, barra, …).
    unknown = wanted - set(HOME_EQUIPMENT_KEYS)
    if unknown:
        raise HTTPException(status_code=400, detail="Material desconocido: " + ", ".join(sorted(unknown)))
    weights = body.kettlebell_weights
    if weights is not None:
        try:
            weights = sorted({float(w) for w in weights if float(w) > 0})
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Los pesos de kettlebell no son válidos")
        if not weights:
            raise HTTPException(status_code=400, detail="Indica al menos un peso de kettlebell")
    conn = get_connection()
    try:
        ensure_casa_schema(conn)
        ts = now_iso()
        for key in HOME_EQUIPMENT_KEYS:
            conn.execute(
                """
                INSERT INTO user_home_equipment (user_id, equipment_key, available, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id, equipment_key) DO UPDATE SET
                    available = excluded.available, updated_at = excluded.updated_at
                """,
                (user_id, key, 1 if key in wanted else 0, ts),
            )
        settings = load_home_settings(conn, user_id)
        kb = json.dumps(weights if weights is not None else settings["kettlebell_weights"])
        inc = body.dumbbell_increment_kg if body.dumbbell_increment_kg is not None else settings["dumbbell_increment_kg"]
        conn.execute(
            """
            INSERT INTO user_home_settings (user_id, kettlebell_weights, dumbbell_increment_kg, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                kettlebell_weights = excluded.kettlebell_weights,
                dumbbell_increment_kg = excluded.dumbbell_increment_kg,
                updated_at = excluded.updated_at
            """,
            (user_id, kb, inc, ts),
        )
        conn.commit()
        return _payload(conn, user_id)
    finally:
        conn.close()
