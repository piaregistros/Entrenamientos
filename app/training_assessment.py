from __future__ import annotations

from dataclasses import dataclass


ASSESSMENT_VERSION = 2


ASSESSMENT_QUESTIONS = [
    {
        "id": "goal",
        "title": "¿Cuál es tu objetivo principal?",
        "options": [
            {"value": "hypertrophy", "label": "Ganar masa muscular"},
            {"value": "strength", "label": "Ganar fuerza"},
            {"value": "glutes", "label": "Priorizar glúteos y tren inferior"},
            {"value": "general", "label": "Mejorar forma física general"},
        ],
    },
    {
        "id": "experience",
        "title": "¿Cuál es tu experiencia entrenando?",
        "options": [
            {"value": "beginner", "label": "Estoy empezando"},
            {"value": "intermediate", "label": "Llevo un tiempo entrenando"},
            {"value": "advanced", "label": "Tengo bastante experiencia"},
        ],
    },
    {
        "id": "days",
        "title": "¿Cuántos días por semana puedes entrenar?",
        "options": [
            {"value": "2", "label": "2 días"},
            {"value": "3", "label": "3 días"},
            {"value": "4", "label": "4 días"},
            {"value": "5", "label": "5 días o más"},
        ],
    },
    {
        "id": "duration",
        "title": "¿Cuánto tiempo tienes por sesión?",
        "options": [
            {"value": "30", "label": "30 minutos"},
            {"value": "45", "label": "45 minutos"},
            {"value": "60", "label": "60 minutos"},
            {"value": "75", "label": "75 minutos o más"},
        ],
    },
    {
        "id": "priority",
        "title": "¿Qué zona quieres priorizar?",
        "options": [
            {"value": "balanced", "label": "Todo el cuerpo"},
            {"value": "glutes", "label": "Glúteos"},
            {"value": "lower", "label": "Piernas"},
            {"value": "upper", "label": "Tren superior"},
        ],
    },
    {
        "id": "style",
        "title": "¿Qué tipo de entrenamiento prefieres?",
        "options": [
            {"value": "full_body", "label": "Cuerpo completo"},
            {"value": "split", "label": "Rutinas divididas por grupos"},
            {
                "value": "mixed",
                "label": "Me da igual / que lo decida el sistema",
            },
        ],
    },
]


@dataclass(frozen=True)
class TrainingProfile:
    goal: str
    experience: str
    days_per_week: int
    duration: str
    priority: str
    style: str


VALID_GOALS = {
    "hypertrophy",
    "strength",
    "glutes",
    "general",
}

VALID_EXPERIENCE = {
    "beginner",
    "intermediate",
    "advanced",
}

VALID_DURATIONS = {
    "30",
    "45",
    "60",
    "75",
}

VALID_PRIORITIES = {
    "balanced",
    "glutes",
    "lower",
    "upper",
}

VALID_STYLES = {
    "full_body",
    "split",
    "mixed",
}


def build_training_profile(answers: dict[str, str]) -> TrainingProfile:
    required = {
        "goal",
        "experience",
        "days",
        "duration",
        "priority",
        "style",
    }

    missing = required - set(answers)

    if missing:
        raise ValueError(
            "Faltan respuestas: " + ", ".join(sorted(missing))
        )

    if answers["goal"] not in VALID_GOALS:
        raise ValueError("Objetivo no válido")

    if answers["experience"] not in VALID_EXPERIENCE:
        raise ValueError("Experiencia no válida")

    try:
        days = int(answers["days"])
    except (TypeError, ValueError):
        raise ValueError("Número de días no válido")

    if days not in {2, 3, 4, 5}:
        raise ValueError("Número de días no válido")

    if answers["duration"] not in VALID_DURATIONS:
        raise ValueError("Duración no válida")

    if answers["priority"] not in VALID_PRIORITIES:
        raise ValueError("Prioridad no válida")

    if answers["style"] not in VALID_STYLES:
        raise ValueError("Estilo no válido")

    return TrainingProfile(
        goal=answers["goal"],
        experience=answers["experience"],
        days_per_week=days,
        duration=answers["duration"],
        priority=answers["priority"],
        style=answers["style"],
    )


def select_program(profile: TrainingProfile) -> str:
    days = min(profile.days_per_week, 4)

    if profile.experience == "beginner":
        if days <= 2:
            return "beginner_2_full_body"

        if days == 3:
            return "beginner_3_full_body"

    if profile.goal == "glutes" or profile.priority == "glutes":
        if days >= 4:
            return "glutes_4"

        return "glutes_3"

    if profile.goal == "strength":
        if days >= 4:
            return "strength_4"

        return "strength_3"

    if days >= 4 and profile.style == "split":
        return "upper_lower_4"

    if profile.goal == "hypertrophy":
        return "hypertrophy_3"

    if days >= 4:
        return "upper_lower_4"

    return "hypertrophy_3"


def explain_selection(profile: TrainingProfile, program_id: str) -> str:
    explanations = {
        "beginner_2_full_body":
            "Cuerpo completo 2 días para comenzar con volumen moderado.",
        "beginner_3_full_body":
            "Cuerpo completo 3 días para desarrollar una base sólida.",
        "glutes_3":
            "3 días con prioridad específica en glúteos y tren inferior.",
        "glutes_4":
            "4 días con mayor frecuencia y prioridad de glúteos.",
        "hypertrophy_3":
            "3 días orientados a hipertrofia con volumen moderado.",
        "upper_lower_4":
            "4 días divididos en tren superior e inferior.",
        "strength_3":
            "3 días orientados principalmente a fuerza.",
        "strength_4":
            "4 días orientados principalmente a fuerza.",
    }

    return explanations.get(
        program_id,
        "Programa seleccionado según el perfil de entrenamiento.",
    )
