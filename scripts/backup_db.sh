#!/bin/bash
# Copia diaria de /opt/entrenamiento/data/entrenamiento.db (Fase 8).
# Prefiere el Python del venv del servicio para usar la API de backup de SQLite.
set -euo pipefail
ROOT="${ENTRENAMIENTO_ROOT:-/opt/entrenamiento}"
DB="${ENTRENAMIENTO_DB:-$ROOT/data/entrenamiento.db}"
DIR="${ENTRENAMIENTO_BACKUP_DIR:-/root/backups/auto}"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="${PYTHON:-python3}"
fi
cd "$ROOT"
exec "$PY" -m app.backup --db "$DB" --dir "$DIR" "$@"
