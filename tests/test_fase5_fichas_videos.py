"""Fase 5: fichas completas, tabla exercise_media y endpoints de ejercicios."""
import json
import re
import sqlite3
import uuid

import pytest

from conftest import EXERCISES
from app import database
from app.database import get_connection
from app.exercise_sheets import (
    apply_exercise_media,
    apply_exercise_sheets,
    attach_sheet_fields,
    ensure_exercise_sheets,
    normalize_name,
    parse_json_list,
)
from app.exercise_sheets_data import SHEET_VERSION, SHEETS
from app.exercise_videos_data import VIDEOS, WITHOUT_VIDEO
from app.seed_exercises_v2 import EXERCISES as CATALOG

CATALOG_NAMES = [e["name"] for e in CATALOG]
YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
BICEPS_ID = EXERCISES["biceps"][0]  # "Curl de bíceps en máquina"


# --------------------------------------------------------------- datos estáticos
def test_hay_ficha_para_los_59_ejercicios_del_catalogo():
    assert len(CATALOG_NAMES) >= 59
    assert set(SHEETS) == set(CATALOG_NAMES)


@pytest.mark.parametrize("name", CATALOG_NAMES)
def test_ficha_completa_y_en_espanol(name):
    s = SHEETS[name]
    assert len(s["instructions"]) > 40
    assert 3 <= len(s["steps"]) <= 8
    assert len(s["technical_cues"]) >= 2
    assert len(s["common_mistakes"]) >= 2
    assert s["safety_notes"].strip() and s["contraindications"].strip()
    for field in ("steps", "technical_cues", "common_mistakes"):
        assert len(set(s[field])) == len(s[field]), f"{name}: {field} con duplicados"
        assert all(isinstance(x, str) and len(x) > 8 for x in s[field])
    # sin restos de inglés típicos ni marcadores de relleno
    blob = json.dumps(s, ensure_ascii=False).lower()
    for bad in ("lorem", "tbd", "xxx", "pendiente"):
        assert not re.search(rf"\b{bad}\b", blob), f"{name}: contiene {bad}"


def test_videos_verificados_cubren_el_catalogo_sin_urls_inventadas():
    assert set(VIDEOS) | set(WITHOUT_VIDEO) == set(CATALOG_NAMES)
    assert not (set(VIDEOS) & set(WITHOUT_VIDEO))
    ids = [v["video_id"] for v in VIDEOS.values()]
    assert all(YT_ID.match(i) for i in ids)
    assert len(set(ids)) == len(ids), "mismo vídeo asignado a dos ejercicios (¿copia y pega?)"
    for name, v in VIDEOS.items():
        assert v["title"] and v["channel"], name


def test_normalize_name_ignora_tildes_mayusculas_y_espacios():
    assert normalize_name("  Curl de BÍCEPS  en máquina ") == "curl de biceps en maquina"
    assert normalize_name(None) == ""


def test_parse_json_list_es_tolerante():
    assert parse_json_list(None) == []
    assert parse_json_list("") == []
    assert parse_json_list("[]") == []
    assert parse_json_list('["a", "b"]') == ["a", "b"]
    assert parse_json_list("texto suelto") == ["texto suelto"]
    assert parse_json_list('"solo uno"') == ["solo uno"]
    assert parse_json_list("[1, 2]") == ["1", "2"]
    assert parse_json_list('{"a": 1}') == []


# ------------------------------------------------------------------- semilla
@pytest.fixture
def raw_db(test_db):
    conn = get_connection()
    yield conn
    conn.close()


def _full_catalog_db(conn):
    present = {normalize_name(r[0]) for r in conn.execute("SELECT name FROM exercises")}
    for e in CATALOG:
        if normalize_name(e["name"]) in present:
            continue
        conn.execute(
            "INSERT OR IGNORE INTO exercises (id, name, target_muscle, category, equipment, is_active) VALUES (?,?,?,?,?,1)",
            (e.get("id") or str(uuid.uuid4()), e["name"], e["target_muscle"], e["category"], e["equipment"]),
        )
    conn.commit()


