"""Revalida los vídeos de exercise_media con el endpoint oEmbed de YouTube.

Uso (necesita red):  python -m app.check_media [--db RUTA]
Sale con código 1 si algún vídeo ya no responde 200 (borrado o no embebible).
"""
import argparse
import json
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

from app.database import DB_PATH


def check(url: str) -> tuple[int, str | None]:
    query = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(url, safe="") + "&format=json"
    try:
        with urllib.request.urlopen(query, timeout=20) as resp:
            return resp.status, json.loads(resp.read()).get("title")
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return -1, None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT e.name, m.url FROM exercise_media m JOIN exercises e ON e.id = m.exercise_id "
        "WHERE m.type = 'video' ORDER BY e.name"
    ).fetchall()
    bad = 0
    for name, url in rows:
        code, title = check(url)
        flag = "OK " if code == 200 else "MAL"
        bad += code != 200
        print(f"{flag} {code} {name} | {title} | {url}")
    print(f"{len(rows) - bad}/{len(rows)} vídeos responden 200")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
