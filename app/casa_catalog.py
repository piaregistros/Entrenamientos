"""Catálogo de casa (Fase 12): ejercicios nuevos, material y rutinas Casa A/B/C.

Los ejercicios se identifican por NOMBRE normalizado, nunca por id. Si un
ejercicio ya existe en el catálogo del gimnasio (mismo nombre), no se vuelve
a insertar: se reutiliza.
"""
from __future__ import annotations

# Pesos fijos de las kettlebells de Pablo (kg). Editable en Perfil.
DEFAULT_KETTLEBELL_WEIGHTS = [8, 10, 12, 16, 20, 24, 28, 32]
# Mancuernas de discos: placa más pequeña 1,25 kg por lado → +2,5 kg por mancuerna.
DEFAULT_DUMBBELL_INCREMENT_KG = 2.5

PABLO_ID = "1effca7d-97cf-41f2-a930-9ce482972f02"
# Nombres de usuario a los que se siembran las rutinas Casa A/B/C (si existen).
TARGET_USER_NAMES = ("pablo", "pablobot")
TARGET_USER_IDS = (PABLO_ID,)

# Material de casa: checkboxes en Perfil → Material de casa.
HOME_EQUIPMENT_ITEMS = [
    {"key": "jaula", "label": "Jaula / rack", "default": True},
    {"key": "barra", "label": "Barra olímpica", "default": True},
    {"key": "banco", "label": "Banco ajustable (plano/inclinado/declinado)", "default": True},
    {"key": "landmine", "label": "Landmine", "default": True},
    {"key": "trap_bar", "label": "Trap bar / bear bar", "default": True},
    {"key": "dominadas", "label": "Estación de dominadas (varios agarres)", "default": True},
    {"key": "paralelas", "label": "Barras de fondos (dips)", "default": True},
    {"key": "discos", "label": "Discos (más de 150 kg, incluye 1,25 kg)", "default": True},
    {"key": "mancuernas", "label": "Mancuernas de discos", "default": True},
    {"key": "kettlebells", "label": "Kettlebells", "default": True},
    {"key": "cajon", "label": "Cajón pliométrico", "default": True},
    {"key": "cuerda", "label": "Cuerda de combate", "default": True},
    {"key": "remo", "label": "Máquina de remo", "default": True},
    {"key": "eliptica", "label": "Elíptica", "default": True},
    {"key": "trx", "label": "TRX / cintas de suspensión", "default": True},
    {"key": "gomas", "label": "Gomas elásticas", "default": True},
    {"key": "foam_roller", "label": "Rodillo de masaje", "default": True},
    {"key": "straps", "label": "Straps de agarre", "default": True},
]

HOME_EQUIPMENT_KEYS = [i["key"] for i in HOME_EQUIPMENT_ITEMS]

