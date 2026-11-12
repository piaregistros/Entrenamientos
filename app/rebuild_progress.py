"""Reconstruye exercise_progress desde el historial real (limpia estados obsoletos).

Uso (desde /opt/entrenamiento, con el venv del servicio):

    .venv/bin/python -m app.rebuild_progress            # simulación: solo muestra cambios
    .venv/bin/python -m app.rebuild_progress --apply    # aplica los cambios
    .venv/bin/python -m app.rebuild_progress --apply --user <user_id>

HAZ ANTES UNA COPIA DE LA BD (ver instrucciones de despliegue).
"""
from __future__ import annotations

import argparse
import json

from .database import get_connection
from .progress_routes import rebuild_all_progress


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="aplicar (por defecto solo simula)")
    parser.add_argument("--user", help="limitar a un user_id")
    args = parser.parse_args()

    conn = get_connection()
    try:
        report = rebuild_all_progress(conn, args.user)
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        if args.apply:
            conn.commit()
            print("Cambios aplicados.")
        else:
            conn.rollback()
            print("Simulación: no se ha guardado nada. Usa --apply para aplicar.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