def test_catalogo_completo_queda_con_ficha_y_un_video_principal(raw_db):
    _full_catalog_db(raw_db)
    result = ensure_exercise_sheets(raw_db)
    assert result["sheets"]["missing"] == [] and result["media"]["missing"] == []
    rows = raw_db.execute("SELECT name, steps, technical_cues, common_mistakes, video_url, sheet_version FROM exercises").fetchall()
    assert len(rows) >= 59
    for r in rows:
        if r["name"] in SHEETS:
            assert json.loads(r["steps"]) and json.loads(r["technical_cues"]) and json.loads(r["common_mistakes"])
            assert r["video_url"].startswith("https://www.youtube.com/watch?v=")
            assert r["sheet_version"] == SHEET_VERSION
    per_ex = raw_db.execute(
        "SELECT exercise_id, COUNT(*) n, SUM(is_primary) p FROM exercise_media GROUP BY exercise_id"
    ).fetchall()
    assert len(per_ex) == len(CATALOG_NAMES)
    assert all(r["n"] == 1 and r["p"] == 1 for r in per_ex)


def test_seed_es_idempotente(raw_db):
    _full_catalog_db(raw_db)
    ensure_exercise_sheets(raw_db)
    snapshot = [tuple(r) for r in raw_db.execute("SELECT * FROM exercises ORDER BY id")]
    media = [tuple(r)[1:] for r in raw_db.execute("SELECT * FROM exercise_media ORDER BY exercise_id, url")]
    again = ensure_exercise_sheets(raw_db)
    assert again["sheets"]["updated"] == 0 and again["media"]["inserted"] == 0
    assert snapshot == [tuple(r) for r in raw_db.execute("SELECT * FROM exercises ORDER BY id")]
    assert media == [tuple(r)[1:] for r in raw_db.execute("SELECT * FROM exercise_media ORDER BY exercise_id, url")]


def test_corrige_fichas_antiguas_incorrectas(raw_db):
    ensure_exercise_sheets(raw_db)
    raw_db.execute(
        "UPDATE exercises SET steps='[\"paso viejo y malo\"]', instructions='viejo', sheet_version=0 WHERE id=?",
        (BICEPS_ID,),
    )
    raw_db.commit()
    ensure_exercise_sheets(raw_db)
    row = raw_db.execute("SELECT steps, instructions FROM exercises WHERE id=?", (BICEPS_ID,)).fetchone()
    assert json.loads(row["steps"]) == SHEETS["Curl de bíceps en máquina"]["steps"]
    assert row["instructions"] == SHEETS["Curl de bíceps en máquina"]["instructions"]


def test_no_pisa_ediciones_posteriores_si_la_version_esta_al_dia(raw_db):
    ensure_exercise_sheets(raw_db)
    raw_db.execute("UPDATE exercises SET instructions='editado a mano' WHERE id=?", (BICEPS_ID,))
    raw_db.commit()
    ensure_exercise_sheets(raw_db)
    assert raw_db.execute("SELECT instructions FROM exercises WHERE id=?", (BICEPS_ID,)).fetchone()[0] == "editado a mano"


def test_casa_por_nombre_normalizado_y_no_por_id(raw_db):
    ensure_exercise_sheets(raw_db)
    raw_db.execute("UPDATE exercises SET name='CURL DE BICEPS EN MAQUINA', sheet_version=0 WHERE id=?", (BICEPS_ID,))
    raw_db.commit()
    ensure_exercise_sheets(raw_db)
    row = raw_db.execute("SELECT steps FROM exercises WHERE id=?", (BICEPS_ID,)).fetchone()
    assert json.loads(row["steps"])


def test_no_borra_ni_inserta_ejercicios_y_respeta_los_personalizados(raw_db):
    custom = str(uuid.uuid4())
    raw_db.execute(
        "INSERT INTO exercises (id, name, target_muscle, category, equipment, is_active, instructions, steps, video_url) "
        "VALUES (?, 'Mi ejercicio raro', 'Core', 'core', 'Peso corporal', 1, 'mía', '[\"paso mío\"]', 'https://youtu.be/abcdefghijk')",
        (custom,),
    )
    raw_db.commit()
    before = raw_db.execute("SELECT COUNT(*) FROM exercises").fetchone()[0]
    result = ensure_exercise_sheets(raw_db)
    assert raw_db.execute("SELECT COUNT(*) FROM exercises").fetchone()[0] == before
    assert len(result["sheets"]["missing"]) == len(CATALOG_NAMES) - raw_db.execute(
        "SELECT COUNT(*) FROM exercises WHERE sheet_version >= 1"
    ).fetchone()[0]
    row = raw_db.execute("SELECT instructions, steps, video_url FROM exercises WHERE id=?", (custom,)).fetchone()
    assert tuple(row) == ("mía", '["paso mío"]', "https://youtu.be/abcdefghijk")
    assert raw_db.execute("SELECT COUNT(*) FROM exercise_media WHERE exercise_id=?", (custom,)).fetchone()[0] == 0


