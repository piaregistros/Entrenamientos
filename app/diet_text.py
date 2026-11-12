"""Tildes en textos de dieta (solo presentación; los IDs y claves no se tocan)."""
from __future__ import annotations
import re

_WORDS = {
    "atun": "atún", "calabacin": "calabacín", "brocoli": "brócoli", "platano": "plátano",
    "salmon": "salmón", "sarten": "sartén", "arandanos": "arándanos", "rapidas": "rápidas",
    "rapido": "rápido", "datiles": "dátiles", "judias": "judías", "maiz": "maíz",
    "anade": "añade", "sofrie": "sofríe", "frio": "frío", "poche": "poché",
    "requeson": "requesón", "cuscus": "cuscús", "proteina": "proteína", "limon": "limón",
    "liquido": "líquido", "deficit": "déficit", "recomposicion": "recomposición",
    "musculo": "músculo", "superavit": "superávit", "cafe": "café", "azucar": "azúcar",
}
_RE = re.compile(r"\b(" + "|".join(sorted(_WORDS, key=len, reverse=True)) + r")\b", re.IGNORECASE)


def _sub(m: re.Match) -> str:
    word = m.group(0)
    out = _WORDS[word.lower()]
    if word.isupper() and len(word) > 1:
        return out.upper()
    if word[0].isupper():
        return out[0].upper() + out[1:]
    return out


def accentuate(text):
    """Devuelve el texto con tildes en las palabras conocidas. Idempotente."""
    if not isinstance(text, str):
        return text
    return _RE.sub(_sub, text)


def accentuate_meal(meal: dict) -> dict:
    """Corrige name/ingredients/steps de una comida guardada en un plan semanal."""
    if not isinstance(meal, dict):
        return meal
    if "name" in meal:
        meal["name"] = accentuate(meal["name"])
    for key in ("ingredients", "steps"):
        if isinstance(meal.get(key), list):
            meal[key] = [accentuate(x) for x in meal[key]]
    return meal


def accentuate_week(week: dict) -> dict:
    """Los planes ya guardados se guardaron sin tildes: se corrigen al leerlos."""
    for day in (week or {}).get("days", []) or []:
        for meal in day.get("meals", []) or []:
            accentuate_meal(meal)
    return week
