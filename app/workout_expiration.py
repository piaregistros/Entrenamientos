from datetime import datetime, timezone

WORKOUT_MAX_MINUTES = 180


def parse_workout_datetime(value: str) -> datetime:
    """
    Convierte la fecha almacenada del entrenamiento a datetime aware UTC.
    Las fechas antiguas sin zona horaria se interpretan como UTC por
    compatibilidad con datos históricos.
    """
    parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def workout_is_expired(
    started_at: str,
    now: datetime | None = None,
) -> bool:
    """
    Devuelve True cuando el entrenamiento lleva más de 180 minutos
    desde su fecha de inicio.
    """
    start = parse_workout_datetime(started_at)

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    elapsed_seconds = (now - start).total_seconds()

    return elapsed_seconds > WORKOUT_MAX_MINUTES * 60
