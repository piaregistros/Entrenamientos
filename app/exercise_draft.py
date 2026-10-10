"""Borrador de ejercicio a partir de una búsqueda online (Wikipedia)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

UA = "Entrenamientos/1.0 (ficha ejercicio; contacto local)"


def _get(url: str, timeout: int = 8) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", "replace")


def _wiki(name: str) -> tuple[str, str]:
    q = urllib.parse.quote(name)
    for host in ("es.wikipedia.org", "en.wikipedia.org"):
        try:
            search = json.loads(_get(
                f"https://{host}/w/api.php?action=opensearch&search={q}&limit=1&namespace=0&format=json"
            ))
            if len(search) < 4 or not search[1]:
                continue
            title = search[1][0]
            summary = json.loads(_get(
                f"https://{host}/api/rest_v1/page/summary/{urllib.parse.quote(title)}"
            ))
            extract = (summary.get("extract") or "").strip()
            page = summary.get("content_urls", {}).get("desktop", {}).get("page") or search[3][0]
            if extract:
                return extract, page
        except Exception:
            continue
    return "", ""


def _guess(name: str) -> dict:
    n = name.lower()
    if any(k in n for k in ("plancha", "crunch", "pallof", "abdomen")):
        return {"target_muscle": "Core", "category": "core", "equipment": "Peso corporal"}
    if any(k in n for k in ("prensa", "sentadilla", "zancada", "hack", "búlgara", "bulgara", "gemelo", "step")):
        return {"target_muscle": "Cuádriceps y glúteos", "category": "pierna", "equipment": "Máquina"}
    if any(k in n for k in ("peso muerto", "femoral", "hip thrust", "gluteo", "glúteo", "patada")):
        return {"target_muscle": "Isquiosurales y glúteos", "category": "pierna", "equipment": "Máquina"}
    if any(k in n for k in ("jalón", "jalon", "remo", "pullover", "estirar hacia")):
        return {"target_muscle": "Dorsal", "category": "tirón", "equipment": "Polea"}
    if any(k in n for k in ("press", "banca", "apertura", "cruce")):
        return {"target_muscle": "Pectoral", "category": "empuje", "equipment": "Máquina"}
    if any(k in n for k in ("lateral", "hombro", "militar", "pájaro", "pajaro", "face pull")):
        return {"target_muscle": "Deltoides", "category": "hombro", "equipment": "Máquina"}
    if any(k in n for k in ("curl", "bíceps", "biceps")):
        return {"target_muscle": "Bíceps", "category": "brazos", "equipment": "Máquina"}
    if any(k in n for k in ("tríceps", "triceps", "francés", "frances")):
        return {"target_muscle": "Tríceps", "category": "brazos", "equipment": "Polea"}
    return {"target_muscle": "General", "category": "otro", "equipment": "Máquina"}


def draft_exercise(name: str) -> dict:
    name = " ".join(name.split())
    extract, page = _wiki(name)
    guess = _guess(name)
    if extract:
        instructions = extract[:500]
        source = page or "Wikipedia"
    else:
        instructions = f"{name}: movimiento controlado, rango cómodo y sin dolor. No se encontró una ficha online; revisa músculo y equipo antes de guardar."
        source = ""
    steps = [
        f"Prepara la posición de {name} con el cuerpo estable.",
        "Haz el recorrido lento, sin impulso.",
        "Para un segundo en la posición de trabajo.",
        "Vuelve controlado. Si aparece dolor, acorta el rango.",
    ]
    cues = [
        "Respiración continua, no bloquees el aire.",
        "El músculo que quieres trabajar inicia el movimiento.",
    ]
    mistakes = [
        "Usar impulso del tronco para mover más peso.",
        "Recorrido tan largo que se pierde la posición.",
    ]
    return {
        "name": name,
        "target_muscle": guess["target_muscle"],
        "category": guess["category"],
        "equipment": guess["equipment"],
        "instructions": instructions,
        "safety_notes": "Carga que permita controlar la bajada. Para si hay dolor articular.",
        "contraindications": "No forzar con dolor agudo. Ante molestia, reduce rango o cambia de ejercicio.",
        "steps": steps,
        "technical_cues": cues,
        "common_mistakes": mistakes,
        "source": source,
        "weight_increment_kg": 2.5,
    }
