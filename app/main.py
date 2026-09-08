import uuid
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .database import get_connection, init_db


app = FastAPI(
    title="Entrenamiento",
    version="0.1.0",
)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/users")
def get_users():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        ORDER BY name
        """
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.get("/api/routines")
def get_routines(user_id: str | None = None):
    conn = get_connection()

    if user_id:
        rows = conn.execute(
            """
            SELECT id, user_id, name, day_order, is_active, created_at
            FROM routines
            WHERE user_id = ?
              AND is_active = 1
            ORDER BY day_order
            """,
            (user_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, user_id, name, day_order, is_active, created_at
            FROM routines
            WHERE is_active = 1
            ORDER BY user_id, day_order
            """
        ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.get("/api/routines/{routine_id}")
def get_routine(routine_id: str):
    conn = get_connection()

    routine = conn.execute(
        """
        SELECT
            r.id,
            r.user_id,
            r.name,
            r.day_order,
            r.is_active,
            r.created_at,
            u.name AS user_name
        FROM routines r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ?
        """,
        (routine_id,),
    ).fetchone()

    if routine is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Rutina no encontrada")

    exercises = conn.execute(
        """
        SELECT
            re.id,
            re.exercise_id,
            e.name,
            e.target_muscle,
            e.category,
            e.equipment,
            e.safety_notes,
            e.instructions,
            e.contraindications,
            re."order",
            re.target_sets,
            re.target_rep_min,
            re.target_rep_max,
            re.target_rir,
            re.rest_seconds,
            re.is_optional
        FROM routine_exercises re
        JOIN exercises e ON e.id = re.exercise_id
        WHERE re.routine_id = ?
        ORDER BY re."order"
        """,
        (routine_id,),
    ).fetchall()

    conn.close()

    result = dict(routine)
    result["exercises"] = [dict(row) for row in exercises]

    return result



@app.get("/api/routines/{routine_id}/with-last-performance")
def get_routine_with_last_performance(routine_id: str, user_id: str):
    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar usuario
    # -----------------------------------------------------

    user = conn.execute("""
        SELECT id, name
        FROM users
        WHERE id = ?
    """, (user_id,)).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )

    # -----------------------------------------------------
    # Comprobar rutina
    # -----------------------------------------------------

    routine = conn.execute("""
        SELECT
            id,
            user_id,
            name,
            day_order,
            is_active,
            created_at
        FROM routines
        WHERE id = ?
          AND user_id = ?
          AND is_active = 1
    """, (routine_id, user_id)).fetchone()

    if not routine:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Rutina no encontrada"
        )

    # -----------------------------------------------------
    # Obtener ejercicios de la rutina
    # -----------------------------------------------------

    exercises = conn.execute("""
        SELECT
            re.id AS routine_exercise_id,
            re.exercise_id,
            re."order" AS exercise_order,
            re.target_sets,
            re.target_rep_min,
            re.target_rep_max,
            re.target_rir,
            re.rest_seconds,
            re.is_optional,

            e.name,
            e.target_muscle,
            e.category,
            e.equipment,
            e.safety_notes,
            e.instructions,
            e.contraindications,
            e.weight_increment_kg,
            e.progression_type,
            e.rep_progression_enabled

        FROM routine_exercises re
        JOIN exercises e
          ON e.id = re.exercise_id

        WHERE re.routine_id = ?
          AND e.is_active = 1

        ORDER BY re."order"
    """, (routine_id,)).fetchall()

    result = []

    for exercise in exercises:

        # -------------------------------------------------
        # Última realización COMPLETADA del ejercicio
        # -------------------------------------------------

        last_workout = conn.execute("""
            SELECT
                wl.id,
                wl.date,
                wl.duration_minutes,
                wl.notes
            FROM workout_sets ws
            JOIN workout_logs wl
              ON wl.id = ws.workout_log_id
            WHERE wl.user_id = ?
              AND ws.exercise_id = ?
              AND wl.status = 'completed'
              AND ws.is_warmup = 0
            ORDER BY wl.date DESC
            LIMIT 1
        """, (
            user_id,
            exercise["exercise_id"],
        )).fetchone()

        last_sets = []

        if last_workout:
            last_sets = conn.execute("""
                SELECT
                    set_number,
                    weight_kg,
                    reps,
                    rir,
                    is_warmup,
                    notes
                FROM workout_sets
                WHERE workout_log_id = ?
                  AND exercise_id = ?
                  AND is_warmup = 0
                ORDER BY set_number
            """, (
                last_workout["id"],
                exercise["exercise_id"],
            )).fetchall()

        # -------------------------------------------------
        # Sustituciones disponibles
        # -------------------------------------------------

        substitutions = conn.execute("""
            SELECT
                es.alternative_exercise_id,
                e.name,
                e.target_muscle,
                e.category,
                e.equipment,
                e.safety_notes,
                e.instructions,
                e.contraindications,
                e.weight_increment_kg,
                e.progression_type,
                e.rep_progression_enabled,

                es.priority,
                es.reason,
                es.same_muscle,
                es.same_movement_pattern

            FROM exercise_substitutions es

            JOIN exercises e
              ON e.id = es.alternative_exercise_id

            WHERE es.exercise_id = ?
              AND es.is_active = 1
              AND e.is_active = 1

            ORDER BY
                es.priority ASC,
                es.same_movement_pattern DESC,
                es.same_muscle DESC,
                e.name ASC
        """, (
            exercise["exercise_id"],
        )).fetchall()

        alternatives = []

        for substitution in substitutions:

            # ---------------------------------------------
            # Última realización del ejercicio alternativo
            # ---------------------------------------------

            alt_workout = conn.execute("""
                SELECT
                    wl.id,
                    wl.date,
                    wl.duration_minutes,
                    wl.notes
                FROM workout_sets ws
                JOIN workout_logs wl
                  ON wl.id = ws.workout_log_id
                WHERE wl.user_id = ?
                  AND ws.exercise_id = ?
                  AND wl.status = 'completed'
                  AND ws.is_warmup = 0
                ORDER BY wl.date DESC
                LIMIT 1
            """, (
                user_id,
                substitution["alternative_exercise_id"],
            )).fetchone()

            alt_sets = []

            if alt_workout:
                alt_sets = conn.execute("""
                    SELECT
                        set_number,
                        weight_kg,
                        reps,
                        rir,
                        is_warmup,
                        notes
                    FROM workout_sets
                    WHERE workout_log_id = ?
                      AND exercise_id = ?
                      AND is_warmup = 0
                    ORDER BY set_number
                """, (
                    alt_workout["id"],
                    substitution["alternative_exercise_id"],
                )).fetchall()

            alternatives.append({
                "exercise_id": substitution[
                    "alternative_exercise_id"
                ],
                "name": substitution["name"],
                "target_muscle": substitution["target_muscle"],
                "category": substitution["category"],
                "equipment": substitution["equipment"],
                "safety_notes": substitution["safety_notes"],
                "instructions": substitution["instructions"],
                "contraindications": substitution["contraindications"],

                "priority": substitution["priority"],
                "reason": substitution["reason"],
                "same_muscle": bool(
                    substitution["same_muscle"]
                ),
                "same_movement_pattern": bool(
                    substitution["same_movement_pattern"]
                ),

                # Progresión propia del ejercicio alternativo
                "progression": {
                    "weight_increment_kg": substitution[
                        "weight_increment_kg"
                    ],
                    "progression_type": substitution[
                        "progression_type"
                    ],
                    "rep_progression_enabled": bool(
                        substitution["rep_progression_enabled"]
                    ),
                },

                "last_performance": {
                    "workout_id": (
                        alt_workout["id"]
                        if alt_workout else None
                    ),
                    "date": (
                        alt_workout["date"]
                        if alt_workout else None
                    ),
                    "duration_minutes": (
                        alt_workout["duration_minutes"]
                        if alt_workout else None
                    ),
                    "notes": (
                        alt_workout["notes"]
                        if alt_workout else None
                    ),
                    "sets": [
                        dict(row)
                        for row in alt_sets
                    ],
                },
            })

        # -------------------------------------------------
        # Resultado del ejercicio principal
        # -------------------------------------------------

        result.append({
            "routine_exercise_id": exercise[
                "routine_exercise_id"
            ],
            "exercise_id": exercise["exercise_id"],
            "order": exercise["exercise_order"],

            "exercise": {
                "name": exercise["name"],
                "target_muscle": exercise["target_muscle"],
                "category": exercise["category"],
                "equipment": exercise["equipment"],
                "safety_notes": exercise["safety_notes"],
                "instructions": exercise["instructions"],
                "contraindications": exercise[
                    "contraindications"
                ],
            },

            # Objetivo de la rutina
            "target": {
                "sets": exercise["target_sets"],
                "rep_min": exercise["target_rep_min"],
                "rep_max": exercise["target_rep_max"],
                "rir": exercise["target_rir"],
                "rest_seconds": exercise["rest_seconds"],
                "is_optional": bool(
                    exercise["is_optional"]
                ),
            },

            # Progresión propia del ejercicio
            "progression": {
                "weight_increment_kg": exercise[
                    "weight_increment_kg"
                ],
                "progression_type": exercise[
                    "progression_type"
                ],
                "rep_progression_enabled": bool(
                    exercise["rep_progression_enabled"]
                ),
            },

            "last_performance": {
                "workout_id": (
                    last_workout["id"]
                    if last_workout else None
                ),
                "date": (
                    last_workout["date"]
                    if last_workout else None
                ),
                "duration_minutes": (
                    last_workout["duration_minutes"]
                    if last_workout else None
                ),
                "notes": (
                    last_workout["notes"]
                    if last_workout else None
                ),
                "sets": [
                    dict(row)
                    for row in last_sets
                ],
            },

            # Alternativas disponibles
            "substitutions": alternatives,
        })

    conn.close()

    return {
        "routine": {
            "id": routine["id"],
            "user_id": routine["user_id"],
            "name": routine["name"],
            "day_order": routine["day_order"],
            "is_active": bool(routine["is_active"]),
            "created_at": routine["created_at"],
        },
        "exercises": result,
    }


