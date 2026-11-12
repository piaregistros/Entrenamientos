"""GET /api/exercises/{id}: ficha completa de un ejercicio (Fase 5)."""
from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_authenticated_user
from app.database import get_connection
from app.exercise_sheets import attach_sheet_fields

router = APIRouter()


@router.get("/api/exercises/{exercise_id}")
def get_exercise_detail(exercise_id: str, current_user=Depends(get_authenticated_user)):
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, name, target_muscle, category, equipment, safety_notes, is_active,
                   created_at, instructions, contraindications, weight_increment_kg,
                   progression_type, rep_progression_enabled
            FROM exercises WHERE id = ?
            """,
            (exercise_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Ejercicio no encontrado")
        return attach_sheet_fields(conn, [dict(row)])[0]
    finally:
        conn.close()