# Ejercicios que no existen aún en el catálogo del gimnasio.
# measure_type / weight_increment_kg se aplican al insertar (idempotente: no se pisan si ya hay valor).
CASA_EXERCISES = [
    {
        "id": "baeafae7-622d-512a-bfe9-e392ae41df54",
        "name": "Press landmine",
        "target_muscle": "Deltoides y pectoral superior",
        "category": "empuje",
        "equipment": "Landmine",
        "movement_pattern": "empuje_vertical",
        "secondary_muscles": "tríceps,pectoral superior,core",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "unilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "ef07f6ea-93d0-58ad-bd22-1a710754d236",
        "name": "Remo landmine (Meadows)",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "Landmine",
        "movement_pattern": "traccion_horizontal",
        "secondary_muscles": "bíceps,deltoides posterior,core",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "unilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "52adf0c1-ba3a-54ee-9a9c-fe07f228cee1",
        "name": "Sentadilla landmine",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "pierna",
        "equipment": "Landmine",
        "movement_pattern": "sentadilla",
        "secondary_muscles": "isquiosurales,core,aductores",
        "exercise_type": "compuesto",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "fea4d7f4-dd43-597f-b357-a543ff1aa86a",
        "name": "Peso muerto con trap bar",
        "target_muscle": "Cuádriceps, glúteos e isquiosurales",
        "category": "pierna",
        "equipment": "Trap bar",
        "movement_pattern": "bisagra_cadera",
        "secondary_muscles": "erectores espinales,trapecio,antebrazos",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "b8e29def-5522-595c-bdca-af70905d30e5",
        "name": "Press inclinado con barra",
        "target_muscle": "Pectoral superior",
        "category": "empuje",
        "equipment": "Barra",
        "movement_pattern": "empuje_horizontal",
        "secondary_muscles": "tríceps,deltoides anterior",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "bbf5af4c-9e02-58f9-a97d-cfed7792a13e",
        "name": "Dominadas",
        "target_muscle": "Dorsal",
        "category": "tirón",
        "equipment": "Peso corporal",
        "movement_pattern": "traccion_vertical",
        "secondary_muscles": "bíceps,deltoides posterior,core",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "804e7abf-db30-53a3-8acf-a70355fd7c33",
        "name": "Dominadas agarre neutro",
        "target_muscle": "Dorsal",
        "category": "tirón",
        "equipment": "Peso corporal",
        "movement_pattern": "traccion_vertical",
        "secondary_muscles": "bíceps,deltoides posterior,core",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "979a9b7a-465f-5c9a-9e39-eec23ff41bc7",
        "name": "Fondos en paralelas",
        "target_muscle": "Pectoral y tríceps",
        "category": "empuje",
        "equipment": "Peso corporal",
        "movement_pattern": "empuje_horizontal",
        "secondary_muscles": "tríceps,deltoides anterior,pectoral",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "fa20e720-3f2a-5dae-aa05-9756ef138a3e",
        "name": "Remo invertido en TRX",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "TRX",
        "movement_pattern": "traccion_horizontal",
        "secondary_muscles": "bíceps,deltoides posterior,core",
        "exercise_type": "compuesto",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 0,
    },
    {
        "id": "93142441-58d4-5dca-ab30-f19503195f80",
        "name": "Swing con kettlebell",
        "target_muscle": "Glúteos e isquiosurales",
        "category": "pierna",
        "equipment": "Kettlebell",
        "movement_pattern": "bisagra_cadera",
        "secondary_muscles": "erectores espinales,core,deltoides",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 4.0,
    },
    {
        "id": "e106e44b-5b93-503c-b1a0-dc299ce6ab71",
        "name": "Sentadilla goblet con kettlebell",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "pierna",
        "equipment": "Kettlebell",
        "movement_pattern": "sentadilla",
        "secondary_muscles": "isquiosurales,core,aductores",
        "exercise_type": "compuesto",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 4.0,
    },
    {
        "id": "5356652b-77ff-5def-b5c6-ed18b168b8a9",
        "name": "Press de hombro con kettlebell",
        "target_muscle": "Deltoides",
        "category": "empuje",
        "equipment": "Kettlebell",
        "movement_pattern": "empuje_vertical",
        "secondary_muscles": "tríceps,core,deltoides lateral",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "unilateral",
        "measure_type": "reps",
        "weight_increment_kg": 4.0,
    },
    {
        "id": "eb34ee7c-e46e-5235-925c-8c5afda83ff7",
        "name": "Extensión de tríceps en TRX",
        "target_muscle": "Tríceps",
        "category": "brazos",
        "equipment": "TRX",
        "movement_pattern": "extension_codo",
        "secondary_muscles": "core,deltoides anterior",
        "exercise_type": "aislamiento",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 0,
    },
    {
        "id": "221fb65c-d00d-5096-a276-8f07834c3c0c",
        "name": "Extensión de tríceps con goma",
        "target_muscle": "Tríceps",
        "category": "brazos",
        "equipment": "Goma",
        "movement_pattern": "extension_codo",
        "secondary_muscles": "ancóneo",
        "exercise_type": "aislamiento",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 0,
    },
    {
        "id": "2bb8dd85-db95-5a27-8272-f46e6c243c04",
        "name": "Face pull con goma",
        "target_muscle": "Deltoides posterior y espalda alta",
        "category": "hombro",
        "equipment": "Goma",
        "movement_pattern": "traccion_horizontal",
        "secondary_muscles": "deltoides posterior,trapecio,romboides",
        "exercise_type": "aislamiento",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 0,
    },
    {
        "id": "ff06147d-e31e-55dc-b75e-2c4e311a6134",
        "name": "Salto al cajón",
        "target_muscle": "Cuádriceps y glúteos",
        "category": "pierna",
        "equipment": "Cajón pliométrico",
        "movement_pattern": "sentadilla",
        "secondary_muscles": "gemelos,isquiosurales,core",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 0,
    },
    {
        "id": "9ceb3a66-0263-5d91-8c94-2069f6884d3e",
        "name": "Cuerda de combate",
        "target_muscle": "Hombro y core",
        "category": "core",
        "equipment": "Cuerda de combate",
        "movement_pattern": "anti_rotacion",
        "secondary_muscles": "deltoides,antebrazos,core",
        "exercise_type": "core",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "time",
        "weight_increment_kg": 0,
    },
    {
        "id": "d81daf71-9875-5b8c-9415-5ca94dfb59fa",
        "name": "Remo ergómetro",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "Remo ergómetro",
        "movement_pattern": "traccion_horizontal",
        "secondary_muscles": "cuádriceps,glúteos,isquiosurales,bíceps",
        "exercise_type": "compuesto",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "time",
        "weight_increment_kg": 0,
    },
    {
        "id": "926e8658-0c2b-5247-aba1-0c1d04659b1d",
        "name": "Paseo del granjero con kettlebells",
        "target_muscle": "Core y antebrazos",
        "category": "core",
        "equipment": "Kettlebell",
        "movement_pattern": "anti_rotacion",
        "secondary_muscles": "trapecio,glúteos,antebrazos,core",
        "exercise_type": "compuesto",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "time",
        "weight_increment_kg": 4.0,
    },
    {
        "id": "d33d2c9f-a255-5118-8e8e-36808953fe73",
        "name": "Elevación de piernas colgado",
        "target_muscle": "Recto abdominal",
        "category": "core",
        "equipment": "Peso corporal",
        "movement_pattern": "flexion_cadera",
        "secondary_muscles": "flexores de cadera,oblicuos",
        "exercise_type": "core",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "bodyweight",
        "weight_increment_kg": 0,
    },
    {
        "id": "3f71e17a-f768-5521-a277-d42f3e2baedc",
        "name": "Elevación de gemelos en jaula",
        "target_muscle": "Gemelos",
        "category": "pierna",
        "equipment": "Barra",
        "movement_pattern": "flexion_plantar",
        "secondary_muscles": "sóleo",
        "exercise_type": "aislamiento",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "cdc80a7a-025c-5930-a697-109b3cdeedc8",
        "name": "Remo con barra",
        "target_muscle": "Dorsal y espalda media",
        "category": "tirón",
        "equipment": "Barra",
        "movement_pattern": "traccion_horizontal",
        "secondary_muscles": "bíceps,deltoides posterior,erectores espinales",
        "exercise_type": "compuesto",
        "difficulty": "intermedio",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 2.5,
    },
    {
        "id": "c264e57f-b7d9-50a0-b6a9-fac9926fd402",
        "name": "Pallof press con goma",
        "target_muscle": "Core",
        "category": "core",
        "equipment": "Goma",
        "movement_pattern": "anti_rotacion",
        "secondary_muscles": "oblicuos",
        "exercise_type": "core",
        "difficulty": "principiante",
        "laterality": "bilateral",
        "measure_type": "reps",
        "weight_increment_kg": 0,
    },
]