class BodyMetricCreate(BaseModel):
    user_id: str
    date: str
    weight_kg: float
    notes: str | None = None


class BodyMetricUpdate(BaseModel):
    date: str
    weight_kg: float
    notes: str | None = None


def validate_metric_date(date_value: str) -> str:
    try:
        parsed = datetime.strptime(date_value, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="La fecha debe tener formato YYYY-MM-DD",
        )


@app.post("/api/body-metrics")
def create_body_metric(metric: BodyMetricCreate):
    date_value = validate_metric_date(metric.date)

    if metric.weight_kg <= 0:
        raise HTTPException(
            status_code=400,
            detail="El peso debe ser mayor que 0",
        )

    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (metric.user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    existing = conn.execute(
        """
        SELECT id
        FROM body_metrics
        WHERE user_id = ?
          AND date = ?
        """,
        (
            metric.user_id,
            date_value,
        ),
    ).fetchone()

    if existing:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ya existe una medición para este usuario en esa fecha",
        )

    metric_id = str(uuid.uuid4())

    conn.execute(
        """
        INSERT INTO body_metrics (
            id,
            user_id,
            date,
            weight_kg,
            notes
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            metric.user_id,
            date_value,
            metric.weight_kg,
            metric.notes,
        ),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT
            id,
            user_id,
            date,
            weight_kg,
            notes
        FROM body_metrics
        WHERE id = ?
        """,
        (metric_id,),
    ).fetchone()

    conn.close()

    return dict(row)


