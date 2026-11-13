"""Fase 8: copias automáticas de la BD (API de backup, integridad, gzip, rotación)."""
import gzip
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.backup import compress_gzip, integrity_ok, list_backups, rotate, run, sqlite_backup


def _make_db(path: Path, label: str = "hola") -> Path:
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE ping (msg TEXT)")
    conn.execute("INSERT INTO ping VALUES (?)", (label,))
    conn.commit()
    conn.close()
    return path


def test_copia_integridad_y_gzip(tmp_path):
    src = _make_db(tmp_path / "entrenamiento.db", "fase8")
    dest_dir = tmp_path / "auto"
    report = run(src, dest_dir, now=datetime(2026, 11, 13, 4, 0))
    assert report["ok"]
    backup = Path(report["backup"])
    assert backup.name == "entrenamiento-20261113-0400.db.gz"
    assert backup.exists()
    assert not (dest_dir / "entrenamiento-20261113-0400.db").exists()
    assert report["integrity"] == "ok"

    # El gzip se puede abrir y contiene la fila.
    raw = tmp_path / "restored.db"
    with gzip.open(backup, "rb") as fin, raw.open("wb") as fout:
        fout.write(fin.read())
    conn = sqlite3.connect(raw)
    assert conn.execute("SELECT msg FROM ping").fetchone()[0] == "fase8"
    conn.close()


def test_integrity_check_detecta_ok(tmp_path):
    src = _make_db(tmp_path / "ok.db")
    ok, msg = integrity_ok(src)
    assert ok and msg == "ok"


def test_rotate_conserva_14_diarias_y_8_semanales(tmp_path):
    dest = tmp_path / "auto"
    dest.mkdir()
    start = datetime(2026, 8, 1, 4, 0)
    # 80 días de copias diarias (más que 14+8 semanas).
    for i in range(80):
        when = start + timedelta(days=i)
        (dest / f"entrenamiento-{when.strftime('%Y%m%d-%H%M')}.db.gz").write_bytes(b"x")
    removed = rotate(dest)
    kept = list_backups(dest)
    assert len(kept) < 80
    assert removed
    # Al menos 14 diarias.
    days = {when.date() for when, _ in kept}
    assert len(days) >= 14
    # Y al menos alguna semana antigua conservada más allá de 14 días.
    newest = kept[0][0]
    older_than_14 = [when for when, _ in kept if (newest.date() - when.date()).days > 14]
    assert older_than_14, "debería conservar copias semanales de más de 14 días"
    weeks = {when.isocalendar()[:2] for when, _ in kept}
    assert len(weeks) <= 14 + 8
    # Las 14 más recientes (por día) siguen ahí.
    all_days_newest_first = []
    # Reconstruimos lo que debería quedar de diarias: los 14 días más recientes.
    expected_daily = []
    seen = set()
    for i in range(79, -1, -1):
        when = start + timedelta(days=i)
        if when.date() not in seen:
            seen.add(when.date())
            expected_daily.append(when.date())
        if len(expected_daily) == 14:
            break
    kept_days = {when.date() for when, _ in kept}
    assert set(expected_daily) <= kept_days


def test_rotate_no_borra_si_hay_pocas(tmp_path):
    dest = tmp_path / "auto"
    dest.mkdir()
    for i in range(5):
        when = datetime(2026, 11, 1, 4, 0) + timedelta(days=i)
        (dest / f"entrenamiento-{when.strftime('%Y%m%d-%H%M')}.db.gz").write_bytes(b"x")
    assert rotate(dest) == []
    assert len(list_backups(dest)) == 5


def test_sqlite_backup_no_modifica_el_origen(tmp_path):
    src = _make_db(tmp_path / "src.db", "orig")
    dest = tmp_path / "copy.db"
    sqlite_backup(src, dest)
    conn = sqlite3.connect(src)
    assert conn.execute("SELECT msg FROM ping").fetchone()[0] == "orig"
    conn.close()
    ok, msg = integrity_ok(dest)
    assert ok and msg == "ok"


def test_run_falla_si_no_existe_la_bd(tmp_path):
    with pytest.raises(FileNotFoundError):
        run(tmp_path / "no-existe.db", tmp_path / "auto")