def merge_casa_exercises(exercises: list[dict]) -> list[dict]:
    """Añade los de casa que no estén ya (por nombre). No modifica los existentes."""
    from unicodedata import normalize, category as cat

    def norm(v):
        t = normalize("NFD", str(v or ""))
        t = "".join(c for c in t if cat(c) != "Mn")
        return " ".join(t.lower().split())

    have = {norm(e["name"]) for e in exercises}
    out = list(exercises)
    for ex in CASA_EXERCISES:
        if norm(ex["name"]) not in have:
            out.append(ex)
            have.add(norm(ex["name"]))
    return out


# Fase 12c: las rutinas de casa son ESPEJO de las del gimnasio. Casa A sustituye a A, Casa B a B y
# Casa C a C: mismo orden de patrones de movimiento y de grupos musculares, mismas series y rangos de
# repeticiones que la rutina del gimnasio (referencia: app/seed_pablo_routines.py; la base de datos
# real de Pablo puede haberse editado desde «Gestionar rutinas»).
# Siempre que hay material se usa el MISMO ejercicio que en el gimnasio (así la progresión y el
# historial se heredan solos); si no, el equivalente casero y un enlace en CASA_GYM_LINKS.
# Se reaplican si sube CASA_ROUTINES_VERSION (ver casa.py); si no, no se tocan las ediciones del usuario.
CASA_ROUTINES_VERSION = 2