@app.get("/api/body-metrics")
def list_body_metrics(
    user_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
):
    if date_from:
        date_from = validate_metric_date(date_from)

    if date_to:
        date_to = validate_metric_date(date_to)

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from no puede ser posterior a date_to",
        )

    conn = get_connection()

    user = conn.execute(
        """
        SELECT id
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    query = """
        SELECT
            id,
            user_id,
            date,
            weight_kg,
            notes
        FROM body_metrics
        WHERE user_id = ?
    """

    params = [user_id]

    if date_from:
        query += " AND date >= ?"
        params.append(date_from)

    if date_to:
        query += " AND date <= ?"
        params.append(date_to)

    query += " ORDER BY date DESC"

    rows = conn.execute(query, params).fetchall()

    conn.close()

    return {
        "count": len(rows),
        "metrics": [dict(row) for row in rows],
    }


@app.put("/api/body-metrics/{metric_id}")
def update_body_metric(
    metric_id: str,
    metric: BodyMetricUpdate,
    user_id: str,
):
    date_value = validate_metric_date(metric.date)

    if metric.weight_kg <= 0:
        raise HTTPException(
            status_code=400,
            detail="El peso debe ser mayor que 0",
        )

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT
            id,
            user_id,
            date
        FROM body_metrics
        WHERE id = ?
          AND user_id = ?
        """,
        (
            metric_id,
            user_id,
        ),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Medición no encontrada para este usuario",
        )

    duplicate = conn.execute(
        """
        SELECT id
        FROM body_metrics
        WHERE user_id = ?
          AND date = ?
          AND id != ?
        """,
        (
            user_id,
            date_value,
            metric_id,
        ),
    ).fetchone()

    if duplicate:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra medición para este usuario en esa fecha",
        )

    conn.execute(
        """
        UPDATE body_metrics
        SET
            date = ?,
            weight_kg = ?,
            notes = ?
        WHERE id = ?
          AND user_id = ?
        """,
        (
            date_value,
            metric.weight_kg,
            metric.notes,
            metric_id,
            user_id,
        ),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT
            id,
            user_id,
            date,
            weight_kg,
            notes
        FROM body_metrics
        WHERE id = ?
          AND user_id = ?
        """,
        (
            metric_id,
            user_id,
        ),
    ).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/body-metrics/{metric_id}")
def delete_body_metric(
    metric_id: str,
    user_id: str,
):
    conn = get_connection()

    existing = conn.execute(
        """
        SELECT
            id,
            user_id,
            date,
            weight_kg
        FROM body_metrics
        WHERE id = ?
          AND user_id = ?
        """,
        (
            metric_id,
            user_id,
        ),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Medición no encontrada para este usuario",
        )

    conn.execute(
        """
        DELETE FROM body_metrics
        WHERE id = ?
          AND user_id = ?
        """,
        (
            metric_id,
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "id": metric_id,
        "user_id": user_id,
        "deleted": True,
    }



@app.get("/api/stats/summary")
def get_stats_summary(
    user_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
):
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_from debe tener formato YYYY-MM-DD",
            )

    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_to debe tener formato YYYY-MM-DD",
            )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from no puede ser posterior a date_to",
        )

    conn = get_connection()

    user = conn.execute(
        """
        SELECT id, name
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    where = [
        "wl.user_id = ?",
        "wl.status = 'completed'",
    ]
    params = [user_id]

    if date_from:
        where.append("date(wl.date) >= date(?)")
        params.append(date_from)

    if date_to:
        where.append("date(wl.date) <= date(?)")
        params.append(date_to)

    where_sql = " AND ".join(where)

    summary = conn.execute(
        f"""
        SELECT
            COUNT(DISTINCT wl.id) AS completed_workouts,
            COALESCE(SUM(wl.duration_minutes), 0) AS total_duration_minutes,
            COUNT(ws.id) AS working_sets,
            COALESCE(SUM(
                CASE
                    WHEN LOWER(e.category) = 'core'
                         AND LOWER(e.name) = 'plancha'
                    THEN 0
                    ELSE ws.reps
                END
            ), 0) AS total_reps,
            COALESCE(SUM(
                CASE
                    WHEN LOWER(e.category) = 'core'
                         AND LOWER(e.name) = 'plancha'
                    THEN ws.reps
                    ELSE 0
                END
            ), 0) AS timed_seconds,
            COALESCE(SUM(ws.weight_kg * ws.reps), 0) AS total_volume
        FROM workout_logs wl
        LEFT JOIN workout_sets ws
            ON ws.workout_log_id = wl.id
           AND ws.is_warmup = 0
        LEFT JOIN exercises e
            ON e.id = ws.exercise_id
        WHERE {where_sql}
        """,
        params,
    ).fetchone()

    exercise_rows = conn.execute(
        f"""
        SELECT
            e.id,
            e.name,
            e.target_muscle,
            e.category,
            COUNT(ws.id) AS working_sets,
            COALESCE(SUM(
                CASE
                    WHEN LOWER(e.category) = 'core'
                         AND LOWER(e.name) = 'plancha'
                    THEN 0
                    ELSE ws.reps
                END
            ), 0) AS total_reps,
            COALESCE(SUM(
                CASE
                    WHEN LOWER(e.category) = 'core'
                         AND LOWER(e.name) = 'plancha'
                    THEN ws.reps
                    ELSE 0
                END
            ), 0) AS timed_seconds,
            COALESCE(SUM(ws.weight_kg * ws.reps), 0) AS volume_kg,
            MAX(ws.weight_kg) AS max_weight_kg,
            MAX(
                CASE
                    WHEN LOWER(e.category) = 'core'
                         AND LOWER(e.name) = 'plancha'
                    THEN 0
                    ELSE ws.reps
                END
            ) AS max_reps
        FROM workout_logs wl
        JOIN workout_sets ws
            ON ws.workout_log_id = wl.id
           AND ws.is_warmup = 0
        JOIN exercises e
            ON e.id = ws.exercise_id
        WHERE {where_sql}
        GROUP BY
            e.id,
            e.name,
            e.target_muscle,
            e.category
        ORDER BY e.name
        """,
        params,
    ).fetchall()

    exercises = []

    for row in exercise_rows:
        item = dict(row)

        # La plancha guarda los segundos en reps y no usa carga.
        if item["max_weight_kg"] and item["max_weight_kg"] > 0:
            best_set = conn.execute(
                f"""
                SELECT
                    ws.weight_kg,
                    ws.reps
                FROM workout_logs wl
                JOIN workout_sets ws
                    ON ws.workout_log_id = wl.id
                WHERE {where_sql}
                  AND ws.exercise_id = ?
                  AND ws.is_warmup = 0
                  AND ws.weight_kg > 0
                ORDER BY
                    (ws.weight_kg * (1 + ws.reps / 30.0)) DESC
                LIMIT 1
                """,
                params + [item["id"]],
            ).fetchone()

            if best_set:
                item["estimated_1rm_kg"] = round(
                    best_set["weight_kg"] *
                    (1 + best_set["reps"] / 30.0),
                    2,
                )
            else:
                item["estimated_1rm_kg"] = None
        else:
            item["estimated_1rm_kg"] = None

        exercises.append(item)

    body_where = ["user_id = ?"]
    body_params = [user_id]

    if date_from:
        body_where.append("date >= ?")
        body_params.append(date_from)

    if date_to:
        body_where.append("date <= ?")
        body_params.append(date_to)

    body_where_sql = " AND ".join(body_where)

    body_rows = conn.execute(
        f"""
        SELECT
            date,
            weight_kg,
            notes
        FROM body_metrics
        WHERE {body_where_sql}
        ORDER BY date
        """,
        body_params,
    ).fetchall()

    body_metrics = [dict(row) for row in body_rows]

    conn.close()

    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
        },
        "period": {
            "date_from": date_from,
            "date_to": date_to,
        },
        "summary": {
            "completed_workouts": summary["completed_workouts"],
            "total_duration_minutes": summary["total_duration_minutes"],
            "working_sets": summary["working_sets"],
            "total_reps": summary["total_reps"],
            "timed_seconds": summary["timed_seconds"],
            "total_volume_kg": round(summary["total_volume"], 2),
        },
        "exercises": exercises,
        "body_metrics": body_metrics,
    }