def test_no_sobrescribe_un_video_url_existente_pero_el_principal_manda_en_la_api(raw_db):
    raw_db.execute("UPDATE exercises SET video_url='https://youtu.be/abcdefghijk' WHERE id=?", (BICEPS_ID,))
    raw_db.commit()
    ensure_exercise_sheets(raw_db)
    assert raw_db.execute("SELECT video_url FROM exercises WHERE id=?", (BICEPS_ID,)).fetchone()[0] == "https://youtu.be/abcdefghijk"
    item = attach_sheet_fields(raw_db, [{"id": BICEPS_ID}])[0]
    assert item["video_url"].endswith(VIDEOS["Curl de bíceps en máquina"]["video_id"])


def test_solo_un_medio_principal_por_ejercicio_y_tipo(raw_db):
    ensure_exercise_sheets(raw_db)
    with pytest.raises(sqlite3.IntegrityError):
        raw_db.execute(
            "INSERT INTO exercise_media (id, exercise_id, type, url, is_primary) VALUES (?,?,?,?,1)",
            (str(uuid.uuid4()), BICEPS_ID, "video", "https://www.youtube.com/watch?v=aaaaaaaaaaa"),
        )
    raw_db.rollback()
    # un segundo medio no principal sí se admite
    raw_db.execute(
        "INSERT INTO exercise_media (id, exercise_id, type, url, is_primary) VALUES (?,?,?,?,0)",
        (str(uuid.uuid4()), BICEPS_ID, "video", "https://www.youtube.com/watch?v=aaaaaaaaaaa"),
    )
    raw_db.commit()
    item = attach_sheet_fields(raw_db, [{"id": BICEPS_ID}])[0]
    assert len(item["media"]) == 2 and item["media"][0]["is_primary"] is True


def test_media_se_borra_en_cascada_con_el_ejercicio(raw_db):
    ensure_exercise_sheets(raw_db)
    # (los ejercicios no se borran en la app; solo se comprueba que la FK está declarada)
    fks = raw_db.execute("PRAGMA foreign_key_list(exercise_media)").fetchall()
    assert any(fk["table"] == "exercises" and fk["on_delete"] == "CASCADE" for fk in fks)


def test_attach_sheet_fields_tolera_columnas_corruptas(raw_db):
    ensure_exercise_sheets(raw_db)
    raw_db.execute("UPDATE exercises SET steps='no es json', technical_cues=NULL, common_mistakes='' WHERE id=?", (BICEPS_ID,))
    raw_db.commit()
    item = attach_sheet_fields(raw_db, [{"id": BICEPS_ID}])[0]
    assert item["steps"] == ["no es json"]
    assert item["technical_cues"] == [] and item["common_mistakes"] == []


def test_ejercicio_sin_ficha_ni_video_devuelve_listas_vacias_y_null(raw_db):
    custom = str(uuid.uuid4())
    raw_db.execute("INSERT INTO exercises (id, name, is_active) VALUES (?, 'Sin nada', 1)", (custom,))
    raw_db.commit()
    ensure_exercise_sheets(raw_db)
    item = attach_sheet_fields(raw_db, [{"id": custom}])[0]
    assert item["steps"] == [] and item["technical_cues"] == [] and item["common_mistakes"] == []
    assert item["video_url"] is None and item["media"] == [] and item["secondary_muscles"] == []


