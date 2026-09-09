from fastapi import APIRouter, Depends
from app.auth import get_authenticated_user, resolve_target_user
from app.database import get_connection

router = APIRouter()


@router.get("/api/workouts")
def list_workouts(
    user_id: str | None = None,
    status: str | None = None,
    current_user=Depends(get_authenticated_user),
):
    """
    Lista los entrenamientos del usuario autenticado.

    Este endpoint existe específicamente para que Dashboard e Historial
    consuman el mismo contrato que utiliza el resto de la aplicación.
    """
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    try:
        params = [target_user_id]

        query = """
            SELECT
                wl.id,
                wl.user_id,
                wl.routine_id,
                wl.date,
                wl.duration_minutes,
                wl.notes,
                wl.status,
                r.name AS routine_name
            FROM workout_logs wl
            LEFT JOIN routines r
                ON r.id = wl.routine_id
            WHERE wl.user_id = ?
        """

        if status is not None:
            query += " AND wl.status = ?"
            params.append(status)

        query += " ORDER BY wl.date DESC"

        workout_rows = conn.execute(query, params).fetchall()

        result = []

        for workout_row in workout_rows:
            workout = dict(workout_row)

            set_rows = conn.execute(
                """
                SELECT
                    ws.id,
                    ws.workout_log_id,
                    ws.exercise_id,
                    ws.set_number,
                    ws.weight_kg,
                    ws.reps,
                    ws.rir,
                    ws.is_warmup,
                    ws.notes,
                    e.name AS exercise_name
                FROM workout_sets ws
                LEFT JOIN exercises e
                    ON e.id = ws.exercise_id
                WHERE ws.workout_log_id = ?
                ORDER BY ws.exercise_id, ws.set_number, ws.id
                """,
                (workout["id"],),
            ).fetchall()

            workout["sets"] = [dict(row) for row in set_rows]
            result.append(workout)

        return result

    finally:
        conn.close()