@app.get("/api/stats/prs")
def get_stats_prs(
    user_id: str,
    exercise_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
):
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_from debe tener formato YYYY-MM-DD",
            )

    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_to debe tener formato YYYY-MM-DD",
            )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from no puede ser posterior a date_to",
        )

    conn = get_connection()

    user = conn.execute(
        """
        SELECT id, name
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    where = [
        "wl.user_id = ?",
        "wl.status = 'completed'",
        "ws.is_warmup = 0",
    ]
    params = [user_id]

    if exercise_id:
        where.append("ws.exercise_id = ?")
        params.append(exercise_id)

    if date_from:
        where.append("date(wl.date) >= date(?)")
        params.append(date_from)

    if date_to:
        where.append("date(wl.date) <= date(?)")
        params.append(date_to)

    where_sql = " AND ".join(where)

    exercise_filter = ""
    exercise_params = []

    if exercise_id:
        exercise_filter = "AND e.id = ?"
        exercise_params = [exercise_id]

    exercise_rows = conn.execute(
        f"""
        SELECT
            e.id,
            e.name,
            e.target_muscle,
            e.category
        FROM exercises e
        WHERE e.is_active = 1
          {exercise_filter}
        ORDER BY e.name
        """,
        exercise_params,
    ).fetchall()

    prs = []

    for exercise in exercise_rows:
        base_params = params + [exercise["id"]]

        best_weight = conn.execute(
            f"""
            SELECT
                ws.weight_kg,
                ws.reps,
                wl.date AS workout_date,
                wl.id AS workout_id
            FROM workout_logs wl
            JOIN workout_sets ws
                ON ws.workout_log_id = wl.id
            WHERE {where_sql}
              AND ws.exercise_id = ?
              AND ws.weight_kg > 0
            ORDER BY
                ws.weight_kg DESC,
                ws.reps DESC,
                wl.date DESC
            LIMIT 1
            """,
            base_params,
        ).fetchone()

        best_reps = conn.execute(
            f"""
            SELECT
                ws.weight_kg,
                ws.reps,
                wl.date AS workout_date,
                wl.id AS workout_id
            FROM workout_logs wl
            JOIN workout_sets ws
                ON ws.workout_log_id = wl.id
            WHERE {where_sql}
              AND ws.exercise_id = ?
            ORDER BY
                ws.reps DESC,
                ws.weight_kg DESC,
                wl.date DESC
            LIMIT 1
            """,
            base_params,
        ).fetchone()

        # La plancha y otros ejercicios sin carga no tienen e1RM.
        if exercise["name"].lower() == "plancha":
            best_e1rm = None
        else:
            best_e1rm = conn.execute(
                f"""
                SELECT
                    ws.weight_kg,
                    ws.reps,
                    ROUND(
                        ws.weight_kg * (1 + ws.reps / 30.0),
                        2
                    ) AS estimated_1rm_kg,
                    wl.date AS workout_date,
                    wl.id AS workout_id
                FROM workout_logs wl
                JOIN workout_sets ws
                    ON ws.workout_log_id = wl.id
                WHERE {where_sql}
                  AND ws.exercise_id = ?
                  AND ws.weight_kg > 0
                ORDER BY
                    (ws.weight_kg * (1 + ws.reps / 30.0)) DESC,
                    wl.date DESC
                LIMIT 1
                """,
                base_params,
            ).fetchone()

        prs.append(
            {
                "exercise_id": exercise["id"],
                "exercise_name": exercise["name"],
                "target_muscle": exercise["target_muscle"],
                "category": exercise["category"],
                "best_weight": (
                    {
                        "weight_kg": best_weight["weight_kg"],
                        "reps": best_weight["reps"],
                        "date": best_weight["workout_date"],
                        "workout_id": best_weight["workout_id"],
                    }
                    if best_weight
                    else None
                ),
                "best_reps": (
                    None
                    if exercise["name"].lower() == "plancha"
                    else (
                        {
                            "reps": best_reps["reps"],
                            "weight_kg": best_reps["weight_kg"],
                            "date": best_reps["workout_date"],
                            "workout_id": best_reps["workout_id"],
                        }
                        if best_reps
                        else None
                    )
                ),
                "best_time_seconds": (
                    best_reps["reps"]
                    if exercise["name"].lower() == "plancha"
                    and best_reps
                    else None
                ),
                "best_estimated_1rm": (
                    {
                        "estimated_1rm_kg": best_e1rm["estimated_1rm_kg"],
                        "weight_kg": best_e1rm["weight_kg"],
                        "reps": best_e1rm["reps"],
                        "date": best_e1rm["workout_date"],
                        "workout_id": best_e1rm["workout_id"],
                    }
                    if best_e1rm
                    else None
                ),
            }
        )

    # Solo devolvemos ejercicios que tengan al menos un registro.
    prs = [
        item
        for item in prs
        if item["best_weight"] is not None
        or item["best_reps"] is not None
        or item["best_estimated_1rm"] is not None
    ]

    conn.close()

    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
        },
        "period": {
            "date_from": date_from,
            "date_to": date_to,
        },
        "count": len(prs),
        "prs": prs,
    }



@app.get("/api/stats/exercise/{exercise_id}")
def get_exercise_evolution(
    exercise_id: str,
    user_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
):
    if date_from:
        try:
            datetime.strptime(date_from, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_from debe tener formato YYYY-MM-DD",
            )

    if date_to:
        try:
            datetime.strptime(date_to, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_to debe tener formato YYYY-MM-DD",
            )

    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=400,
            detail="date_from no puede ser posterior a date_to",
        )

    conn = get_connection()

    user = conn.execute(
        """
        SELECT id, name
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    exercise = conn.execute(
        """
        SELECT
            id,
            name,
            target_muscle,
            category,
            equipment,
            weight_increment_kg,
            progression_type,
            rep_progression_enabled
        FROM exercises
        WHERE id = ?
        """,
        (exercise_id,),
    ).fetchone()

    if not exercise:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Ejercicio no encontrado",
        )

    where = [
        "wl.user_id = ?",
        "wl.status = 'completed'",
        "ws.exercise_id = ?",
        "ws.is_warmup = 0",
    ]
    params = [user_id, exercise_id]

    if date_from:
        where.append("date(wl.date) >= date(?)")
        params.append(date_from)

    if date_to:
        where.append("date(wl.date) <= date(?)")
        params.append(date_to)

    where_sql = " AND ".join(where)

    workout_rows = conn.execute(
        f"""
        SELECT DISTINCT
            wl.id,
            wl.date,
            wl.duration_minutes,
            wl.notes
        FROM workout_logs wl
        JOIN workout_sets ws
            ON ws.workout_log_id = wl.id
        WHERE {where_sql}
        ORDER BY wl.date
        """,
        params,
    ).fetchall()

    evolution = []

    for workout in workout_rows:
        sets = conn.execute(
            """
            SELECT
                id,
                set_number,
                weight_kg,
                reps,
                rir,
                notes
            FROM workout_sets
            WHERE workout_log_id = ?
              AND exercise_id = ?
              AND is_warmup = 0
            ORDER BY set_number
            """,
            (
                workout["id"],
                exercise_id,
            ),
        ).fetchall()

        if not sets:
            continue

        total_reps = sum(row["reps"] for row in sets)
        volume_kg = sum(
            row["weight_kg"] * row["reps"]
            for row in sets
        )

        max_weight = max(row["weight_kg"] for row in sets)

        # Los RIR nulos no participan en la media.
        rir_values = [
            row["rir"]
            for row in sets
            if row["rir"] is not None
        ]

        average_rir = (
            round(sum(rir_values) / len(rir_values), 2)
            if rir_values
            else None
        )

        # La plancha es un ejercicio por tiempo.
        if exercise["name"].lower() == "plancha":
            best_time_seconds = max(row["reps"] for row in sets)
            best_1rm = None
        else:
            best_time_seconds = None

            best_1rm = max(
                (
                    row["weight_kg"] * (1 + row["reps"] / 30.0)
                    for row in sets
                    if row["weight_kg"] > 0
                ),
                default=None,
            )

            if best_1rm is not None:
                best_1rm = round(best_1rm, 2)

        evolution.append(
            {
                "workout_id": workout["id"],
                "date": workout["date"],
                "duration_minutes": workout["duration_minutes"],
                "workout_notes": workout["notes"],
                "working_sets": len(sets),
                "total_reps": (
                    0
                    if exercise["name"].lower() == "plancha"
                    else total_reps
                ),
                "timed_seconds": (
                    best_time_seconds
                    if exercise["name"].lower() == "plancha"
                    else 0
                ),
                "volume_kg": round(volume_kg, 2),
                "max_weight_kg": max_weight,
                "average_rir": average_rir,
                "estimated_1rm_kg": best_1rm,
                "sets": [dict(row) for row in sets],
            }
        )

    conn.close()

    return {
        "user": {
            "id": user["id"],
            "name": user["name"],
        },
        "exercise": dict(exercise),
        "period": {
            "date_from": date_from,
            "date_to": date_to,
        },
        "count": len(evolution),
        "evolution": evolution,
    }


@app.get("/api/exercises")
def list_exercises(
    target_muscle: str | None = None,
    category: str | None = None,
    equipment: str | None = None,
    include_inactive: bool = False,
):
    conn = get_connection()

    query = """
        SELECT
            id,
            name,
            target_muscle,
            category,
            equipment,
            safety_notes,
            is_active,
            created_at,
            instructions,
            contraindications,
            weight_increment_kg,
            progression_type,
            rep_progression_enabled
        FROM exercises
        WHERE 1 = 1
    """

    params = []

    if not include_inactive:
        query += " AND is_active = 1"

    if target_muscle:
        query += " AND target_muscle = ?"
        params.append(target_muscle)

    if category:
        query += " AND category = ?"
        params.append(category)

    if equipment:
        query += " AND equipment = ?"
        params.append(equipment)

    query += " ORDER BY name COLLATE NOCASE"

    rows = conn.execute(query, params).fetchall()

    conn.close()

    return {
        "count": len(rows),
        "exercises": [dict(row) for row in rows],
    }

