"""Siembra idempotente del entreno en casa (Fase 12).

Uso:
    python -m app.seed_casa           # ensayo: muestra qué haría, no escribe
    python -m app.seed_casa --apply   # aplica ejercicios, material y rutinas Casa A/B/C

No borra historial. Fase 12c: Casa A/B/C son espejo de A/B/C del gimnasio. Si ya existen y su
versión es anterior, se reescribe su lista de ejercicios (una sola vez; después se respetan tus
ediciones). --force-routines la reescribe siempre.
Las rutinas se crean para Pablo y, si existe, para Pablobot; no se crean usuarios.
"""
from __future__ import annotations

import argparse
import sys

from .casa import apply_casa_seed, ensure_casa_schema, find_target_users, upsert_casa_exercises
from .casa_catalog import CASA_EXERCISES, CASA_ROUTINES
from .database import get_connection


def _print_report(report: dict, applied: bool) -> None:
    cat = report["catalog"]
    mode = "APLICADO" if applied else "ENSAYO"
    print(f"[{mode}] Catálogo casa: {cat['inserted']} insertados, {cat['already']} ya existían "
          f"(de {len(CASA_EXERCISES)} definidos).")
    if not report["users"]:
        print("No se encontró a Pablo ni a Pablobot: no se crean rutinas ni material.")
        print("Los ejercicios del catálogo sí quedan disponibles para cualquier usuario.")
        return
    for u in report["users"]:
        created = ", ".join(u["routines"]["created"]) or "—"
        updated = ", ".join(u["routines"].get("updated", [])) or "—"
        already = ", ".join(u["routines"]["already"]) or "—"
        print(f"  Usuario {u['name']} ({u['user_id']}): material={u['equipment']}; "
              f"rutinas nuevas: {created}; "
              f"actualizadas: {updated}; sin cambios: {already}")
    print("Rutinas definidas: " + ", ".join(CASA_ROUTINES))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Siembra del entreno en casa (Fase 12).")
    parser.add_argument("--apply", action="store_true", help="Escribe en la base de datos (si no, solo ensaya).")
    parser.add_argument("--force-routines", action="store_true",
                        help="Reescribe Casa A/B/C aunque ya estén en la versión actual (pisa tus ediciones).")
    args = parser.parse_args(argv)

    conn = get_connection()
    try:
        ensure_casa_schema(conn)
        if not args.apply:
            users = find_target_users(conn)
            existing_names = {r["name"] for r in conn.execute("SELECT name FROM exercises")}
            would_insert = sum(1 for e in CASA_EXERCISES if e["name"] not in existing_names
                               and e["name"].casefold() not in {n.casefold() for n in existing_names})
            print(f"[ENSAYO] Ejercicios de casa nuevos (aprox. por nombre exacto): {would_insert}.")
            print("Usuarios destino: " + (", ".join("{0} ({1})".format(u["name"], u["id"]) for u in users) or "ninguno"))
            for u in users:
                have = [r["name"] for r in conn.execute(
                    "SELECT name FROM routines WHERE user_id = ? AND name IN ('Casa A','Casa B','Casa C')",
                    (u["id"],),
                )]
                missing = [n for n in CASA_ROUTINES if n not in have]
                vers = {r["routine_name"]: r["version"] for r in conn.execute(
                    "SELECT routine_name, version FROM casa_routine_versions WHERE user_id = ?", (u["id"],))}
                stale = [n for n in have if vers.get(n, 0) < CASA_ROUTINES_VERSION]
                print(f"  {u['name']}: ya tiene {have or 'ninguna'}; se crearían {missing or 'ninguna'}; "
                      f"se actualizarían {stale or 'ninguna'}.")
            print("Nada se ha escrito. Pasa --apply para aplicar.")
            return 0
        report = apply_casa_seed(conn, force=args.force_routines)
        # Fichas, vídeos y parejas de sustitución (también se aplican al arrancar).
        try:
            from .exercise_sheets import ensure_exercise_sheets
            ensure_exercise_sheets(conn)
        except Exception:
            print("Aviso: no se pudieron aplicar las fichas/vídeos (se reintentan al arrancar).", file=sys.stderr)
        try:
            from .substitutions import ensure_substitutions
            ensure_substitutions(conn)
        except Exception:
            print("Aviso: no se pudieron ampliar las sustituciones (se reintentan al arrancar).", file=sys.stderr)
        _print_report(report, applied=True)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