# (nombre, orden, series, rep_min, rep_max, rir, descanso_s, is_optional)
CASA_ROUTINES = {
    "Casa A": {
        "day_order": 11,
        "gym_slot": "A",
        "session_label": "Equivale a A",
        "location": "casa",
        "exercises": [
            ("Sentadilla libre", 1, 3, 8, 10, 2, 150, 0),                      # Prensa de piernas
            ("Press banca plano", 2, 3, 6, 8, 2, 150, 0),                      # = gimnasio
            ("Remo con barra", 3, 3, 8, 10, 2, 120, 0),                        # Remo con pecho apoyado
            ("Peso muerto rumano", 4, 2, 10, 12, 2, 90, 0),                     # Curl femoral
            ("Elevaciones laterales con mancuernas", 5, 3, 12, 15, 2, 75, 0),  # Elevaciones laterales en máquina
            ("Curl con mancuernas", 6, 2, 10, 12, 2, 75, 0),                   # Curl de bíceps en máquina
            ("Extensión de tríceps con goma", 7, 2, 10, 12, 2, 75, 0),         # Extensión de tríceps en polea
        ],
    },
    "Casa B": {
        "day_order": 12,
        "gym_slot": "B",
        "session_label": "Equivale a B",
        "location": "casa",
        "exercises": [
            ("Press de hombro con mancuernas agarre neutro", 1, 3, 8, 10, 2, 120, 0),  # = gimnasio
            ("Sentadilla landmine", 2, 3, 8, 10, 2, 150, 0),                           # Prensa de piernas
            ("Dominadas agarre neutro", 3, 3, 6, 10, 2, 120, 0),                       # Jalón al pecho agarre neutro
            ("Hip thrust", 4, 3, 8, 10, 2, 120, 0),                                    # = gimnasio (barra y banco)
            ("Face pull con goma", 5, 3, 12, 15, 2, 75, 0),                            # Face pull
            ("Elevaciones laterales con mancuernas", 6, 2, 12, 15, 2, 75, 0),          # Elevaciones laterales en máquina
            ("Plancha", 7, 2, 30, 60, 2, 60, 0),                                       # = gimnasio
        ],
    },
    "Casa C": {
        "day_order": 13,
        "gym_slot": "C",
        "session_label": "Equivale a C",
        "location": "casa",
        "exercises": [
            ("Press inclinado con mancuernas 30 grados", 1, 3, 8, 10, 2, 120, 0),  # = gimnasio (banco ajustable)
            ("Sentadilla búlgara", 2, 3, 8, 10, 2, 120, 0),                        # = gimnasio
            ("Remo unilateral con mancuerna", 3, 3, 10, 12, 2, 90, 0),             # = gimnasio
            ("Peso muerto rumano con mancuernas", 4, 2, 10, 12, 2, 90, 0),         # Curl femoral
            ("Elevaciones laterales con mancuernas", 5, 3, 12, 15, 2, 75, 0),      # Elevaciones laterales en máquina
            ("Curl con mancuernas", 6, 2, 10, 12, 2, 75, 0),                       # Curl de bíceps en máquina
            ("Extensión de tríceps en TRX", 7, 2, 10, 12, 2, 75, 0),               # Extensión de tríceps en polea
        ],
    },
}

