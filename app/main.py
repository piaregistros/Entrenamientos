import json
import logging
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, File, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .database import get_connection, init_db
from .auth_routes import router as auth_router
from .activity_routes import router as activity_router, init_activity_db
from .diet_routes import router as diet_router, init_diet_db
from .progress_routes import router as progress_router, init_progress_db, apply_progression, refresh_progress_after_set_edit
from .onboarding_routes import router as onboarding_router
from .progression_db import compute_exercise_target, ensure_progression_schema
from .progression import MEASURE_TYPES, default_increment, infer_measure_type
from .workout_extras import router as workout_extras_router, load_extra_exercises, load_substitutions
from .exercise_sheets import ensure_exercise_sheets, attach_sheet_fields
from .exercise_info_routes import router as exercise_info_router
from .substitutions import (
    router as substitutions_router,
    ensure_substitutions,
    record_substitution_pref,
    apply_always_substitutions,
    enrich_substitutions,
    recommendation_item,
    score_pair,
    slot_for,
    EXERCISE_REC_COLUMNS,
)
from .exercise_crud import router as exercise_crud_router, ensure_crud_schema, apply_data_migrations
from .push_routes import router as push_router
from .push import init_push_db, start_scheduler, stop_scheduler
from .auth import (
    get_authenticated_user,
    require_admin,
    resolve_target_user,
    validate_csrf_token,
    CSRF_COOKIE_NAME,
)

from app.workout_history_routes import (
    get_in_progress_workout,
    list_workouts,
    delete_workout,
)


app = FastAPI(
    title="Entrenamiento",
    version="0.1.0",
)

app.include_router(auth_router)
app.include_router(activity_router)
app.include_router(diet_router)
app.include_router(progress_router)
app.include_router(onboarding_router)
app.include_router(workout_extras_router)
app.include_router(exercise_info_router)
app.include_router(substitutions_router)
app.include_router(exercise_crud_router)
app.include_router(push_router)

app.add_api_route(
    "/api/workouts/in-progress",
    get_in_progress_workout,
    methods=["GET"],
    name="get_in_progress_workout",
)

app.add_api_route(
    "/api/workouts",
    list_workouts,
    methods=["GET"],
    name="list_workouts",
)

app.add_api_route(
    "/api/workouts/{workout_id}",
    delete_workout,
    methods=["DELETE"],
    name="delete_workout",
)

@app.middleware("http")
async def csrf_protection_middleware(request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        path = request.url.path

        # Login no necesita CSRF porque todavía no existe sesión.
        # Health tampoco necesita protección.
        if path not in {"/api/auth/login", "/health"}:
            session_cookie = request.cookies.get("entrenamiento_session")

            if session_cookie:
                cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                header_token = request.headers.get("X-CSRF-Token")

                if not validate_csrf_token(cookie_token, header_token):
                    from fastapi.responses import JSONResponse

                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF validation failed"},
                    )

    return await call_next(request)


logger = logging.getLogger(__name__)


@app.on_event("startup")
def startup():
    # Todo el DDL / migraciones se hace UNA vez aquí, nunca en peticiones GET
    # (evita "database is locked" al cargar el Inicio con varias peticiones).
    init_db()
    init_activity_db()
    init_diet_db()
    init_progress_db()
    conn = get_connection()
    try:
        _ensure_session_label(conn)
    finally:
        conn.close()
    # Fase 5: fichas de ejercicio + vídeos (idempotente, una sola vez al arrancar).
    conn = get_connection()
    try:
        ensure_exercise_sheets(conn)
    except Exception:
        logger.exception("No se pudieron aplicar las fichas/vídeos de ejercicios; la app sigue arrancando")
    finally:
        conn.close()


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/users")
def get_users(current_user = Depends(get_authenticated_user)):
    require_admin(current_user)

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


def _ensure_session_label(conn) -> None:
    cols = {row["name"] for row in conn.execute("PRAGMA table_info(routines)")}
    if "session_label" not in cols:
        conn.execute("ALTER TABLE routines ADD COLUMN session_label TEXT")
        conn.commit()


@app.on_event("startup")
def startup_progression():
    # Fase 6: measure_type / weight_increment_kg de todos los ejercicios (idempotente).
    # Handler propio: se ejecuta después de `startup` (y de las fichas de la Fase 5 si están).
    import logging as _logging

    conn = get_connection()
    try:
        ensure_progression_schema(conn)
    except Exception:
        _logging.getLogger(__name__).exception("No se pudo aplicar el esquema de progresión; la app sigue arrancando")
    finally:
        conn.close()


@app.on_event("startup")
def startup_fase7():
    # Fase 7: sustituciones (tablas, parejas curadas y automáticas), columnas de CRUD y migraciones
    # de datos idempotentes. Handler propio, después de los de las fases 5 y 6.
    import logging as _logging

    conn = get_connection()
    try:
        ensure_crud_schema(conn)
        ensure_substitutions(conn)
        apply_data_migrations(conn)
    except Exception:
        _logging.getLogger(__name__).exception("No se pudo aplicar la Fase 7 (sustituciones/CRUD); la app sigue arrancando")
    finally:
        conn.close()


@app.on_event("startup")
def startup_fase10_push():
    # Fase 10: tablas de suscripciones y avisos programados (DDL solo al arrancar).
    try:
        init_push_db()
    except Exception:
        logger.exception("No se pudo aplicar el esquema de avisos push; la app sigue arrancando")


@app.on_event("startup")
async def startup_fase10_scheduler():
    # Bucle en memoria que revisa scheduled_pushes cada 1-2 s. Sobrevive un reinicio
    # porque los avisos viven en la base de datos.
    try:
        start_scheduler()
    except Exception:
        logger.exception("No se pudo arrancar el programador de avisos push")


@app.on_event("shutdown")
async def shutdown_fase10_scheduler():
    stop_scheduler()


