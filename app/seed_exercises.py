import uuid

from database import get_connection


EXERCISES = [
    {
        "name": "Press banca plano",
        "target_muscle": "Pectoral",
        "category": "empuje",
        "equipment": "Barra",
        "safety_notes": "Mantener escápulas estables y evitar rebotes.",
        "instructions": "Tumbado en banco, pies firmes en el suelo. Descender la barra de forma controlada hasta el pecho y empujar manteniendo una trayectoria estable.",
        "contraindications": "Evitar posiciones que provoquen dolor o inestabilidad en el hombro. No forzar amplitud excesiva.",
    },
    {
        "name": "Remo con pecho apoyado",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "Máquina o banco",
        "safety_notes": "Priorizar control escapular y evitar tirones.",
        "instructions": "Con el pecho apoyado, tirar de los agarres hacia el torso manteniendo el movimiento controlado.",
        "contraindications": "Evitar compensaciones con cuello y hombros. Reducir carga si aparece molestia en el hombro.",
    },
    {
        "name": "Prensa de piernas",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "pierna",
        "equipment": "Máquina",
        "safety_notes": "Controlar la profundidad y mantener pelvis estable.",
        "instructions": "Colocar los pies firmes en la plataforma. Descender de forma controlada hasta un rango cómodo y volver extendiendo las piernas sin bloquear agresivamente las rodillas.",
        "contraindications": "No buscar profundidad que provoque molestia en cadera o pérdida de posición pélvica.",
    },
    {
        "name": "Curl femoral",
        "target_muscle": "Isquiosurales",
        "category": "pierna",
        "equipment": "Máquina",
        "safety_notes": "Movimiento controlado y sin impulso.",
        "instructions": "Flexionar las rodillas llevando los talones hacia los glúteos y regresar lentamente a la posición inicial.",
        "contraindications": "Reducir rango o carga ante tensión excesiva en la zona distal de los isquios.",
    },
    {
        "name": "Elevaciones laterales en máquina",
        "target_muscle": "Deltoides lateral",
        "category": "hombro",
        "equipment": "Máquina",
        "safety_notes": "Carga moderada y cuello relajado.",
        "instructions": "Elevar los brazos lateralmente de forma controlada, manteniendo el cuello relajado y evitando encoger los hombros.",
        "contraindications": "Si aparece tensión marcada en trapecio/cuello, reducir carga o amplitud.",
    },
    {
        "name": "Curl de bíceps en máquina",
        "target_muscle": "Bíceps",
        "category": "brazos",
        "equipment": "Máquina",
        "safety_notes": "Evitar balanceos y mantener tensión continua.",
        "instructions": "Flexionar los codos llevando las manos hacia el cuerpo y volver lentamente.",
        "contraindications": "Evitar dolor en codo o hombro.",
    },
    {
        "name": "Extensión de tríceps en polea",
        "target_muscle": "Tríceps",
        "category": "brazos",
        "equipment": "Polea",
        "safety_notes": "Mantener los codos estables.",
        "instructions": "Con los codos próximos al cuerpo, extender los antebrazos hacia abajo y regresar de forma controlada.",
        "contraindications": "Evitar movimientos que generen dolor en hombro o codo.",
    },
    {
        "name": "Press de hombro con mancuernas agarre neutro",
        "target_muscle": "Deltoides",
        "category": "empuje",
        "equipment": "Mancuernas",
        "safety_notes": "Agarre neutro y recorrido cómodo.",
        "instructions": "Partir con las mancuernas a la altura de los hombros y empujar verticalmente manteniendo las palmas enfrentadas.",
        "contraindications": "No forzar el rango si provoca molestias en el hombro.",
    },
    {
        "name": "Jalón al pecho agarre neutro",
        "target_muscle": "Dorsal",
        "category": "tirón",
        "equipment": "Polea",
        "safety_notes": "Evitar tirar detrás de la cabeza.",
        "instructions": "Tirar del agarre hacia la parte superior del pecho manteniendo el torso estable.",
        "contraindications": "Evitar posiciones dolorosas del hombro o compensaciones con el tronco.",
    },
    {
        "name": "Hip thrust",
        "target_muscle": "Glúteos",
        "category": "pierna",
        "equipment": "Barra o máquina",
        "safety_notes": "Controlar la posición de la pelvis.",
        "instructions": "Apoyar la espalda alta, colocar la carga sobre la pelvis y extender la cadera hasta una posición neutra controlada.",
        "contraindications": "Evitar hiperextender la zona lumbar o realizar el movimiento con dolor de cadera.",
    },
    {
        "name": "Face pull",
        "target_muscle": "Deltoides posterior y espalda alta",
        "category": "hombro",
        "equipment": "Polea",
        "safety_notes": "Carga moderada y control escapular.",
        "instructions": "Tirar de la cuerda hacia la cara separando las manos al final del movimiento.",
        "contraindications": "Reducir carga si genera molestias en el hombro o tensión excesiva en cuello.",
    },
    {
        "name": "Press inclinado con mancuernas 30 grados",
        "target_muscle": "Pectoral superior",
        "category": "empuje",
        "equipment": "Mancuernas",
        "safety_notes": "Mantener recorrido cómodo y estable.",
        "instructions": "Con el banco a unos 30 grados, bajar las mancuernas de forma controlada y empujar hacia arriba manteniendo estabilidad.",
        "contraindications": "Evitar profundidad o posiciones que molesten al hombro.",
    },
    {
        "name": "Sentadilla búlgara",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "unilateral",
        "equipment": "Mancuernas o peso corporal",
        "safety_notes": "Controlar equilibrio y profundidad.",
        "instructions": "Colocar el empeine de una pierna atrás y realizar una flexión controlada de la pierna delantera.",
        "contraindications": "No buscar profundidad que provoque dolor o restricción en la cadera.",
    },
    {
        "name": "Zancadas",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "unilateral",
        "equipment": "Mancuernas o peso corporal",
        "safety_notes": "Paso estable y controlado.",
        "instructions": "Dar un paso hacia delante y descender manteniendo el control de rodilla y cadera antes de volver a la posición inicial.",
        "contraindications": "Reducir longitud de zancada o sustituir si aparece molestia de cadera.",
    },
    {
        "name": "Remo unilateral con mancuerna",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "Mancuerna",
        "safety_notes": "Evitar rotaciones excesivas del tronco.",
        "instructions": "Con apoyo estable, llevar la mancuerna hacia la cadera manteniendo el torso controlado.",
        "contraindications": "Evitar movimientos que provoquen molestia en hombro o espalda.",
    },
    {
        "name": "Plancha",
        "target_muscle": "Core",
        "category": "core",
        "equipment": "Peso corporal",
        "safety_notes": "Mantener pelvis y columna neutras.",
        "instructions": "Apoyar antebrazos y pies, mantener el cuerpo alineado y realizar una respiración controlada.",
        "contraindications": "Finalizar la serie cuando se pierda la posición neutra o aparezca dolor.",
    },
]