# Ejercicio de casa -> (ejercicio del gimnasio al que sustituye, factor).
# Sirve para el PUNTO DE PARTIDA cuando aún no hay historial del ejercicio de casa pero sí del de
# gimnasio: peso orientativo = factor × última carga de trabajo del gimnasio, redondeado hacia abajo
# al incremento. Solo donde la carga es comparable; sin factor (None) solo se enlaza.
CASA_GYM_LINKS = {
    "Sentadilla libre": ("Prensa de piernas", 0.4),
    "Sentadilla landmine": ("Prensa de piernas", 0.2),
    "Remo con barra": ("Remo con pecho apoyado", 0.8),
    "Peso muerto rumano": ("Curl femoral", 1.0),
    "Peso muerto rumano con mancuernas": ("Curl femoral", 0.5),
    "Elevaciones laterales con mancuernas": ("Elevaciones laterales en máquina", 0.4),
    "Curl con mancuernas": ("Curl de bíceps en máquina", 0.4),
    "Dominadas agarre neutro": ("Jalón al pecho agarre neutro", None),
    "Face pull con goma": ("Face pull", None),
    "Extensión de tríceps con goma": ("Extensión de tríceps en polea", None),
    "Extensión de tríceps en TRX": ("Extensión de tríceps en polea", None),
}