@app.get("/api/exercises/{exercise_id}/last-performance")
def get_last_performance(exercise_id: str, user_id: str):
    conn = get_connection()

    exercise = conn.execute(
        """
        SELECT id, name
        FROM exercises
        WHERE id = ?
        """,
        (exercise_id,),
    ).fetchone()

    if exercise is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Ejercicio no encontrado",
        )

    workout = conn.execute(
        """
        SELECT
            wl.id,
            wl.date,
            wl.duration_minutes,
            wl.notes
        FROM workout_logs wl
        JOIN workout_sets ws
            ON ws.workout_log_id = wl.id
        WHERE wl.user_id = ?
          AND wl.status = 'completed'
          AND ws.exercise_id = ?
          AND ws.is_warmup = 0
        ORDER BY wl.date DESC
        LIMIT 1
        """,
        (user_id, exercise_id),
    ).fetchone()

    if workout is None:
        conn.close()

        return {
            "exercise": dict(exercise),
            "workout": None,
            "sets": [],
        }

    sets = conn.execute(
        """
        SELECT
            set_number,
            weight_kg,
            reps,
            rir,
            is_warmup,
            notes
        FROM workout_sets
        WHERE workout_log_id = ?
          AND exercise_id = ?
          AND is_warmup = 0
        ORDER BY set_number
        """,
        (workout["id"], exercise_id),
    ).fetchall()

    conn.close()

    return {
        "exercise": dict(exercise),
        "workout": dict(workout),
        "sets": [dict(row) for row in sets],
    }


from datetime import datetime


class WorkoutCreate(BaseModel):
    user_id: str
    routine_id: str | None = None
    notes: str | None = None


class WorkoutSetCreate(BaseModel):
    exercise_id: str
    set_number: int
    weight_kg: float
    reps: int
    rir: int | None = None
    is_warmup: bool = False
    notes: str | None = None


class WorkoutUpdate(BaseModel):
    status: str
    duration_minutes: int | None = None
    notes: str | None = None


@app.post("/api/workouts")
def create_workout(workout: WorkoutCreate):
    conn = get_connection()

    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (workout.user_id,),
    ).fetchone()

    if user is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    if workout.routine_id:
        routine = conn.execute(
            """
            SELECT id
            FROM routines
            WHERE id = ?
              AND user_id = ?
              AND is_active = 1
            """,
            (workout.routine_id, workout.user_id),
        ).fetchone()

        if routine is None:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail="Rutina no encontrada para este usuario",
            )

    workout_id = str(uuid.uuid4())
    now = datetime.now().isoformat(timespec="seconds")

    conn.execute(
        """
        INSERT INTO workout_logs (
            id,
            user_id,
            routine_id,
            date,
            notes,
            status
        )
        VALUES (?, ?, ?, ?, ?, 'in_progress')
        """,
        (
            workout_id,
            workout.user_id,
            workout.routine_id,
            now,
            workout.notes,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "id": workout_id,
        "user_id": workout.user_id,
        "routine_id": workout.routine_id,
        "date": now,
        "status": "in_progress",
    }



class WorkoutExerciseSubstitutionCreate(BaseModel):
    original_exercise_id: str
    substitute_exercise_id: str
    reason: str | None = None


@app.post("/api/workouts/{workout_id}/substitute-exercise")
def substitute_workout_exercise(
    workout_id: str,
    data: WorkoutExerciseSubstitutionCreate,
    user_id: str,
):
    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar sesión
    # -----------------------------------------------------

    workout = conn.execute("""
        SELECT
            id,
            user_id,
            routine_id,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
    """, (workout_id, user_id)).fetchone()

    if not workout:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Entrenamiento no encontrado"
        )

    if workout["status"] != "in_progress":
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Solo se puede sustituir un ejercicio en una sesión en curso"
        )

    if not workout["routine_id"]:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Este entrenamiento no está asociado a una rutina"
        )

    # -----------------------------------------------------
    # Comprobar ejercicio original
    # -----------------------------------------------------

    original = conn.execute("""
        SELECT
            re.id,
            re.exercise_id,
            e.name,
            re."order" AS exercise_order,
            re.target_sets,
            re.target_rep_min,
            re.target_rep_max,
            re.target_rir,
            re.rest_seconds,
            re.is_optional
        FROM routine_exercises re
        JOIN exercises e
          ON e.id = re.exercise_id
        WHERE re.routine_id = ?
          AND re.exercise_id = ?
          AND e.is_active = 1
    """, (
        workout["routine_id"],
        data.original_exercise_id,
    )).fetchone()

    if not original:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="El ejercicio original no pertenece a esta rutina"
        )

    # -----------------------------------------------------
    # Comprobar ejercicio alternativo
    # -----------------------------------------------------

    substitute = conn.execute("""
        SELECT
            id,
            name,
            target_muscle,
            category,
            equipment,
            safety_notes,
            instructions,
            contraindications,
            weight_increment_kg,
            progression_type,
            rep_progression_enabled
        FROM exercises
        WHERE id = ?
          AND is_active = 1
    """, (data.substitute_exercise_id,)).fetchone()

    if not substitute:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Ejercicio alternativo no encontrado"
        )

    # No permitimos sustituirse a sí mismo
    if data.original_exercise_id == data.substitute_exercise_id:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="El ejercicio alternativo debe ser diferente"
        )

    # -----------------------------------------------------
    # Comprobar que existe una sustitución configurada
    # -----------------------------------------------------

    substitution = conn.execute("""
        SELECT
            priority,
            reason,
            same_muscle,
            same_movement_pattern
        FROM exercise_substitutions
        WHERE exercise_id = ?
          AND alternative_exercise_id = ?
          AND is_active = 1
    """, (
        data.original_exercise_id,
        data.substitute_exercise_id,
    )).fetchone()

    if not substitution:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="El ejercicio alternativo no está configurado como sustitución válida"
        )

    # -----------------------------------------------------
    # Comprobar si ya existe una sustitución para ese
    # ejercicio en esta sesión
    # -----------------------------------------------------

    existing = conn.execute("""
        SELECT id
        FROM workout_exercise_substitutions
        WHERE workout_log_id = ?
          AND original_exercise_id = ?
    """, (
        workout_id,
        data.original_exercise_id,
    )).fetchone()

    if existing:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Este ejercicio ya ha sido sustituido en esta sesión"
        )

    # -----------------------------------------------------
    # Registrar la sustitución
    # -----------------------------------------------------

    substitution_id = str(uuid.uuid4())

    reason = data.reason or substitution["reason"]

    conn.execute("""
        INSERT INTO workout_exercise_substitutions (
            id,
            workout_log_id,
            original_exercise_id,
            substitute_exercise_id,
            reason
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        substitution_id,
        workout_id,
        data.original_exercise_id,
        data.substitute_exercise_id,
        reason,
    ))

    conn.commit()

    # -----------------------------------------------------
    # Devolver la configuración del ejercicio alternativo
    # usando las mismas exigencias de la rutina
    # -----------------------------------------------------

    result = {
        "substitution_id": substitution_id,

        "original_exercise": {
            "id": original["exercise_id"],
            "name": original["name"],
        },

        "substitute_exercise": {
            "id": substitute["id"],
            "name": substitute["name"],
            "target_muscle": substitute["target_muscle"],
            "category": substitute["category"],
            "equipment": substitute["equipment"],
            "safety_notes": substitute["safety_notes"],
            "instructions": substitute["instructions"],
            "contraindications": substitute["contraindications"],
        },

        # La estructura de trabajo procede de la rutina original
        "target": {
            "sets": original["target_sets"],
            "rep_min": original["target_rep_min"],
            "rep_max": original["target_rep_max"],
            "rir": original["target_rir"],
            "rest_seconds": original["rest_seconds"],
            "is_optional": bool(original["is_optional"]),
        },

        # La progresión procede del ejercicio que realmente se hará
        "progression": {
            "weight_increment_kg": substitute["weight_increment_kg"],
            "progression_type": substitute["progression_type"],
            "rep_progression_enabled": bool(
                substitute["rep_progression_enabled"]
            ),
        },

        "reason": reason,
        "priority": substitution["priority"],
        "same_muscle": bool(substitution["same_muscle"]),
        "same_movement_pattern": bool(
            substitution["same_movement_pattern"]
        ),
    }

    conn.close()

    return result

@app.post("/api/workouts/{workout_id}/sets")
def add_workout_set(
    workout_id: str,
    workout_set: WorkoutSetCreate,
    user_id: str,
):
    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar entrenamiento
    # -----------------------------------------------------

    workout = conn.execute("""
        SELECT
            id,
            user_id,
            routine_id,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
    """, (
        workout_id,
        user_id,
    )).fetchone()

    if not workout:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Entrenamiento no encontrado"
        )

    if workout["status"] != "in_progress":
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="El entrenamiento no está en curso"
        )

    # -----------------------------------------------------
    # Comprobar ejercicio
    # -----------------------------------------------------

    exercise = conn.execute("""
        SELECT
            id,
            name,
            target_muscle,
            category,
            equipment,
            safety_notes,
            instructions,
            contraindications
        FROM exercises
        WHERE id = ?
          AND is_active = 1
    """, (
        workout_set.exercise_id,
    )).fetchone()

    if not exercise:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Ejercicio no encontrado"
        )

    # -----------------------------------------------------
    # Si la sesión pertenece a una rutina, comprobar si
    # este ejercicio ha sido sustituido.
    #
    # Si fue sustituido:
    #   - NO permitimos registrar el original.
    #   - SÍ permitimos registrar el sustituto.
    # -----------------------------------------------------

    if workout["routine_id"]:

        original_substitution = conn.execute("""
            SELECT
                original_exercise_id,
                substitute_exercise_id
            FROM workout_exercise_substitutions
            WHERE workout_log_id = ?
              AND original_exercise_id = ?
        """, (
            workout_id,
            workout_set.exercise_id,
        )).fetchone()

        if original_substitution:
            conn.close()

            raise HTTPException(
                status_code=409,
                detail=(
                    "Este ejercicio ha sido sustituido en esta sesión. "
                    "Debes registrar el ejercicio alternativo."
                )
            )

        # -------------------------------------------------
        # Comprobar si el ejercicio es un sustituto elegido
        # en esta sesión.
        # -------------------------------------------------

        selected_substitution = conn.execute("""
            SELECT
                original_exercise_id,
                substitute_exercise_id
            FROM workout_exercise_substitutions
            WHERE workout_log_id = ?
              AND substitute_exercise_id = ?
        """, (
            workout_id,
            workout_set.exercise_id,
        )).fetchone()

        # Si es un sustituto elegido, está permitido.
        #
        # Si no es un sustituto, comprobamos que pertenezca
        # a la rutina original.
        if not selected_substitution:

            routine_exercise = conn.execute("""
                SELECT id
                FROM routine_exercises
                WHERE routine_id = ?
                  AND exercise_id = ?
            """, (
                workout["routine_id"],
                workout_set.exercise_id,
            )).fetchone()

            if not routine_exercise:
                conn.close()

                raise HTTPException(
                    status_code=400,
                    detail=(
                        "El ejercicio no pertenece a la rutina "
                        "ni ha sido seleccionado como sustitución."
                    )
                )

    # -----------------------------------------------------
    # Validaciones de la serie
    # -----------------------------------------------------

    if workout_set.set_number < 1:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="set_number debe ser >= 1"
        )

    if workout_set.reps < 1:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="reps debe ser >= 1"
        )

    if workout_set.weight_kg < 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="weight_kg debe ser >= 0"
        )

    if workout_set.rir is not None:
        if workout_set.rir < 0 or workout_set.rir > 10:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="RIR debe estar entre 0 y 10"
            )

    # -----------------------------------------------------
    # Evitar duplicar número de serie para el mismo
    # ejercicio dentro del entrenamiento
    # -----------------------------------------------------

    existing_set = conn.execute("""
        SELECT id
        FROM workout_sets
        WHERE workout_log_id = ?
          AND exercise_id = ?
          AND set_number = ?
    """, (
        workout_id,
        workout_set.exercise_id,
        workout_set.set_number,
    )).fetchone()

    if existing_set:
        conn.close()

        raise HTTPException(
            status_code=409,
            detail=(
                "Ya existe esa serie para este ejercicio "
                "en este entrenamiento."
            )
        )

    # -----------------------------------------------------
    # Insertar serie
    # -----------------------------------------------------

    set_id = str(uuid.uuid4())

    conn.execute("""
        INSERT INTO workout_sets (
            id,
            workout_log_id,
            exercise_id,
            set_number,
            weight_kg,
            reps,
            rir,
            is_warmup,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        set_id,
        workout_id,
        workout_set.exercise_id,
        workout_set.set_number,
        workout_set.weight_kg,
        workout_set.reps,
        workout_set.rir,
        int(workout_set.is_warmup),
        workout_set.notes,
    ))

    conn.commit()

    row = conn.execute("""
        SELECT
            ws.id,
            ws.workout_log_id,
            ws.exercise_id,
            e.name AS exercise_name,
            ws.set_number,
            ws.weight_kg,
            ws.reps,
            ws.rir,
            ws.is_warmup,
            ws.notes
        FROM workout_sets ws
        JOIN exercises e
          ON e.id = ws.exercise_id
        WHERE ws.id = ?
    """, (
        set_id,
    )).fetchone()

    conn.close()

    return dict(row)


