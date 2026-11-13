"""Copia automática de la base SQLite (Fase 8).

Uso (en el LXC, con el venv del servicio):

    .venv/bin/python -m app.backup
    .venv/bin/python -m app.backup --db /opt/entrenamiento/data/entrenamiento.db \
                                   --dir /root/backups/auto

Hace una copia en caliente con la API de backup de SQLite, comprueba integridad,
la comprime con gzip y rota: conserva 14 copias diarias y 8 semanales.
"""
from __future__ import annotations

import argparse
import gzip
import os
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

from .database import DB_PATH

DEFAULT_DIR = Path(os.environ.get("ENTRENAMIENTO_BACKUP_DIR", "/root/backups/auto"))
KEEP_DAILY = 14
KEEP_WEEKLY = 8
NAME_RE = re.compile(r"^entrenamiento-(\d{8})-(\d{4})\.db(?:\.gz)?$")


def _stamp(now: datetime | None = None) -> str:
    return (now or datetime.now()).strftime("%Y%m%d-%H%M")


def _parse_name(path: Path) -> datetime | None:
    m = NAME_RE.match(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M")
    except ValueError:
        return None


def sqlite_backup(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    source = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30)
    try:
        target = sqlite3.connect(dest)
        try:
            source.backup(target)
            target.commit()
        finally:
            target.close()
    finally:
        source.close()


def integrity_ok(path: Path) -> tuple[bool, str]:
    conn = sqlite3.connect(path, timeout=30)
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        msg = row[0] if row else "sin resultado"
        return msg == "ok", str(msg)
    finally:
        conn.close()


def compress_gzip(path: Path) -> Path:
    gz = path.with_suffix(path.suffix + ".gz")
    if gz.exists():
        gz.unlink()
    with path.open("rb") as fin, gzip.open(gz, "wb", compresslevel=9) as fout:
        shutil.copyfileobj(fin, fout)
    path.unlink()
    return gz


def list_backups(directory: Path) -> list[tuple[datetime, Path]]:
    items = []
    if not directory.exists():
        return items
    for path in directory.iterdir():
        if not path.is_file():
            continue
        when = _parse_name(path)
        if when:
            items.append((when, path))
    items.sort(key=lambda x: x[0], reverse=True)
    return items


def rotate(directory: Path, keep_daily: int = KEEP_DAILY, keep_weekly: int = KEEP_WEEKLY) -> list[Path]:
    """Borra copias que no entran en las 14 diarias ni en las 8 semanales.

    - Diarias: la más reciente de cada día civil, de los últimos ``keep_daily`` días
      que tengan copia (no calendario vacío).
    - Semanales: la más reciente de cada semana ISO, de las últimas ``keep_weekly``
      semanas que tengan copia. Así una copia semanal sobrevive al recorte diario.
    """
    kept = set()
    seen_days = []
    seen_weeks = []
    for when, path in list_backups(directory):
        day = when.date()
        week = when.isocalendar()[:2]  # (year, week)
        if day not in seen_days and len(seen_days) < keep_daily:
            seen_days.append(day)
            kept.add(path)
        if week not in seen_weeks and len(seen_weeks) < keep_weekly:
            seen_weeks.append(week)
            kept.add(path)
    removed = []
    for when, path in list_backups(directory):
        if path not in kept:
            path.unlink()
            removed.append(path)
    return removed


def run(db_path: Path, backup_dir: Path, now: datetime | None = None) -> dict:
    if not db_path.exists():
        raise FileNotFoundError(f"No existe la base de datos: {db_path}")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = _stamp(now)
    raw = backup_dir / f"entrenamiento-{stamp}.db"
    sqlite_backup(db_path, raw)
    ok, msg = integrity_ok(raw)
    if not ok:
        raise RuntimeError(f"integrity_check falló ({msg}) en {raw}")
    gz = compress_gzip(raw)
    removed = rotate(backup_dir)
    remaining = [p.name for _, p in list_backups(backup_dir)]
    return {
        "ok": True,
        "src": str(db_path),
        "backup": str(gz),
        "integrity": msg,
        "removed": [p.name for p in removed],
        "kept": remaining,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default=str(os.environ.get("ENTRENAMIENTO_DB", DB_PATH)),
                        help="ruta de la BD origen")
    parser.add_argument("--dir", default=str(DEFAULT_DIR), help="directorio de copias")
    args = parser.parse_args(argv)
    try:
        report = run(Path(args.db), Path(args.dir))
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"OK {report['backup']} (integrity={report['integrity']})")
    if report["removed"]:
        print("rotadas:", ", ".join(report["removed"]))
    print("conservadas:", len(report["kept"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