# Parejas curadas casa ↔ gimnasio / casa ↔ casa. (a, b, score, motivo)
CASA_CURATED_PAIRS = [
    ("Press banca plano", "Press landmine", 78, "Empuje de pecho y hombro; barra plana por landmine (trayectoria diagonal, más amable con el hombro)."),
    ("Press inclinado con mancuernas 30 grados", "Press inclinado con barra", 92, "Mismo ángulo y músculo (pectoral superior); mancuernas por barra."),
    ("Press inclinado en máquina", "Press inclinado con barra", 90, "Mismo ángulo y músculo; máquina por barra en banco ajustable."),
    ("Press de hombros en máquina", "Press de hombro con kettlebell", 88, "Mismo empuje vertical; máquina por kettlebell (un brazo)."),
    ("Press de hombros en máquina", "Press landmine", 90, "Mismo empuje vertical, más amable con el hombro; máquina por landmine."),
    ("Press de hombro con mancuernas agarre neutro", "Press de hombro con kettlebell", 92, "Mismo empuje vertical; mancuernas por kettlebell."),
    ("Press militar con barra", "Press de hombro con kettlebell", 86, "Mismo empuje vertical; barra por kettlebell."),
    ("Press militar con barra", "Press landmine", 88, "Mismo empuje vertical; barra por landmine."),
    ("Jalón al pecho agarre amplio", "Dominadas", 94, "Misma tracción vertical; polea por peso corporal en la estación de dominadas."),
    ("Jalón al pecho agarre neutro", "Dominadas agarre neutro", 96, "Misma tracción vertical con agarre neutro; polea por peso corporal."),
    ("Jalón al pecho agarre amplio", "Dominadas agarre neutro", 88, "Misma tracción vertical; cambia el agarre (amplio por neutro)."),
    ("Jalón al pecho agarre neutro", "Dominadas", 88, "Misma tracción vertical; polea por peso corporal."),
    ("Remo en máquina", "Remo landmine (Meadows)", 90, "Misma tracción horizontal; máquina por landmine (un brazo)."),
    ("Remo en máquina", "Remo con barra", 92, "Misma tracción horizontal; máquina por barra."),
    ("Remo en máquina", "Remo invertido en TRX", 84, "Misma tracción horizontal; máquina por TRX (peso corporal)."),
    ("Remo sentado en polea", "Remo invertido en TRX", 82, "Misma tracción horizontal; polea por TRX."),
    ("Remo sentado en polea", "Remo con barra", 88, "Misma tracción horizontal; polea por barra."),
    ("Remo unilateral con mancuerna", "Remo landmine (Meadows)", 92, "Misma tracción horizontal unilateral; mancuerna por landmine."),
    ("Remo con pecho apoyado", "Remo invertido en TRX", 80, "Misma tracción horizontal; máquina con apoyo por TRX."),
    ("Face pull", "Face pull con goma", 96, "Mismo gesto de deltoides posterior y espalda alta; polea por goma."),
    ("Pájaros en máquina", "Face pull con goma", 88, "Deltoides posterior y espalda alta; máquina por goma."),
    ("Extensión de tríceps en polea", "Extensión de tríceps en TRX", 88, "Misma extensión de codo; polea por TRX."),
    ("Extensión de tríceps en polea", "Extensión de tríceps con goma", 94, "Misma extensión de codo; polea por goma."),
    ("Extensión de tríceps con cuerda", "Extensión de tríceps con goma", 92, "Misma extensión de codo; polea por goma."),
    ("Prensa de piernas", "Peso muerto con trap bar", 78, "Empuje de piernas; máquina por trap bar (más bisagra que la prensa)."),
    ("Prensa de piernas", "Sentadilla landmine", 82, "Mismo patrón de sentadilla; máquina por landmine."),
    ("Sentadilla goblet", "Sentadilla goblet con kettlebell", 96, "Misma sentadilla goblet; mancuerna por kettlebell."),
    ("Sentadilla goblet", "Sentadilla landmine", 86, "Misma sentadilla; mancuerna por landmine."),
    ("Sentadilla libre", "Sentadilla landmine", 88, "Misma sentadilla; barra por landmine (más fácil de aprender)."),
    ("Peso muerto rumano", "Peso muerto con trap bar", 80, "Bisagra de cadera; barra recta por trap bar (más cuádriceps, menos estrés lumbar)."),
    ("Peso muerto rumano con mancuernas", "Peso muerto con trap bar", 76, "Bisagra de cadera; mancuernas por trap bar."),
    ("Pallof press", "Pallof press con goma", 96, "Mismo anti-rotación de core; polea por goma."),
    ("Elevación de gemelos de pie", "Elevación de gemelos en jaula", 94, "Mismo gemelo de pie; máquina por barra en la jaula."),
    ("Elevación de rodillas", "Elevación de piernas colgado", 92, "Recto abdominal colgado; rodillas por piernas estiradas (más exigente)."),
    ("Crunch en máquina", "Elevación de piernas colgado", 74, "Recto abdominal; máquina por peso corporal colgado."),
    ("Hip thrust", "Swing con kettlebell", 62, "Glúteo e isquios con extensión de cadera; barra por kettlebell."),
    ("Fondos en paralelas", "Press banca plano", 70, "Empuje de pecho y tríceps; fondos por barra."),
    ("Dominadas", "Dominadas agarre neutro", 95, "Misma tracción vertical; cambia el agarre (amplio/prono por neutro)."),
    ("Remo invertido en TRX", "Remo con barra", 84, "Misma tracción horizontal; TRX por barra."),
    ("Press de hombro con kettlebell", "Press landmine", 90, "Mismo empuje vertical unilateral; kettlebell por landmine."),
    # Fase 12c: huecos de las rutinas espejo
    ("Remo con pecho apoyado", "Remo con barra", 84, "Misma tracción horizontal; con apoyo de pecho por barra."),
    ("Remo con pecho apoyado", "Remo landmine (Meadows)", 86, "Misma tracción horizontal; apoyo de pecho por landmine."),
    ("Curl femoral", "Peso muerto rumano", 68, "Isquiosurales; curl en máquina por bisagra de cadera con barra."),
    ("Curl femoral", "Peso muerto rumano con mancuernas", 70, "Isquiosurales; curl en máquina por bisagra con mancuernas."),
]