class WorkoutSetUpdate(BaseModel):
    set_number: int
    weight_kg: float
    reps: int
    rir: int | None = None
    is_warmup: bool = False
    notes: str | None = None


@app.put("/api/workouts/{workout_id}/sets/{set_id}")
def update_workout_set(
    workout_id: str,
    set_id: str,
    workout_set: WorkoutSetUpdate,
    user_id: str,
):
    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar entrenamiento y propietario
    # -----------------------------------------------------

    workout = conn.execute("""
        SELECT
            id,
            user_id,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
    """, (
        workout_id,
        user_id,
    )).fetchone()

    if not workout:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Entrenamiento no encontrado",
        )

    if workout["status"] != "in_progress":
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="El entrenamiento no está en curso",
        )

    # -----------------------------------------------------
    # Comprobar que la serie pertenece al entrenamiento
    # -----------------------------------------------------

    existing_set = conn.execute("""
        SELECT
            id,
            workout_log_id,
            exercise_id
        FROM workout_sets
        WHERE id = ?
          AND workout_log_id = ?
    """, (
        set_id,
        workout_id,
    )).fetchone()

    if not existing_set:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Serie no encontrada en este entrenamiento",
        )

    exercise_id = existing_set["exercise_id"]

    # -----------------------------------------------------
    # Validaciones
    # -----------------------------------------------------

    if workout_set.set_number < 1:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="set_number debe ser >= 1",
        )

    if workout_set.reps < 1:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="reps debe ser >= 1",
        )

    if workout_set.weight_kg < 0:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail="weight_kg debe ser >= 0",
        )

    if workout_set.rir is not None:
        if workout_set.rir < 0 or workout_set.rir > 10:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="RIR debe estar entre 0 y 10",
            )

    # -----------------------------------------------------
    # Evitar duplicar número de serie
    # -----------------------------------------------------

    duplicate = conn.execute("""
        SELECT id
        FROM workout_sets
        WHERE workout_log_id = ?
          AND exercise_id = ?
          AND set_number = ?
          AND id != ?
    """, (
        workout_id,
        exercise_id,
        workout_set.set_number,
        set_id,
    )).fetchone()

    if duplicate:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=(
                "Ya existe esa serie para este ejercicio "
                "en este entrenamiento."
            ),
        )

    # -----------------------------------------------------
    # Actualizar
    # -----------------------------------------------------

    conn.execute("""
        UPDATE workout_sets
        SET
            set_number = ?,
            weight_kg = ?,
            reps = ?,
            rir = ?,
            is_warmup = ?,
            notes = ?
        WHERE id = ?
          AND workout_log_id = ?
    """, (
        workout_set.set_number,
        workout_set.weight_kg,
        workout_set.reps,
        workout_set.rir,
        int(workout_set.is_warmup),
        workout_set.notes,
        set_id,
        workout_id,
    ))

    conn.commit()

    row = conn.execute("""
        SELECT
            ws.id,
            ws.workout_log_id,
            ws.exercise_id,
            e.name AS exercise_name,
            ws.set_number,
            ws.weight_kg,
            ws.reps,
            ws.rir,
            ws.is_warmup,
            ws.notes
        FROM workout_sets ws
        JOIN exercises e
          ON e.id = ws.exercise_id
        WHERE ws.id = ?
          AND ws.workout_log_id = ?
    """, (
        set_id,
        workout_id,
    )).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/workouts/{workout_id}/sets/{set_id}")