@app.get("/api/routines")
def get_routines(
    user_id: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    rows = conn.execute(
        """
        SELECT id, user_id, name, day_order, is_active, session_label, created_at
        FROM routines
        WHERE user_id = ?
          AND is_active = 1
        ORDER BY day_order
        """,
        (target_user_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


@app.get("/api/routines/{routine_id}")
def get_routine(
    routine_id: str,
    current_user = Depends(get_authenticated_user),
):
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

    if (
        current_user["role"] != "admin"
        and routine["user_id"] != current_user["id"]
    ):
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
            e.weight_increment_kg,
            e.progression_type,
            e.rep_progression_enabled,
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



@app.get("/api/routines/{routine_id}/overlap")
def routine_overlap(
    routine_id: str,
    current_user = Depends(get_authenticated_user),
):
    conn = get_connection()
    routine = conn.execute(
        "SELECT id, user_id, name FROM routines WHERE id = ?",
        (routine_id,),
    ).fetchone()
    if routine is None or (
        current_user["role"] != "admin"
        and routine["user_id"] != current_user["id"]
    ):
        conn.close()
        raise HTTPException(status_code=404, detail="Rutina no encontrada")

    last = conn.execute(
        """
        SELECT wl.id, wl.date, r.name AS routine_name
        FROM workout_logs wl
        LEFT JOIN routines r ON r.id = wl.routine_id
        WHERE wl.user_id = ? AND wl.status = 'completed'
        ORDER BY wl.date DESC
        LIMIT 1
        """,
        (routine["user_id"],),
    ).fetchone()
    names = []
    if last is not None:
        names = [
            row["name"]
            for row in conn.execute(
                """
                SELECT DISTINCT e.name
                FROM workout_sets ws
                JOIN routine_exercises re
                  ON re.exercise_id = ws.exercise_id
                 AND re.routine_id = ?
                JOIN exercises e ON e.id = ws.exercise_id
                WHERE ws.workout_log_id = ?
                  AND ws.is_warmup = 0
                ORDER BY e.name
                """,
                (routine_id, last["id"]),
            )
        ]
    conn.close()
    return {
        "exercises": names,
        "last_date": None if last is None else last["date"],
        "last_routine_name": None if last is None else last["routine_name"],
    }


@app.get("/api/routines/{routine_id}/with-last-performance")
def get_routine_with_last_performance(
    routine_id: str,
    user_id: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    # -----------------------------------------------------
    # Comprobar usuario
    # -----------------------------------------------------

    user = conn.execute("""
        SELECT id, name
        FROM users
        WHERE id = ?
    """, (target_user_id,)).fetchone()

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
    """, (routine_id, target_user_id)).fetchone()

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
            target_user_id,
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
                target_user_id,
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
    body_fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    water_pct: float | None = None
    visceral_fat: float | None = None
    basal_metabolic_rate_kcal: float | None = None
    bone_mass_kg: float | None = None
    notes: str | None = None


class BodyMetricUpdate(BaseModel):
    date: str
    weight_kg: float
    body_fat_pct: float | None = None
    muscle_mass_kg: float | None = None
    water_pct: float | None = None
    visceral_fat: float | None = None
    basal_metabolic_rate_kcal: float | None = None
    bone_mass_kg: float | None = None
    notes: str | None = None


class BodyMeasurementCreate(BaseModel):
    user_id: str
    date: str
    waist_cm: float | None = None
    chest_cm: float | None = None
    arm_left_cm: float | None = None
    arm_right_cm: float | None = None
    thigh_left_cm: float | None = None
    thigh_right_cm: float | None = None
    hip_cm: float | None = None
    neck_cm: float | None = None
    notes: str | None = None


class BodyMeasurementUpdate(BaseModel):
    date: str
    waist_cm: float | None = None
    chest_cm: float | None = None
    arm_left_cm: float | None = None
    arm_right_cm: float | None = None
    thigh_left_cm: float | None = None
    thigh_right_cm: float | None = None
    hip_cm: float | None = None
    neck_cm: float | None = None
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



class UserGoalCreate(BaseModel):
    user_id: str
    goal_type: str
    title: str
    description: str | None = None
    start_date: str
    target_date: str | None = None
    is_active: bool = True


class UserGoalUpdate(BaseModel):
    goal_type: str
    title: str
    description: str | None = None
    start_date: str
    target_date: str | None = None
    is_active: bool = True



class ProgressNoteCreate(BaseModel):
    user_id: str
    workout_log_id: str | None = None
    date: str
    energy: int | None = None
    satisfaction: int | None = None
    effort: int | None = None
    motivation: int | None = None
    recovery: int | None = None
    soreness: int | None = None
    notes: str | None = None


class ProgressNoteUpdate(BaseModel):
    date: str
    energy: int | None = None
    satisfaction: int | None = None
    effort: int | None = None
    motivation: int | None = None
    recovery: int | None = None
    soreness: int | None = None
    notes: str | None = None


@app.post("/api/body-metrics")
def create_body_metric(
    metric: BodyMetricCreate,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, metric.user_id)
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
        (user_id,),
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
        (user_id, date_value),
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
            body_fat_pct,
            muscle_mass_kg,
            water_pct,
            visceral_fat,
            basal_metabolic_rate_kcal,
            bone_mass_kg,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            metric_id,
            user_id,
            date_value,
            metric.weight_kg,
            metric.body_fat_pct,
            metric.muscle_mass_kg,
            metric.water_pct,
            metric.visceral_fat,
            metric.basal_metabolic_rate_kcal,
            metric.bone_mass_kg,
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
            body_fat_pct,
            muscle_mass_kg,
            water_pct,
            visceral_fat,
            basal_metabolic_rate_kcal,
            bone_mass_kg,
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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

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
            body_fat_pct,
            muscle_mass_kg,
            water_pct,
            visceral_fat,
            basal_metabolic_rate_kcal,
            bone_mass_kg,
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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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
        (metric_id, user_id),
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
        (user_id, date_value, metric_id),
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
            body_fat_pct = ?,
            muscle_mass_kg = ?,
            water_pct = ?,
            visceral_fat = ?,
            basal_metabolic_rate_kcal = ?,
            bone_mass_kg = ?,
            notes = ?
        WHERE id = ?
          AND user_id = ?
        """,
        (
            date_value,
            metric.weight_kg,
            metric.body_fat_pct,
            metric.muscle_mass_kg,
            metric.water_pct,
            metric.visceral_fat,
            metric.basal_metabolic_rate_kcal,
            metric.bone_mass_kg,
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
            body_fat_pct,
            muscle_mass_kg,
            water_pct,
            visceral_fat,
            basal_metabolic_rate_kcal,
            bone_mass_kg,
            notes
        FROM body_metrics
        WHERE id = ?
          AND user_id = ?
        """,
        (metric_id, user_id),
    ).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/body-metrics/{metric_id}")
def delete_body_metric(
    metric_id: str,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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
        (metric_id, user_id),
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
        (metric_id, user_id),
    )

    conn.commit()
    conn.close()

    return {
        "id": metric_id,
        "user_id": user_id,
        "deleted": True,
    }


# ============================================================
# BODY MEASUREMENTS
# ============================================================


# =========================================================
# USER GOALS
# =========================================================

VALID_GOAL_TYPES = {
    "muscle_gain",
    "strength",
    "fat_loss",
    "maintenance",
    "other",
}


def validate_goal_dates(start_date: str, target_date: str | None):
    from datetime import date

    try:
        start = date.fromisoformat(start_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="start_date must be a valid ISO date (YYYY-MM-DD)",
        )

    if target_date is None:
        return

    try:
        target = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="target_date must be a valid ISO date (YYYY-MM-DD)",
        )

    if target < start:
        raise HTTPException(
            status_code=400,
            detail="target_date cannot be earlier than start_date",
        )


@app.post("/api/body/goals")
def create_user_goal(
    goal: UserGoalCreate,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, goal.user_id)

    if goal.goal_type not in VALID_GOAL_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Invalid goal_type",
        )

    if not goal.title.strip():
        raise HTTPException(
            status_code=422,
            detail="title is required",
        )

    validate_goal_dates(goal.start_date, goal.target_date)

    goal_id = str(uuid.uuid4())
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO user_goals (
                id,
                user_id,
                goal_type,
                title,
                description,
                start_date,
                target_date,
                is_active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                goal_id,
                target_user_id,
                goal.goal_type,
                goal.title.strip(),
                goal.description,
                goal.start_date,
                goal.target_date,
                1 if goal.is_active else 0,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                user_id,
                goal_type,
                title,
                description,
                start_date,
                target_date,
                is_active,
                created_at,
                updated_at
            FROM user_goals
            WHERE id = ?
            """,
            (goal_id,),
        ).fetchone()

        return dict(row)

    finally:
        conn.close()


@app.get("/api/body/goals")
def get_user_goals(
    user_id: str,
    is_active: bool | None = Query(default=None),
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    try:
        if is_active is None:
            rows = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    goal_type,
                    title,
                    description,
                    start_date,
                    target_date,
                    is_active,
                    created_at,
                    updated_at
                FROM user_goals
                WHERE user_id = ?
                ORDER BY start_date DESC, created_at DESC
                """,
                (target_user_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    id,
                    user_id,
                    goal_type,
                    title,
                    description,
                    start_date,
                    target_date,
                    is_active,
                    created_at,
                    updated_at
                FROM user_goals
                WHERE user_id = ?
                  AND is_active = ?
                ORDER BY start_date DESC, created_at DESC
                """,
                (target_user_id, 1 if is_active else 0),
            ).fetchall()

        return {
            "count": len(rows),
            "goals": [dict(row) for row in rows],
        }

    finally:
        conn.close()


@app.put("/api/body/goals/{goal_id}")
def update_user_goal(
    goal_id: str,
    goal: UserGoalUpdate,
    user_id: str,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    if goal.goal_type not in VALID_GOAL_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Invalid goal_type",
        )

    if not goal.title.strip():
        raise HTTPException(
            status_code=422,
            detail="title is required",
        )

    validate_goal_dates(goal.start_date, goal.target_date)

    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM user_goals
            WHERE id = ?
              AND user_id = ?
            """,
            (goal_id, target_user_id),
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Goal not found",
            )

        conn.execute(
            """
            UPDATE user_goals
            SET
                goal_type = ?,
                title = ?,
                description = ?,
                start_date = ?,
                target_date = ?,
                is_active = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND user_id = ?
            """,
            (
                goal.goal_type,
                goal.title.strip(),
                goal.description,
                goal.start_date,
                goal.target_date,
                1 if goal.is_active else 0,
                goal_id,
                target_user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                user_id,
                goal_type,
                title,
                description,
                start_date,
                target_date,
                is_active,
                created_at,
                updated_at
            FROM user_goals
            WHERE id = ?
            """,
            (goal_id,),
        ).fetchone()

        return dict(row)

    finally:
        conn.close()


@app.delete("/api/body/goals/{goal_id}")
def delete_user_goal(
    goal_id: str,
    user_id: str,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM user_goals
            WHERE id = ?
              AND user_id = ?
            """,
            (goal_id, target_user_id),
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Goal not found",
            )

        conn.execute(
            """
            DELETE FROM user_goals
            WHERE id = ?
              AND user_id = ?
            """,
            (goal_id, target_user_id),
        )

        conn.commit()

        return {
            "message": "Goal deleted successfully",
            "id": goal_id,
        }

    finally:
        conn.close()




# =========================================================
# PROGRESS NOTES
# =========================================================

PROGRESS_NOTE_RATING_FIELDS = (
    "energy",
    "satisfaction",
    "effort",
    "motivation",
    "recovery",
    "soreness",
)


def validate_progress_note_date(value: str):
    from datetime import date

    try:
        date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="date must be a valid ISO date (YYYY-MM-DD)",
        )


def validate_progress_note_ratings(note):
    for field in PROGRESS_NOTE_RATING_FIELDS:
        value = getattr(note, field)

        if value is not None and not 1 <= value <= 5:
            raise HTTPException(
                status_code=422,
                detail=f"{field} must be between 1 and 5",
            )


def validate_progress_note_workout(
    conn,
    workout_log_id: str | None,
    user_id: str,
):
    if workout_log_id is None:
        return

    row = conn.execute(
        """
        SELECT id
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
        """,
        (workout_log_id, user_id),
    ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Workout log not found",
        )


@app.post("/api/progress-notes")
def create_progress_note(
    note: ProgressNoteCreate,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, note.user_id)

    validate_progress_note_date(note.date)
    validate_progress_note_ratings(note)

    note_id = str(uuid.uuid4())
    conn = get_connection()

    try:
        validate_progress_note_workout(
            conn,
            note.workout_log_id,
            target_user_id,
        )

        if note.workout_log_id is not None:
            existing = conn.execute(
                """
                SELECT id
                FROM progress_notes
                WHERE user_id = ?
                  AND workout_log_id = ?
                """,
                (target_user_id, note.workout_log_id),
            ).fetchone()

            if existing is not None:
                raise HTTPException(
                    status_code=409,
                    detail="A progress note already exists for this workout",
                )

        conn.execute(
            """
            INSERT INTO progress_notes (
                id,
                user_id,
                workout_log_id,
                date,
                energy,
                satisfaction,
                effort,
                motivation,
                recovery,
                soreness,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                note_id,
                target_user_id,
                note.workout_log_id,
                note.date,
                note.energy,
                note.satisfaction,
                note.effort,
                note.motivation,
                note.recovery,
                note.soreness,
                note.notes,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                user_id,
                workout_log_id,
                date,
                energy,
                satisfaction,
                effort,
                motivation,
                recovery,
                soreness,
                notes,
                created_at
            FROM progress_notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()

        return dict(row)

    finally:
        conn.close()


@app.get("/api/progress-notes")
def get_progress_notes(
    user_id: str,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    try:
        rows = conn.execute(
            """
            SELECT
                id,
                user_id,
                workout_log_id,
                date,
                energy,
                satisfaction,
                effort,
                motivation,
                recovery,
                soreness,
                notes,
                created_at
            FROM progress_notes
            WHERE user_id = ?
            ORDER BY date DESC, created_at DESC
            """,
            (target_user_id,),
        ).fetchall()

        return {
            "count": len(rows),
            "notes": [dict(row) for row in rows],
        }

    finally:
        conn.close()


@app.put("/api/progress-notes/{note_id}")
def update_progress_note(
    note_id: str,
    note: ProgressNoteUpdate,
    user_id: str,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    validate_progress_note_date(note.date)
    validate_progress_note_ratings(note)

    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM progress_notes
            WHERE id = ?
              AND user_id = ?
            """,
            (note_id, target_user_id),
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Progress note not found",
            )

        conn.execute(
            """
            UPDATE progress_notes
            SET
                date = ?,
                energy = ?,
                satisfaction = ?,
                effort = ?,
                motivation = ?,
                recovery = ?,
                soreness = ?,
                notes = ?
            WHERE id = ?
              AND user_id = ?
            """,
            (
                note.date,
                note.energy,
                note.satisfaction,
                note.effort,
                note.motivation,
                note.recovery,
                note.soreness,
                note.notes,
                note_id,
                target_user_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT
                id,
                user_id,
                workout_log_id,
                date,
                energy,
                satisfaction,
                effort,
                motivation,
                recovery,
                soreness,
                notes,
                created_at
            FROM progress_notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()

        return dict(row)

    finally:
        conn.close()


@app.delete("/api/progress-notes/{note_id}")
def delete_progress_note(
    note_id: str,
    user_id: str,
    current_user=Depends(get_authenticated_user),
):
    target_user_id = resolve_target_user(current_user, user_id)

    conn = get_connection()

    try:
        existing = conn.execute(
            """
            SELECT id
            FROM progress_notes
            WHERE id = ?
              AND user_id = ?
            """,
            (note_id, target_user_id),
        ).fetchone()

        if existing is None:
            raise HTTPException(
                status_code=404,
                detail="Progress note not found",
            )

        conn.execute(
            """
            DELETE FROM progress_notes
            WHERE id = ?
              AND user_id = ?
            """,
            (note_id, target_user_id),
        )

        conn.commit()

        return {
            "message": "Progress note deleted successfully",
            "id": note_id,
        }

    finally:
        conn.close()



@app.post("/api/body/measurements")
def create_body_measurement(
    measurement: BodyMeasurementCreate,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, measurement.user_id)
    date_value = validate_metric_date(measurement.date)

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

    existing = conn.execute(
        """
        SELECT id
        FROM body_measurements
        WHERE user_id = ?
          AND date = ?
        """,
        (user_id, date_value),
    ).fetchone()

    if existing:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ya existe una medición corporal para este usuario en esa fecha",
        )

    measurement_id = str(uuid.uuid4())

    conn.execute(
        """
        INSERT INTO body_measurements (
            id,
            user_id,
            date,
            waist_cm,
            chest_cm,
            arm_left_cm,
            arm_right_cm,
            thigh_left_cm,
            thigh_right_cm,
            hip_cm,
            neck_cm,
            notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            measurement_id,
            user_id,
            date_value,
            measurement.waist_cm,
            measurement.chest_cm,
            measurement.arm_left_cm,
            measurement.arm_right_cm,
            measurement.thigh_left_cm,
            measurement.thigh_right_cm,
            measurement.hip_cm,
            measurement.neck_cm,
            measurement.notes,
        ),
    )

    conn.commit()

    row = conn.execute(
        """
        SELECT
            id,
            user_id,
            date,
            waist_cm,
            chest_cm,
            arm_left_cm,
            arm_right_cm,
            thigh_left_cm,
            thigh_right_cm,
            hip_cm,
            neck_cm,
            notes,
            created_at
        FROM body_measurements
        WHERE id = ?
        """,
        (measurement_id,),
    ).fetchone()

    conn.close()

    return dict(row)


@app.get("/api/body/measurements")
def list_body_measurements(
    user_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

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
            waist_cm,
            chest_cm,
            arm_left_cm,
            arm_right_cm,
            thigh_left_cm,
            thigh_right_cm,
            hip_cm,
            neck_cm,
            notes,
            created_at
        FROM body_measurements
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
        "measurements": [dict(row) for row in rows],
    }


@app.put("/api/body/measurements/{measurement_id}")
def update_body_measurement(
    measurement_id: str,
    measurement: BodyMeasurementUpdate,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
    date_value = validate_metric_date(measurement.date)

    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM body_measurements
        WHERE id = ?
          AND user_id = ?
        """,
        (measurement_id, user_id),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Medición corporal no encontrada para este usuario",
        )

    duplicate = conn.execute(
        """
        SELECT id
        FROM body_measurements
        WHERE user_id = ?
          AND date = ?
          AND id != ?
        """,
        (user_id, date_value, measurement_id),
    ).fetchone()

    if duplicate:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ya existe otra medición corporal para este usuario en esa fecha",
        )

    conn.execute(
        """
        UPDATE body_measurements
        SET
            date = ?,
            waist_cm = ?,
            chest_cm = ?,
            arm_left_cm = ?,
            arm_right_cm = ?,
            thigh_left_cm = ?,
            thigh_right_cm = ?,
            hip_cm = ?,
            neck_cm = ?,
            notes = ?
        WHERE id = ?
          AND user_id = ?
        """,
        (
            date_value,
            measurement.waist_cm,
            measurement.chest_cm,
            measurement.arm_left_cm,
            measurement.arm_right_cm,
            measurement.thigh_left_cm,
            measurement.thigh_right_cm,
            measurement.hip_cm,
            measurement.neck_cm,
            measurement.notes,
            measurement_id,
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
            waist_cm,
            chest_cm,
            arm_left_cm,
            arm_right_cm,
            thigh_left_cm,
            thigh_right_cm,
            hip_cm,
            neck_cm,
            notes,
            created_at
        FROM body_measurements
        WHERE id = ?
          AND user_id = ?
        """,
        (measurement_id, user_id),
    ).fetchone()

    conn.close()

    return dict(row)


@app.delete("/api/body/measurements/{measurement_id}")
def delete_body_measurement(
    measurement_id: str,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
    conn = get_connection()

    existing = conn.execute(
        """
        SELECT id
        FROM body_measurements
        WHERE id = ?
          AND user_id = ?
        """,
        (measurement_id, user_id),
    ).fetchone()

    if not existing:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Medición corporal no encontrada para este usuario",
        )

    conn.execute(
        """
        DELETE FROM body_measurements
        WHERE id = ?
          AND user_id = ?
        """,
        (measurement_id, user_id),
    )

    conn.commit()
    conn.close()

    return {
        "id": measurement_id,
        "user_id": user_id,
        "deleted": True,
    }




# ============================================================
# BODY PHOTOS
# ============================================================

BODY_PHOTOS_DIR = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "uploads"
    / "body_photos"
)

BODY_PHOTO_MAX_BYTES = 10 * 1024 * 1024

BODY_PHOTO_ANGLES = {"front", "side", "back"}

BODY_PHOTO_SIGNATURES = {
    b"\xff\xd8\xff": ("image/jpeg", ".jpg"),
    b"\x89PNG\r\n\x1a\n": ("image/png", ".png"),
    b"RIFF": ("image/webp", ".webp"),
}


def validate_body_photo_angle(angle: str) -> str:
    angle = angle.strip().lower()

    if angle not in BODY_PHOTO_ANGLES:
        raise HTTPException(
            status_code=400,
            detail="Ángulo no válido. Debe ser front, side o back.",
        )

    return angle


def detect_body_photo_type(data: bytes) -> tuple[str, str]:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg", ".jpg"

    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png", ".png"

    if (
        len(data) >= 12
        and data.startswith(b"RIFF")
        and data[8:12] == b"WEBP"
    ):
        return "image/webp", ".webp"

    raise HTTPException(
        status_code=400,
        detail="El archivo no es una imagen JPEG, PNG o WebP válida.",
    )


def validate_body_photo_data(data: bytes) -> tuple[str, str]:
    if not data:
        raise HTTPException(
            status_code=400,
            detail="La imagen está vacía.",
        )

    if len(data) > BODY_PHOTO_MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail="La imagen supera el límite de 10 MB.",
        )

    return detect_body_photo_type(data)


@app.post("/api/body/photos")
async def upload_body_photo(
    user_id: str = Query(...),
    date: str = Query(...),
    angle: str = Query(...),
    file: UploadFile = File(...),
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
    date_value = validate_metric_date(date)
    angle = validate_body_photo_angle(angle)

    conn = get_connection()

    try:
        user = conn.execute(
            """
            SELECT id
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

        if not user:
            raise HTTPException(
                status_code=404,
                detail="Usuario no encontrado",
            )

        existing = conn.execute(
            """
            SELECT id, file_path
            FROM body_photos
            WHERE user_id = ?
              AND month_key = ?
              AND angle = ?
            """,
            (user_id, date_value[:7], angle),
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Ya existe una foto para ese usuario, mes y ángulo.",
            )

        data = await file.read()

        content_type, extension = validate_body_photo_data(data)

        photo_id = str(uuid.uuid4())
        month_key = date_value[:7]

        user_dir = BODY_PHOTOS_DIR / user_id / month_key
        user_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{photo_id}{extension}"
        absolute_path = user_dir / filename

        relative_path = (
            Path("body_photos")
            / user_id
            / month_key
            / filename
        )

        absolute_path.write_bytes(data)

        conn.execute(
            """
            INSERT INTO body_photos (
                id,
                user_id,
                date,
                month_key,
                angle,
                file_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                photo_id,
                user_id,
                date_value,
                month_key,
                angle,
                str(relative_path),
            ),
        )

        conn.commit()

        return {
            "id": photo_id,
            "user_id": user_id,
            "date": date_value,
            "month_key": month_key,
            "angle": angle,
            "file_path": str(relative_path),
            "content_type": content_type,
            "original_filename": file.filename,
        }

    except HTTPException:
        conn.close()
        raise

    except Exception:
        conn.rollback()
        conn.close()

        if "absolute_path" in locals() and absolute_path.exists():
            absolute_path.unlink()

        raise

    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/api/body/photos")
def list_body_photos(
    user_id: str,
    month_key: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

    if month_key is not None:
        if (
            len(month_key) != 7
            or month_key[4] != "-"
            or not month_key[:4].isdigit()
            or not month_key[5:].isdigit()
        ):
            raise HTTPException(
                status_code=400,
                detail="month_key debe tener formato YYYY-MM.",
            )

    conn = get_connection()

    try:
        query = """
            SELECT
                id,
                user_id,
                date,
                month_key,
                angle,
                file_path,
                created_at
            FROM body_photos
            WHERE user_id = ?
        """

        params = [user_id]

        if month_key:
            query += " AND month_key = ?"
            params.append(month_key)

        query += " ORDER BY date DESC, angle"

        rows = conn.execute(query, params).fetchall()

        return {
            "photos": [dict(row) for row in rows]
        }

    finally:
        conn.close()


@app.get("/api/body/photos/{photo_id}/file")
def get_body_photo_file(
    photo_id: str,
    current_user = Depends(get_authenticated_user),
):
    conn = get_connection()

    try:
        photo = conn.execute(
            """
            SELECT id, user_id, file_path, angle
            FROM body_photos
            WHERE id = ?
            """,
            (photo_id,),
        ).fetchone()

        if not photo:
            raise HTTPException(
                status_code=404,
                detail="Foto no encontrada",
            )

        resolve_target_user(current_user, photo["user_id"])

        relative_path = Path(photo["file_path"])

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
            or relative_path.parts[0] != "body_photos"
        ):
            raise HTTPException(
                status_code=500,
                detail="Ruta de foto inválida.",
            )

        absolute_path = BODY_PHOTOS_DIR / Path(*relative_path.parts[1:])

        if not absolute_path.is_file():
            raise HTTPException(
                status_code=404,
                detail="Archivo de foto no encontrado",
            )

        media_type, _ = detect_body_photo_type(
            absolute_path.read_bytes()[:16]
        )

        return FileResponse(
            absolute_path,
            media_type=media_type,
        )

    finally:
        conn.close()


@app.delete("/api/body/photos/{photo_id}")
def delete_body_photo(
    photo_id: str,
    current_user = Depends(get_authenticated_user),
):
    conn = get_connection()

    try:
        photo = conn.execute(
            """
            SELECT id, user_id, file_path
            FROM body_photos
            WHERE id = ?
            """,
            (photo_id,),
        ).fetchone()

        if not photo:
            raise HTTPException(
                status_code=404,
                detail="Foto no encontrada",
            )

        resolve_target_user(current_user, photo["user_id"])

        relative_path = Path(photo["file_path"])

        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or not relative_path.parts
            or relative_path.parts[0] != "body_photos"
        ):
            raise HTTPException(
                status_code=500,
                detail="Ruta de foto inválida.",
            )

        absolute_path = BODY_PHOTOS_DIR / Path(*relative_path.parts[1:])

        conn.execute(
            """
            DELETE FROM body_photos
            WHERE id = ?
            """,
            (photo_id,),
        )

        conn.commit()

        if absolute_path.is_file():
            absolute_path.unlink()

        return {
            "message": "Foto eliminada correctamente",
            "id": photo_id,
        }

    finally:
        conn.close()


@app.get("/api/stats/summary")
def get_stats_summary(
    user_id: str,
    date_from: str | None = None,
    date_to: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

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
    current_user = Depends(get_authenticated_user),
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
            rep_progression_enabled,
            created_by,
            is_custom
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

    exercises = attach_sheet_fields(conn, [dict(row) for row in rows])
    for exercise in exercises:
        exercise["is_custom"] = bool(exercise.get("is_custom"))
        exercise["can_edit"] = current_user["role"] == "admin" or (
            exercise["is_custom"] and exercise.get("created_by") == current_user["id"]
        )

    conn.close()

    return {
        "count": len(rows),
        "exercises": exercises,
    }

@app.get("/api/exercises/{exercise_id}/last-performance")
def get_last_performance(
    exercise_id: str,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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


from datetime import datetime, timezone
from app.workout_expiration import workout_is_expired


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
    current_exercise_id: str | None = None
    is_deload: int | None = 0


@app.post("/api/workouts")
def create_workout(
    workout: WorkoutCreate,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, workout.user_id)
    conn = get_connection()

    user = conn.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()

    if user is None:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado",
        )

    # Solo puede existir una sesión de entrenamiento activa por usuario.
    # Si existe una sesión antigua, se caduca antes de decidir si puede
    # reutilizarse.
    existing_in_progress = conn.execute(
        """
        SELECT
            id,
            routine_id,
            date,
            status,
            current_exercise_id
        FROM workout_logs
        WHERE user_id = ?
          AND status = 'in_progress'
        ORDER BY date DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if existing_in_progress is not None:
        if workout_is_expired(existing_in_progress["date"]):
            conn.execute(
                """
                UPDATE workout_logs
                SET status = 'expired'
                WHERE id = ?
                  AND user_id = ?
                  AND status = 'in_progress'
                """,
                (existing_in_progress["id"], user_id),
            )
            conn.commit()
        else:
            conn.close()
            return {
                "id": existing_in_progress["id"],
                "user_id": user_id,
                "routine_id": existing_in_progress["routine_id"],
                "date": existing_in_progress["date"],
                "status": "in_progress",
                "current_exercise_id": existing_in_progress["current_exercise_id"],
                "existing": True,
            }

    if workout.routine_id:
        routine = conn.execute(
            """
            SELECT id
            FROM routines
            WHERE id = ?
              AND user_id = ?
              AND is_active = 1
            """,
            (workout.routine_id, user_id),
        ).fetchone()

        if routine is None:
            conn.close()
            raise HTTPException(
                status_code=404,
                detail="Rutina no encontrada para este usuario",
            )

    workout_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

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
            user_id,
            workout.routine_id,
            now,
            workout.notes,
        ),
    )

    # Fase 7: las sustituciones marcadas «usar siempre» en esta rutina se aplican al empezar
    # (solo en entrenos NUEVOS; el early-return de arriba reutiliza el que ya está en curso).
    applied = apply_always_substitutions(conn, workout_id, user_id, workout.routine_id)
    substitutions = (
        enrich_substitutions(conn, user_id, workout_id, load_substitutions(conn, workout_id))
        if applied
        else []
    )

    conn.commit()
    conn.close()

    return {
        "id": workout_id,
        "user_id": user_id,
        "routine_id": workout.routine_id,
        "date": now,
        "status": "in_progress",
        "substitutions": substitutions,
    }



class WorkoutExerciseSubstitutionCreate(BaseModel):
    original_exercise_id: str
    substitute_exercise_id: str
    reason: str | None = None
    always_in_routine: bool | None = None  # Fase 7: «usar siempre esta sustitución en esta rutina»


@app.post("/api/workouts/{workout_id}/substitute-exercise")
def substitute_workout_exercise(
    workout_id: str,
    data: WorkoutExerciseSubstitutionCreate,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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

    if workout["status"] not in ("in_progress", "completed"):
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
    # Fase 7: se puede sustituir por CUALQUIER ejercicio activo del catálogo
    # (antes solo por las parejas curadas). La pareja curada, si existe, aporta
    # el motivo; si no, se calcula por parecido.
    # -----------------------------------------------------

    original_meta = conn.execute(
        "SELECT * FROM exercises WHERE id = ?", (data.original_exercise_id,)
    ).fetchone()
    substitute_meta = conn.execute(
        "SELECT * FROM exercises WHERE id = ?", (data.substitute_exercise_id,)
    ).fetchone()
    computed_score, computed_level, computed_reason = score_pair(
        dict(original_meta), dict(substitute_meta)
    )
    substitution = conn.execute("""
        SELECT priority, reason, same_muscle, same_movement_pattern
        FROM exercise_substitutions
        WHERE exercise_id = ?
          AND alternative_exercise_id = ?
          AND is_active = 1
    """, (
        data.original_exercise_id,
        data.substitute_exercise_id,
    )).fetchone()
    if substitution is None:
        substitution = {
            "priority": 1 if computed_score >= 85 else 2 if computed_score >= 65 else 3,
            "reason": computed_reason or "Sustitución elegida por el usuario",
            "same_muscle": computed_level in ("pattern", "muscle"),
            "same_movement_pattern": computed_level == "pattern",
        }

    # El sustituto no puede ser ya otro ejercicio de la rutina.
    already_in_routine = conn.execute(
        "SELECT 1 FROM routine_exercises WHERE routine_id = ? AND exercise_id = ?",
        (workout["routine_id"], data.substitute_exercise_id),
    ).fetchone()
    if already_in_routine:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ese ejercicio ya forma parte de la rutina"
        )

    # -----------------------------------------------------
    # Comprobar si ya existe una sustitución para ese
    # ejercicio en esta sesión
    # -----------------------------------------------------

    existing = conn.execute("""
        SELECT id, substitute_exercise_id
        FROM workout_exercise_substitutions
        WHERE workout_log_id = ?
          AND original_exercise_id = ?
    """, (
        workout_id,
        data.original_exercise_id,
    )).fetchone()

    # Fase 7: el sustituto tampoco puede estar ya haciendo de sustituto de otro hueco.
    used_elsewhere = conn.execute("""
        SELECT 1 FROM workout_exercise_substitutions
        WHERE workout_log_id = ? AND substitute_exercise_id = ? AND original_exercise_id <> ?
    """, (workout_id, data.substitute_exercise_id, data.original_exercise_id)).fetchone()
    if used_elsewhere:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Ese ejercicio ya sustituye a otro de esta sesión"
        )

    if existing and existing["substitute_exercise_id"] == data.substitute_exercise_id:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="Este ejercicio ya ha sido sustituido en esta sesión"
        )

    if existing:
        # Cambiar de opinión: se puede cambiar de sustituto mientras no haya series registradas con él.
        logged = conn.execute(
            "SELECT COUNT(*) FROM workout_sets WHERE workout_log_id = ? AND exercise_id = ?",
            (workout_id, existing["substitute_exercise_id"]),
        ).fetchone()[0]
        if logged:
            conn.close()
            raise HTTPException(
                status_code=409,
                detail="Este ejercicio ya ha sido sustituido en esta sesión y tiene series registradas"
            )

    # -----------------------------------------------------
    # Registrar la sustitución
    # -----------------------------------------------------

    reason = data.reason or substitution["reason"]

    if existing:
        substitution_id = existing["id"]
        conn.execute(
            "UPDATE workout_exercise_substitutions SET substitute_exercise_id = ?, reason = ? WHERE id = ?",
            (data.substitute_exercise_id, reason, substitution_id),
        )
    else:
        substitution_id = str(uuid.uuid4())
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

    # Fase 7: recordar la elección (y, si se pide, fijarla para esta rutina).
    record_substitution_pref(
        conn, user_id, data.original_exercise_id, data.substitute_exercise_id,
        routine_id=workout["routine_id"], always=data.always_in_routine,
    )

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
        "always_in_routine": bool(data.always_in_routine),
    }

    # Fase 7: historial y objetivo siguiente DEL SUSTITUTO (con el rango de series/reps del hueco).
    slot = slot_for(conn, workout["routine_id"], data.original_exercise_id)
    substitute_row = conn.execute(
        f"SELECT {EXERCISE_REC_COLUMNS} FROM exercises e WHERE e.id = ?",
        (data.substitute_exercise_id,),
    ).fetchone()
    recommendation = recommendation_item(
        conn, user_id, workout["routine_id"], workout_id, slot, substitute_row
    )
    recommendation["original_exercise_id"] = data.original_exercise_id
    recommendation["substituted"] = True
    result["recommendation"] = recommendation
    result["last_performance"] = (
        recommendation["last_performance"]["sets"]
        if recommendation["last_performance"]
        else None
    )
    result["last_performance_detail"] = recommendation["last_performance"]

    conn.close()

    return result

@app.post("/api/workouts/{workout_id}/sets")
def add_workout_set(
    workout_id: str,
    workout_set: WorkoutSetCreate,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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

    if workout["status"] not in ("in_progress", "completed"):
        conn.close()
        raise HTTPException(
            status_code=409,
            detail="El entrenamiento no admite series"
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

            # Sesión abierta o ya cerrada: se puede apuntar un extra
            # (plancha, máquina del gym, etc.) aunque no esté en la rutina.
            if not routine_exercise and workout["status"] not in ("in_progress", "completed"):
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

    refresh_progress_after_set_edit(conn, user_id, workout_id, workout_set.exercise_id)

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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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

    if workout["status"] not in ("in_progress", "completed"):
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

    refresh_progress_after_set_edit(conn, user_id, workout_id, existing_set["exercise_id"])

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
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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

    if workout["status"] not in ("in_progress", "completed"):
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

    refresh_progress_after_set_edit(conn, user_id, workout_id, existing_set["exercise_id"])

    conn.commit()

    conn.close()

    return {
        "id": set_id,
        "workout_log_id": workout_id,
        "deleted": True,
    }


@app.get("/api/routines/{routine_id}/recommendations")
def get_routine_recommendations(
    routine_id: str,
    user_id: str,
    workout_id: str | None = None,
    current_user = Depends(get_authenticated_user),
):
    """Objetivo siguiente de cada hueco de la rutina.

    Fase 7: con ``workout_id`` los huecos sustituidos en ese entreno devuelven el objetivo del
    EJERCICIO SUSTITUTO (su carga e historial, con el rango de series/reps del hueco).
    """
    user_id = resolve_target_user(current_user, user_id)
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

    substitutes = {}
    if workout_id:
        workout_row = conn.execute(
            "SELECT id FROM workout_logs WHERE id = ? AND user_id = ?", (workout_id, user_id)
        ).fetchone()
        if workout_row is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Entrenamiento no encontrado")
        substitutes = {
            r["original_exercise_id"]: r["substitute_exercise_id"]
            for r in conn.execute(
                "SELECT original_exercise_id, substitute_exercise_id FROM workout_exercise_substitutions "
                "WHERE workout_log_id = ?",
                (workout_id,),
            )
        }

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
        effective_id = substitutes.get(exercise["exercise_id"], exercise["exercise_id"])
        effective = conn.execute(
            f"SELECT {EXERCISE_REC_COLUMNS} FROM exercises e WHERE e.id = ?", (effective_id,)
        ).fetchone() or conn.execute(
            f"SELECT {EXERCISE_REC_COLUMNS} FROM exercises e WHERE e.id = ?", (exercise["exercise_id"],)
        ).fetchone()
        # Fase 6: la misma doble progresión que apply_progression (app/progression.py)
        item = recommendation_item(
            conn, user_id, routine_id, workout_id,
            {"order": exercise["order"], "target_sets": exercise["target_sets"],
             "target_rep_min": exercise["target_rep_min"], "target_rep_max": exercise["target_rep_max"],
             "target_rir": exercise["target_rir"]},
            effective,
        )
        if effective["id"] != exercise["exercise_id"]:
            item["original_exercise_id"] = exercise["exercise_id"]
            item["substituted"] = True
        recommendations.append(item)

    conn.close()

    return {
        "routine_id": routine["id"],
        "routine_name": routine["name"],
        "user_id": routine["user_id"],
        "recommendations": recommendations,
    }


@app.get("/api/workouts/{workout_id}")
def get_workout(
    workout_id: str,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)
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
            wl.current_exercise_id,
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

    # Si se intenta recuperar una sesión en curso demasiado antigua,
    # la marcamos como expired. El historial y las series se conservan.
    if (
        workout["status"] == "in_progress"
        and workout_is_expired(workout["date"])
    ):
        conn.execute(
            """
            UPDATE workout_logs
            SET status = 'expired'
            WHERE id = ?
              AND user_id = ?
              AND status = 'in_progress'
            """,
            (workout_id, user_id),
        )
        conn.commit()

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
            WHERE wl.id = ?
              AND wl.user_id = ?
            """,
            (workout_id, user_id),
        ).fetchone()

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

    # Ejercicios extra y sustituciones de la sesión: sin esto, al recargar o
    # salir y continuar la lista se reconstruía solo desde la rutina.
    extra_exercises = load_extra_exercises(conn, workout_id)
    substitutions = enrich_substitutions(
        conn, user_id, workout_id, load_substitutions(conn, workout_id)
    )

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
        "current_exercise_id": workout["current_exercise_id"],
        "sets": result_sets,
        "extra_exercises": extra_exercises,
        "substitutions": substitutions,
    }

@app.put("/api/workouts/{workout_id}")
def update_workout(
    workout_id: str,
    workout: WorkoutUpdate,
    user_id: str,
    current_user = Depends(get_authenticated_user),
):
    user_id = resolve_target_user(current_user, user_id)

    if workout.status not in {
        "in_progress",
        "completed",
        "cancelled",
        "expired",
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

    # Los entrenamientos finalizados, cancelados o caducados son inmutables.
    if current_status in {"completed", "cancelled", "expired"}:
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
            notes = ?,
            current_exercise_id = ?
        WHERE id = ?
          AND user_id = ?
        """,
        (
            workout.status,
            workout.duration_minutes,
            workout.notes,
            workout.current_exercise_id,
            workout_id,
            user_id,
        ),
    )

    if workout.status == "completed":
        if getattr(workout, "is_deload", 0):
            try:
                conn.execute("UPDATE workout_logs SET is_deload=1 WHERE id=?", (workout_id,))
            except Exception:
                pass
        apply_progression(conn, user_id, workout_id)
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
            status,
            current_exercise_id
        FROM workout_logs
        WHERE id = ?
          AND user_id = ?
        """,
        (workout_id, user_id),
    ).fetchone()

    conn.close()

    return dict(row)




class ExerciseDraftIn(BaseModel):
    name: str

class ExerciseCreateIn(BaseModel):
    name: str
    target_muscle: str = ""
    category: str = "otro"
    equipment: str = ""
    instructions: str = ""
    safety_notes: str = ""
    contraindications: str = ""
    steps: list[str] = []
    technical_cues: list[str] = []
    common_mistakes: list[str] = []
    weight_increment_kg: float | None = None  # None: se deduce del equipo (Fase 6)
    measure_type: str | None = None  # reps | time | bodyweight; None: se deduce del nombre/equipo


@app.post("/api/exercises/draft")
def draft_new_exercise(body: ExerciseDraftIn, current_user=Depends(get_authenticated_user)):
    from .exercise_draft import draft_exercise
    name = body.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Escribe el nombre del ejercicio")
    return draft_exercise(name)


@app.post("/api/exercises")
def create_exercise(body: ExerciseCreateIn, current_user=Depends(get_authenticated_user)):
    name = body.name.strip()
    if len(name) < 2:
        raise HTTPException(status_code=400, detail="Nombre demasiado corto")
    conn = get_connection()
    existing = conn.execute("SELECT id FROM exercises WHERE lower(name)=lower(?)", (name,)).fetchone()
    if existing:
        conn.close()
        raise HTTPException(status_code=409, detail="Ese ejercicio ya existe")
    eid = str(uuid.uuid4())
    measure_type = body.measure_type if body.measure_type in MEASURE_TYPES else infer_measure_type(name, body.equipment)
    increment = (
        body.weight_increment_kg
        if body.weight_increment_kg is not None
        else default_increment(body.equipment, None, measure_type)
    )
    conn.execute(
        """INSERT INTO exercises (
            id, name, target_muscle, category, equipment, safety_notes, is_active,
            instructions, contraindications, steps, technical_cues, common_mistakes,
            weight_increment_kg, progression_type, rep_progression_enabled
        ) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, 'reps_then_weight', 1)""",
        (
            eid, name, body.target_muscle, body.category, body.equipment, body.safety_notes,
            body.instructions, body.contraindications,
            json.dumps(body.steps, ensure_ascii=False),
            json.dumps(body.technical_cues, ensure_ascii=False),
            json.dumps(body.common_mistakes, ensure_ascii=False),
            increment,
        ),
    )
    try:
        conn.execute("UPDATE exercises SET measure_type = ? WHERE id = ?", (measure_type, eid))
    except Exception:
        pass  # la columna la crea el arranque (ensure_progression_schema)
    try:
        # Fase 7: ejercicio propio, con dueño.
        conn.execute("UPDATE exercises SET created_by = ?, is_custom = 1 WHERE id = ?", (current_user["id"], eid))
    except Exception:
        pass  # columnas creadas en el arranque (ensure_crud_schema)
    conn.commit()
    conn.close()
    return {"id": eid, "name": name, "measure_type": measure_type, "weight_increment_kg": increment}