def seed_exercises() -> None:
    conn = get_connection()

    inserted = 0

    for exercise in EXERCISES:
        existing = conn.execute(
            "SELECT id FROM exercises WHERE name = ?",
            (exercise["name"],),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO exercises (
                    id,
                    name,
                    target_muscle,
                    category,
                    equipment,
                    safety_notes,
                    is_active,
                    instructions,
                    contraindications
                )
                VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    exercise["name"],
                    exercise["target_muscle"],
                    exercise["category"],
                    exercise["equipment"],
                    exercise["safety_notes"],
                    exercise["instructions"],
                    exercise["contraindications"],
                ),
            )
            inserted += 1

    conn.commit()

    total = conn.execute(
        "SELECT COUNT(*) AS total FROM exercises"
    ).fetchone()["total"]

    print(f"Ejercicios nuevos: {inserted}")
    print(f"Total de ejercicios: {total}")

    print("\nCatálogo:")
    rows = conn.execute(
        """
        SELECT id, name, target_muscle, category, equipment
        FROM exercises
        ORDER BY name
        """
    ).fetchall()

    for row in rows:
        print(
            f"  {row['id']} | "
            f"{row['name']} | "
            f"{row['target_muscle']} | "
            f"{row['category']} | "
            f"{row['equipment']}"
        )

    conn.close()


if __name__ == "__main__":
    seed_exercises()