def delete_workout_set(
    workout_id: str,
    set_id: str,
    user_id: str,
):
    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar entrenamiento y propietario
    # -----------------------------------------------------

    workout = conn.execute("""
        SELECT
            id,
            user_id,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
    """, (
        workout_id,
        user_id,
    )).fetchone()

    if not workout:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Entrenamiento no encontrado",
        )

    if workout["status"] != "in_progress":
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="El entrenamiento no está en curso",
        )

    # -----------------------------------------------------
    # Comprobar serie
    # -----------------------------------------------------

    existing_set = conn.execute("""
        SELECT
            id,
            exercise_id,
            set_number
        FROM workout_sets
        WHERE id = ?
          AND workout_log_id = ?
    """, (
        set_id,
        workout_id,
    )).fetchone()

    if not existing_set:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Serie no encontrada en este entrenamiento",
        )

    # -----------------------------------------------------
    # Eliminar
    # -----------------------------------------------------

    conn.execute("""
        DELETE FROM workout_sets
        WHERE id = ?
          AND workout_log_id = ?
    """, (
        set_id,
        workout_id,
    ))

    conn.commit()

    conn.close()

    return {
        "id": set_id,
        "workout_log_id": workout_id,
        "deleted": True,
    }


@app.get("/api/routines/{routine_id}/recommendations")
def get_routine_recommendations(routine_id: str, user_id: str):
    conn = get_connection()

    routine = conn.execute(
        """
        SELECT id, user_id, name, day_order, is_active
        FROM routines
        WHERE id = ?
          AND user_id = ?
          AND is_active = 1
        """,
        (routine_id, user_id),
    ).fetchone()

    if routine is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Rutina no encontrada")

    exercises = conn.execute(
        """
        SELECT
            re.id AS routine_exercise_id,
            re.exercise_id,
            re."order",
            re.target_sets,
            re.target_rep_min,
            re.target_rep_max,
            re.target_rir,
            re.rest_seconds,
            re.is_optional,
            e.name,
            e.equipment,
            e.weight_increment_kg,
            e.progression_type,
            e.rep_progression_enabled
        FROM routine_exercises re
        JOIN exercises e
          ON e.id = re.exercise_id
        WHERE re.routine_id = ?
          AND e.is_active = 1
        ORDER BY re."order"
        """,
        (routine_id,),
    ).fetchall()

    recommendations = []

    for exercise in exercises:
        last_workout = conn.execute(
            """
            SELECT wl.id, wl.date
            FROM workout_logs wl
            JOIN workout_sets ws
              ON ws.workout_log_id = wl.id
            WHERE wl.user_id = ?
              AND wl.status = 'completed'
              AND ws.exercise_id = ?
              AND ws.is_warmup = 0
            ORDER BY datetime(wl.date) DESC
            LIMIT 1
            """,
            (user_id, exercise["exercise_id"]),
        ).fetchone()

        base_response = {
            "exercise_id": exercise["exercise_id"],
            "exercise_name": exercise["name"],
            "order": exercise["order"],
            "target_sets": exercise["target_sets"],
            "target_rep_min": exercise["target_rep_min"],
            "target_rep_max": exercise["target_rep_max"],
            "target_rir": exercise["target_rir"],
            "weight_increment_kg": exercise["weight_increment_kg"],
            "progression_type": exercise["progression_type"],
            "rep_progression_enabled": bool(exercise["rep_progression_enabled"]),
        }

        if last_workout is None:
            recommendations.append(
                {
                    **base_response,
                    "recommendation": "start",
                    "recommended_weight_kg": None,
                    "recommended_rep_target": exercise["target_rep_min"],
                    "reason": (
                        "No hay histórico de series efectivas. "
                        f"Empieza con una carga que permita "
                        f"{exercise['target_rep_min']}-{exercise['target_rep_max']} "
                        f"repeticiones dejando aproximadamente "
                        f"{exercise['target_rir']} RIR."
                    ),
                    "last_performance": None,
                }
            )
            continue

        last_sets = conn.execute(
            """
            SELECT set_number, weight_kg, reps, rir
            FROM workout_sets
            WHERE workout_log_id = ?
              AND exercise_id = ?
              AND is_warmup = 0
            ORDER BY set_number
            """,
            (
                last_workout["id"],
                exercise["exercise_id"],
            ),
        ).fetchall()

        if not last_sets:
            recommendations.append(
                {
                    **base_response,
                    "recommendation": "start",
                    "recommended_weight_kg": None,
                    "recommended_rep_target": exercise["target_rep_min"],
                    "reason": "No hay series efectivas registradas.",
                    "last_performance": None,
                }
            )
            continue

        reps = [int(row["reps"]) for row in last_sets]
        weights = [float(row["weight_kg"]) for row in last_sets]
        rirs = [row["rir"] for row in last_sets]

        current_weight = max(weights)

        all_reached_min = all(
            rep >= exercise["target_rep_min"]
            for rep in reps
        )

        all_reached_max = all(
            rep >= exercise["target_rep_max"]
            for rep in reps
        )

        rir_available = all(rir is not None for rir in rirs)

        all_rir_at_or_above_target = (
            rir_available
            and all(
                int(rir) >= exercise["target_rir"]
                for rir in rirs
            )
        )

        any_rir_too_low = any(
            int(rir) < exercise["target_rir"]
            for rir in rirs
            if rir is not None
        )

        rep_progression_enabled = bool(
            exercise["rep_progression_enabled"]
        )

        weight_increment = (
            float(exercise["weight_increment_kg"])
            if exercise["weight_increment_kg"] is not None
            else 0.0
        )

        # ---------------------------------------------------------
        # DOBLE PROGRESIÓN
        # ---------------------------------------------------------

        if not all_reached_min:
            recommendation = "maintain_weight"
            recommended_weight = current_weight
            recommended_rep_target = exercise["target_rep_min"]

            reason = (
                f"No todas las series han alcanzado el mínimo de "
                f"{exercise['target_rep_min']} repeticiones. "
                f"Mantén {current_weight:g} kg e intenta completar "
                f"al menos {exercise['target_rep_min']} repeticiones "
                "en todas las series."
            )

        elif all_reached_max:
            if rir_available and all_rir_at_or_above_target:
                if weight_increment > 0:
                    recommendation = "increase_weight"
                    recommended_weight = current_weight + weight_increment
                    recommended_rep_target = exercise["target_rep_min"]

                    reason = (
                        f"Has completado todas las series en el máximo "
                        f"del rango ({exercise['target_rep_max']} reps) "
                        f"con al menos {exercise['target_rir']} RIR. "
                        f"Sube {weight_increment:g} kg y vuelve al inicio "
                        f"del rango ({exercise['target_rep_min']} reps)."
                    )
                else:
                    recommendation = "maintain_weight"
                    recommended_weight = current_weight
                    recommended_rep_target = exercise["target_rep_max"]

                    reason = (
                        "Has alcanzado el máximo del rango con el RIR "
                        "objetivo, pero este ejercicio no tiene un incremento "
                        "de peso configurado."
                    )

            elif any_rir_too_low:
                recommendation = "maintain_weight"
                recommended_weight = current_weight
                recommended_rep_target = exercise["target_rep_max"]

                reason = (
                    f"Has alcanzado el máximo de {exercise['target_rep_max']} "
                    "repeticiones, pero alguna serie ha quedado por debajo "
                    f"del RIR objetivo ({exercise['target_rir']}). "
                    f"Mantén {current_weight:g} kg."
                )

            else:
                recommendation = "maintain_weight"
                recommended_weight = current_weight
                recommended_rep_target = exercise["target_rep_max"]

                reason = (
                    f"Has alcanzado el máximo de {exercise['target_rep_max']} "
                    "repeticiones, pero no hay RIR suficiente registrado "
                    "para justificar una subida. Mantén la carga."
                )

        elif rep_progression_enabled:
            next_rep_target = min(
                max(reps) + 1,
                exercise["target_rep_max"],
            )

            recommendation = "add_reps"
            recommended_weight = current_weight
            recommended_rep_target = next_rep_target

            if any_rir_too_low:
                reason = (
                    f"Mantén {current_weight:g} kg. Busca progresar en "
                    "repeticiones sin aumentar la carga porque alguna serie "
                    "quedó por debajo del RIR objetivo."
                )
            else:
                reason = (
                    f"Mantén {current_weight:g} kg y busca aumentar "
                    f"las repeticiones. Próximo objetivo: "
                    f"{next_rep_target} reps por serie."
                )

        else:
            recommendation = "maintain_weight"
            recommended_weight = current_weight
            recommended_rep_target = max(reps)

            reason = (
                f"La progresión por repeticiones está desactivada. "
                f"Mantén {current_weight:g} kg."
            )

        recommendations.append(
            {
                **base_response,
                "recommendation": recommendation,
                "recommended_weight_kg": recommended_weight,
                "recommended_rep_target": recommended_rep_target,
                "reason": reason,
                "last_performance": {
                    "workout_id": last_workout["id"],
                    "date": last_workout["date"],
                    "sets": [
                        {
                            "set_number": int(row["set_number"]),
                            "weight_kg": float(row["weight_kg"]),
                            "reps": int(row["reps"]),
                            "rir": row["rir"],
                        }
                        for row in last_sets
                    ],
                },
            }
        )

    conn.close()

    return {
        "routine_id": routine["id"],
        "routine_name": routine["name"],
        "user_id": routine["user_id"],
        "recommendations": recommendations,
    }


