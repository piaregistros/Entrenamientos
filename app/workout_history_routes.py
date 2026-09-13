from fastapi import APIRouter, Depends
from app.auth import get_authenticated_user, resolve_target_user
from app.database import get_connection
from app.workout_expiration import workout_is_expired

router = APIRouter()


@router.get("/api/workouts/in-progress")
def get_in_progress_workout(
    current_user=Depends(get_authenticated_user),
):
    """
    Devuelve el entrenamiento en curso del usuario autenticado.

    Solo puede existir una sesión activa recuperable. Si por datos antiguos
    hubiera más de una, se devuelve la más reciente.
    """
    conn = get_connection()

    try:
        workout = conn.execute(
            """
            SELECT
                wl.id,
                wl.user_id,
                wl.routine_id,
                wl.date,
                wl.duration_minutes,
                wl.notes,
                wl.status,
                wl.current_exercise_id,
                r.name AS routine_name
            FROM workout_logs wl
            LEFT JOIN routines r
                ON r.id = wl.routine_id
            WHERE wl.user_id = ?
              AND wl.status = 'in_progress'
            ORDER BY wl.date DESC
            LIMIT 1
            """,
            (current_user["id"],),
        ).fetchone()

        if workout is None:
            return None

        # Una sesión abandonada no puede permanecer activa indefinidamente.
        # Si supera 180 minutos desde su inicio, se conserva en el historial
        # pero pasa a estado expired y deja de ser recuperable como activa.
        if workout_is_expired(workout["date"]):
            conn.execute(
                """
                UPDATE workout_logs
                SET status = 'expired'
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'in_progress'
                """,
                (workout["id"], current_user["id"]),
            )
            conn.commit()
            return None

        result = dict(workout)

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
            (result["id"],),
        ).fetchall()

        result["sets"] = [dict(row) for row in set_rows]

        return result

    finally:
        conn.close()


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

@router.delete("/api/workouts/{workout_id}")
def delete_workout(
    workout_id: str,
    current_user=Depends(get_authenticated_user),
):
    """
    Elimina un entrenamiento del usuario autenticado y todas sus series.

    La comprobación de user_id impide que un usuario pueda eliminar
    un entrenamiento perteneciente a otro usuario.
    """
    conn = get_connection()

    try:
        workout = conn.execute(
            """
            SELECT id
            FROM workout_logs
            WHERE id = ? AND user_id = ?
            """,
            (workout_id, current_user["id"]),
        ).fetchone()

        if workout is None:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail="Entrenamiento no encontrado",
            )

        conn.execute(
            """
            DELETE FROM workout_sets
            WHERE workout_log_id = ?
            """,
            (workout_id,),
        )

        conn.execute(
            """
            DELETE FROM workout_logs
            WHERE id = ? AND user_id = ?
            """,
            (workout_id, current_user["id"]),
        )

        conn.commit()

        return {
            "ok": True,
            "message": "Entrenamiento eliminado correctamente",
        }

    finally:
        conn.close()