def test_esquema_viejo_sin_columnas_se_migra(tmp_path, monkeypatch):
    path = tmp_path / "old.db"
    monkeypatch.setattr(database, "DB_PATH", path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE exercises (id TEXT PRIMARY KEY, name TEXT NOT NULL, target_muscle TEXT, category TEXT, "
                 "equipment TEXT, safety_notes TEXT, is_active INTEGER NOT NULL DEFAULT 1, instructions TEXT, contraindications TEXT)")
    conn.execute("INSERT INTO exercises (id, name) VALUES ('1', 'Face pull')")
    conn.commit()
    ensure_exercise_sheets(conn)
    row = conn.execute("SELECT steps, sheet_version, movement_pattern, secondary_muscles FROM exercises").fetchone()
    assert json.loads(row["steps"]) and row["sheet_version"] == SHEET_VERSION
    assert row["movement_pattern"] == "traccion_horizontal" and "romboides" in row["secondary_muscles"]
    conn.close()


# ----------------------------------------------------------------- endpoints
def test_lista_de_ejercicios_incluye_ficha_video_musculos_y_equipo(client):
    r = client.get("/api/exercises")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] == len(data["exercises"]) > 0
    by_id = {e["id"]: e for e in data["exercises"]}
    ex = by_id[BICEPS_ID]
    sheet = SHEETS["Curl de bíceps en máquina"]
    assert ex["steps"] == sheet["steps"]
    assert ex["technical_cues"] == sheet["technical_cues"]
    assert ex["common_mistakes"] == sheet["common_mistakes"]
    assert ex["video_url"] == "https://www.youtube.com/watch?v=" + VIDEOS["Curl de bíceps en máquina"]["video_id"]
    assert ex["target_muscle"] == "Bíceps" and ex["equipment"] == "Máquina"
    assert ex["secondary_muscles"] == ["braquial", "braquiorradial"]
    assert ex["media"][0]["is_primary"] is True and ex["media"][0]["type"] == "video"
    for e in data["exercises"]:
        assert isinstance(e["steps"], list) and isinstance(e["technical_cues"], list)
        assert isinstance(e["common_mistakes"], list) and isinstance(e["secondary_muscles"], list)
        assert e["video_url"] is None or e["video_url"].startswith("https://www.youtube.com/")


def test_los_filtros_de_la_lista_siguen_funcionando(client):
    r = client.get("/api/exercises", params={"equipment": "Polea"})
    assert r.status_code == 200
    assert all(e["equipment"] == "Polea" for e in r.json()["exercises"])
    assert r.json()["count"] >= 1


def test_detalle_de_ejercicio(client):
    r = client.get(f"/api/exercises/{BICEPS_ID}")
    assert r.status_code == 200, r.text
    ex = r.json()
    assert ex["id"] == BICEPS_ID and ex["name"] == "Curl de bíceps en máquina"
    assert len(ex["steps"]) >= 3 and ex["technical_cues"] and ex["common_mistakes"]
    assert ex["video_url"].startswith("https://www.youtube.com/watch?v=")
    assert ex["instructions"] == SHEETS["Curl de bíceps en máquina"]["instructions"]
    assert ex["secondary_muscles"] and ex["movement_pattern"] == "flexion_codo"


def test_detalle_404_y_requiere_login(client, test_db):
    assert client.get(f"/api/exercises/{uuid.uuid4()}").status_code == 404
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as anonimo:
        assert anonimo.get(f"/api/exercises/{BICEPS_ID}").status_code in (401, 403)
        assert anonimo.get("/api/exercises").status_code in (401, 403)


def test_las_rutas_existentes_de_ejercicios_no_se_pisan(client):
    # /api/exercises/{id}/last-performance y /substitutions siguen resolviendo a sus handlers
    r = client.get(f"/api/exercises/{BICEPS_ID}/substitutions", params={"user_id": "1effca7d-97cf-41f2-a930-9ce482972f02"})
    assert r.status_code == 200
    assert "substitutions" in r.json()


def test_arranque_es_idempotente_con_varios_clientes(test_db):
    from fastapi.testclient import TestClient
    from app.main import app
    for _ in range(2):
        with TestClient(app):
            pass
    conn = get_connection()
    try:
        n = conn.execute("SELECT COUNT(*) FROM exercise_media WHERE exercise_id=?", (BICEPS_ID,)).fetchone()[0]
        assert n == 1
    finally:
        conn.close()
