"""Catálogo de clases dirigidas Enjoy! Murcia (C. Pablo Neruda, 2).
Fuente: listado público del centro + Les Mills que anuncian.
No es el horario de un día concreto; son las actividades que se pueden apuntar.
"""

GYM = {
    "id": "enjoy-murcia",
    "name": "Enjoy! Murcia",
    "address": "C. Pablo Neruda, 2, 30011 Murcia",
}

# category: strength | cardio | cycle | mind | aqua | sport | other
CLASSES = [
    {"id": "bodypump", "name": "BodyPump", "category": "strength", "minutes": 55, "load": ["full_body"], "note": "Les Mills. Barra y discos."},
    {"id": "bodycombat", "name": "BodyCombat", "category": "cardio", "minutes": 55, "load": ["shoulders", "core"], "note": "Les Mills. Golpes, sin contacto."},
    {"id": "bodybalance", "name": "BodyBalance", "category": "mind", "minutes": 55, "load": ["core"], "note": "Les Mills. Yoga, tai chi, pilates."},
    {"id": "bodystep", "name": "BodyStep", "category": "cardio", "minutes": 55, "load": ["legs"], "note": "Les Mills. Step."},
    {"id": "shbam", "name": "SH'Bam", "category": "cardio", "minutes": 45, "load": ["full_body"], "note": "Les Mills. Baile."},
    {"id": "ciclo-indoor", "name": "Ciclo indoor", "category": "cycle", "minutes": 45, "load": ["legs"], "note": "Bici de sala."},
    {"id": "core", "name": "Core", "category": "strength", "minutes": 30, "load": ["core"], "note": "Abdomen y lumbar."},
    {"id": "gap", "name": "G.A.P.", "category": "strength", "minutes": 45, "load": ["glutes", "legs"], "note": "Glúteo, abdomen, pierna."},
    {"id": "hiit", "name": "HIIT", "category": "cardio", "minutes": 30, "load": ["full_body"], "note": "Intervalos de alta intensidad."},
    {"id": "hict", "name": "HICT", "category": "cardio", "minutes": 30, "load": ["full_body"], "note": "Circuito de alta intensidad."},
    {"id": "gritt", "name": "GRITT Series", "category": "cardio", "minutes": 30, "load": ["full_body"], "note": "Les Mills. Alta intensidad."},
    {"id": "funcional-360", "name": "Funcional 360", "category": "strength", "minutes": 45, "load": ["full_body"], "note": "Funcional multiestación."},
    {"id": "wod", "name": "WOD", "category": "strength", "minutes": 40, "load": ["full_body"], "note": "Entrenamiento del día / metcon."},
    {"id": "pilates", "name": "Pilates", "category": "mind", "minutes": 50, "load": ["core"], "note": "Control y movilidad."},
    {"id": "yoga", "name": "Yoga", "category": "mind", "minutes": 55, "load": ["core"], "note": "Cuerpo-mente."},
    {"id": "stretch", "name": "Stretch", "category": "mind", "minutes": 30, "load": [], "note": "Estiramientos."},
    {"id": "espalda-sana", "name": "Espalda sana", "category": "mind", "minutes": 45, "load": ["back"], "note": "Movilidad y higiene postural."},
    {"id": "aquafit", "name": "Aquafit", "category": "aqua", "minutes": 45, "load": ["full_body"], "note": "Piscina. Cardio suave."},
    {"id": "aquagym", "name": "Aquagym", "category": "aqua", "minutes": 45, "load": ["full_body"], "note": "Gimnasia en el agua."},
    {"id": "senior", "name": "Acondicionamiento senior", "category": "other", "minutes": 45, "load": ["full_body"], "note": "Grupo senior."},
    {"id": "nado", "name": "Nado libre", "category": "aqua", "minutes": 40, "load": ["full_body"], "note": "Piscina climatizada 25 m."},
    {"id": "padel", "name": "Pádel", "category": "sport", "minutes": 60, "load": ["legs", "shoulders"], "note": "Pistas del centro."},
    {"id": "otro", "name": "Otra actividad", "category": "other", "minutes": 45, "load": [], "note": "Lo que no encaje arriba."},
]


def class_by_id(class_id: str):
    for item in CLASSES:
        if item["id"] == class_id:
            return item
    return None