@app.get("/api/exercises/{exercise_id}/substitutions")
def get_exercise_substitutions(exercise_id: str, user_id: str):
    conn = get_connection()

    exercise = conn.execute("""
        SELECT id, name, equipment, target_muscle, category
        FROM exercises
        WHERE id = ? AND is_active = 1
    """, (exercise_id,)).fetchone()

    if not exercise:
        conn.close()
        raise HTTPException(status_code=404, detail="Ejercicio no encontrado")

    # Comprobar usuario
    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    rows = conn.execute("""
        SELECT
            es.alternative_exercise_id,
            e.name,
            e.target_muscle,
            e.category,
            e.equipment,
            e.safety_notes,
            e.instructions,
            e.contraindications,
            es.priority,
            es.reason,
            es.same_muscle,
            es.same_movement_pattern
        FROM exercise_substitutions es
        JOIN exercises e
          ON e.id = es.alternative_exercise_id
        WHERE es.exercise_id = ?
          AND es.is_active = 1
          AND e.is_active = 1
        ORDER BY
            es.priority ASC,
            es.same_movement_pattern DESC,
            es.same_muscle DESC,
            e.name ASC
    """, (exercise_id,)).fetchall()

    result = []

    for row in rows:
        result.append({
            "exercise_id": row["alternative_exercise_id"],
            "name": row["name"],
            "target_muscle": row["target_muscle"],
            "category": row["category"],
            "equipment": row["equipment"],
            "safety_notes": row["safety_notes"],
            "instructions": row["instructions"],
            "contraindications": row["contraindications"],
            "priority": row["priority"],
            "reason": row["reason"],
            "same_muscle": bool(row["same_muscle"]),
            "same_movement_pattern": bool(row["same_movement_pattern"]),
        })

    conn.close()

    return {
        "exercise_id": exercise["id"],
        "exercise_name": exercise["name"],
        "substitutions": result,
    }

@app.get("/api/workouts/{workout_id}")
def get_workout(workout_id: str, user_id: str):
    conn = get_connection()

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
            r.name AS routine_name
        FROM workout_logs wl
        LEFT JOIN routines r
          ON r.id = wl.routine_id
        WHERE wl.id = ?
          AND wl.user_id = ?
        """,
        (workout_id, user_id),
    ).fetchone()

    if workout is None:
        conn.close()
        raise HTTPException(status_code=404, detail="Entrenamiento no encontrado")

    sets = conn.execute(
        """
        SELECT
            ws.id,
            ws.exercise_id,
            e.name AS exercise_name,
            e.target_muscle,
            e.category,
            e.equipment,
            ws.set_number,
            ws.weight_kg,
            ws.reps,
            ws.rir,
            ws.is_warmup,
            ws.notes
        FROM workout_sets ws
        JOIN exercises e
          ON e.id = ws.exercise_id
        WHERE ws.workout_log_id = ?
        ORDER BY ws.exercise_id, ws.set_number
        """,
        (workout_id,),
    ).fetchall()

    result_sets = [dict(row) for row in sets]

    conn.close()

    return {
        "id": workout["id"],
        "user_id": workout["user_id"],
        "routine_id": workout["routine_id"],
        "routine_name": workout["routine_name"],
        "date": workout["date"],
        "duration_minutes": workout["duration_minutes"],
        "notes": workout["notes"],
        "status": workout["status"],
        "sets": result_sets,
    }

@app.put("/api/workouts/{workout_id}")
def update_workout(
    workout_id: str,
    workout: WorkoutUpdate,
    user_id: str,
):
    if workout.status not in {
        "in_progress",
        "completed",
        "cancelled",
    }:
        raise HTTPException(
            status_code=400,
            detail="Estado no válido",
        )

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT
            id,
            user_id,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
        """,
        (workout_id, user_id),
    ).fetchone()

    if existing is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Entrenamiento no encontrado para este usuario",
        )

    current_status = existing["status"]

    # Los entrenamientos finalizados o cancelados son inmutables.
    if current_status in {"completed", "cancelled"}:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="El entrenamiento ya está finalizado y no puede cambiar de estado",
        )

    # Un entrenamiento en curso solo puede mantenerse en curso,
    # finalizarse o cancelarse.
    allowed_transitions = {
        "in_progress": {
            "in_progress",
            "completed",
            "cancelled",
        }
    }

    if workout.status not in allowed_transitions.get(current_status, set()):
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"No se puede cambiar de '{current_status}' a '{workout.status}'",
        )

    if workout.duration_minutes is not None:
        if workout.duration_minutes < 0:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail="La duración no puede ser negativa",
            )

    conn.execute(
        """
        UPDATE workout_logs
        SET
            status = ?,
            duration_minutes = ?,
            notes = ?
        WHERE id = ?
          AND user_id = ?
        """,
        (
            workout.status,
            workout.duration_minutes,
            workout.notes,
            workout_id,
            user_id,
        ),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT
            id,
            user_id,
            routine_id,
            date,
            duration_minutes,
            notes,
            status
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
        """,
        (workout_id, user_id),
    ).fetchone()

    conn.close()

    return dict(row)
