"""Parejas de sustitución curadas a mano (Fase 7).

Cada tupla es (ejercicio, alternativa, puntuación 0-100, motivo). Todas son
bidireccionales (se insertan A→B y B→A con el mismo motivo adaptado) salvo que
se indique lo contrario. Se enlazan por NOMBRE normalizado, nunca por id.

El foco está en el caso real de Pablo: mancuernas ↔ máquina / polea / barra
cuando el material no está libre en el gimnasio.
"""
from __future__ import annotations

# (a, b, score, motivo)
CURATED_PAIRS: list[tuple[str, str, int, str]] = [
    # ---- PECHO: mancuernas ↔ máquina / barra / polea
    ("Press banca con mancuernas", "Press convergente de pecho", 92, "Mismo empuje horizontal de pecho; cambias mancuernas por máquina guiada."),
    ("Press banca con mancuernas", "Press banca plano", 90, "Mismo patrón y músculo; cambias mancuernas por barra."),
    ("Press banca con mancuernas", "Press inclinado con mancuernas 30 grados", 80, "Mismas mancuernas; cambia el ángulo (más pectoral superior)."),
    ("Press banca con mancuernas", "Press inclinado en máquina", 82, "Empuje de pecho en máquina; algo más de pectoral superior."),
    ("Press banca plano", "Press convergente de pecho", 88, "Empuje horizontal de pecho en máquina guiada si la barra está ocupada."),
    ("Press banca plano", "Press inclinado con mancuernas 30 grados", 80, "Empuje de pecho con mancuernas; cambia el ángulo."),
    ("Press inclinado con mancuernas 30 grados", "Press inclinado en máquina", 94, "Mismo ángulo y músculo (pectoral superior); mancuernas por máquina."),
    ("Press inclinado con mancuernas 30 grados", "Press convergente de pecho", 84, "Empuje de pecho en máquina; menos énfasis superior."),
    ("Press convergente de pecho", "Press inclinado en máquina", 86, "Misma máquina de empuje; cambia el ángulo."),
    ("Aperturas de pecho en máquina", "Cruce de poleas", 94, "Mismo movimiento de aducción de hombro; máquina por poleas."),
    ("Aperturas de pecho en máquina", "Press convergente de pecho", 60, "Trabaja el mismo pectoral con un empuje en vez de apertura."),
    ("Cruce de poleas", "Press convergente de pecho", 60, "Trabaja el mismo pectoral con un empuje en vez de apertura."),
    # ---- HOMBRO
    ("Press de hombro con mancuernas agarre neutro", "Press de hombros en máquina", 94, "Mismo empuje vertical; mancuernas por máquina guiada."),
    ("Press de hombro con mancuernas agarre neutro", "Press militar con barra", 88, "Mismo empuje vertical; mancuernas por barra."),
    ("Press de hombros en máquina", "Press militar con barra", 84, "Mismo empuje vertical; máquina por barra."),
    ("Elevaciones laterales con mancuernas", "Elevaciones laterales en máquina", 95, "Mismo gesto de deltoides lateral; mancuernas por máquina."),
    ("Elevaciones laterales con mancuernas", "Elevaciones laterales en polea", 93, "Mismo gesto con tensión constante; mancuernas por polea."),
    ("Elevaciones laterales en máquina", "Elevaciones laterales en polea", 92, "Mismo gesto de deltoides lateral; máquina por polea."),
    ("Face pull", "Pájaros en máquina", 90, "Deltoides posterior y espalda alta; polea por máquina."),
    ("Pájaros en máquina", "Remo sentado en polea", 55, "Trabaja la espalda alta/deltoides posterior con un remo."),
    # ---- ESPALDA
    ("Remo unilateral con mancuerna", "Remo en máquina", 90, "Misma tracción horizontal; mancuerna por máquina."),
    ("Remo unilateral con mancuerna", "Remo unilateral en polea", 94, "Misma tracción unilateral; mancuerna por polea."),
    ("Remo unilateral con mancuerna", "Remo con pecho apoyado", 88, "Misma tracción horizontal con el pecho apoyado."),
    ("Remo unilateral con mancuerna", "Remo sentado en polea", 86, "Misma tracción horizontal; mancuerna por polea."),
    ("Remo en máquina", "Remo sentado en polea", 92, "Misma tracción horizontal; máquina por polea."),
    ("Remo en máquina", "Remo con pecho apoyado", 92, "Misma tracción horizontal; ambos con apoyo."),
    ("Remo sentado en polea", "Remo unilateral en polea", 90, "Misma polea; bilateral por unilateral."),
    ("Remo con pecho apoyado", "Remo sentado en polea", 86, "Misma tracción horizontal; con o sin apoyo de pecho."),
    ("Jalón al pecho agarre amplio", "Jalón al pecho agarre neutro", 95, "Mismo jalón vertical; cambia el agarre."),
    ("Jalón al pecho agarre amplio", "Jalón unilateral en polea", 88, "Mismo jalón vertical, de un brazo."),
    ("Jalón al pecho agarre neutro", "Jalón unilateral en polea", 90, "Mismo jalón vertical, de un brazo."),
    ("Jalón al pecho agarre neutro", "Pullover en polea", 62, "Dorsal con brazos extendidos; menos bíceps."),
    ("Jalón al pecho agarre neutro", "Remo sentado en polea", 70, "Dorsal con tracción horizontal en vez de vertical."),
    # ---- BRAZOS
    ("Curl con mancuernas", "Curl de bíceps en máquina", 92, "Mismo curl de bíceps; mancuernas por máquina."),
    ("Curl con mancuernas", "Curl de bíceps en polea", 93, "Mismo curl con tensión constante; mancuernas por polea."),
    ("Curl con mancuernas", "Curl inclinado con mancuernas", 90, "Mismas mancuernas; en banco inclinado (más estiramiento)."),
    ("Curl con mancuernas", "Curl martillo", 88, "Mismas mancuernas; agarre neutro (braquial)."),
    ("Curl inclinado con mancuernas", "Curl de bíceps en polea", 88, "Curl de bíceps; mancuernas por polea."),
    ("Curl inclinado con mancuernas", "Curl de bíceps en máquina", 84, "Curl de bíceps; mancuernas por máquina."),
    ("Curl martillo", "Curl de bíceps en polea", 86, "Flexión de codo; mancuernas por polea (con cuerda es casi igual)."),
    ("Curl de bíceps en máquina", "Curl de bíceps en polea", 92, "Mismo curl; máquina por polea."),
    ("Extensión de tríceps en polea", "Extensión de tríceps con cuerda", 96, "Misma extensión de codo; cambia el agarre."),
    ("Extensión de tríceps en polea", "Extensión de tríceps por encima de la cabeza", 88, "Mismo músculo; el brazo por encima de la cabeza estira más el tríceps."),
    ("Extensión de tríceps con cuerda", "Extensión de tríceps por encima de la cabeza", 88, "Mismo músculo y polea; cambia la posición del brazo."),
    ("Press francés", "Extensión de tríceps por encima de la cabeza", 90, "Tríceps con el brazo por encima de la cabeza; barra por polea."),
    ("Press francés", "Extensión de tríceps en polea", 86, "Misma extensión de codo; barra por polea."),
    ("Press francés", "Extensión de tríceps con cuerda", 86, "Misma extensión de codo; barra por polea."),
    # ---- PIERNA
    ("Prensa de piernas", "Hack squat", 92, "Mismo patrón de sentadilla guiada en máquina."),
    ("Prensa de piernas", "Prensa unilateral", 94, "Misma máquina; con una pierna cada vez."),
    ("Prensa de piernas", "Sentadilla búlgara", 80, "Cuádriceps y glúteos con una pierna; mancuernas o peso corporal."),
    ("Prensa de piernas", "Zancadas", 78, "Cuádriceps y glúteos, unilateral."),
    ("Prensa de piernas", "Sentadilla libre", 84, "Mismo patrón; máquina por barra."),
    ("Prensa de piernas", "Sentadilla goblet", 80, "Mismo patrón; máquina por mancuerna."),
    ("Hack squat", "Sentadilla libre", 88, "Mismo patrón de sentadilla; máquina por barra."),
    ("Hack squat", "Sentadilla goblet", 80, "Mismo patrón; máquina por mancuerna."),
    ("Hack squat", "Prensa unilateral", 82, "Cuádriceps y glúteos en máquina, una pierna."),
    ("Sentadilla goblet", "Sentadilla libre", 88, "Misma sentadilla; mancuerna por barra."),
    ("Sentadilla goblet", "Sentadilla búlgara", 82, "Misma sentadilla, unilateral."),
    ("Sentadilla goblet", "Prensa unilateral", 78, "Cuádriceps y glúteos; mancuerna por máquina."),
    ("Sentadilla búlgara", "Prensa unilateral", 90, "Pierna a pierna; mancuernas por máquina."),
    ("Sentadilla búlgara", "Zancadas", 94, "Mismo patrón unilateral."),
    ("Sentadilla búlgara", "Step-up", 88, "Unilateral con mancuernas; menos carga sobre la rodilla."),
    ("Sentadilla búlgara", "Hack squat", 80, "Cuádriceps y glúteos; mancuernas por máquina."),
    ("Zancadas", "Step-up", 92, "Mismo patrón unilateral con mancuernas."),
    ("Zancadas", "Prensa unilateral", 86, "Unilateral; mancuernas por máquina."),
    ("Step-up", "Prensa unilateral", 84, "Unilateral; mancuernas por máquina."),
    ("Step-up", "Extensión de cadera en máquina", 55, "Glúteo con carga guiada en vez de subir al cajón."),
    ("Peso muerto rumano", "Peso muerto rumano con mancuernas", 96, "Misma bisagra de cadera; barra por mancuernas."),
    ("Peso muerto rumano", "Curl femoral tumbado", 70, "Isquiosurales; barra por máquina."),
    ("Peso muerto rumano", "Hip thrust", 72, "Glúteo e isquios con bisagra de cadera; mismo peso libre."),
    ("Peso muerto rumano con mancuernas", "Curl femoral tumbado", 72, "Isquiosurales; mancuernas por máquina."),
    ("Peso muerto rumano con mancuernas", "Curl femoral sentado", 70, "Isquiosurales; mancuernas por máquina."),
    ("Peso muerto rumano con mancuernas", "Hip thrust", 72, "Glúteo e isquios con bisagra de cadera."),
    ("Curl femoral", "Curl femoral sentado", 96, "Mismo curl femoral en otra máquina."),
    ("Curl femoral", "Curl femoral tumbado", 96, "Mismo curl femoral en otra máquina."),
    ("Curl femoral sentado", "Curl femoral tumbado", 95, "Mismo curl femoral; cambia la postura."),
    ("Curl femoral tumbado", "Hip thrust", 62, "Trabaja isquios y glúteo; sin máquina de curl."),
    ("Hip thrust", "Hip thrust unilateral", 94, "Mismo empuje de cadera; una pierna cada vez."),
    ("Hip thrust", "Extensión de cadera en máquina", 86, "Extensión de cadera en máquina."),
    ("Hip thrust", "Patada de glúteo en polea", 78, "Glúteo mayor con polea."),
    ("Hip thrust unilateral", "Extensión de cadera en máquina", 88, "Glúteo mayor, una pierna; banco por máquina."),
    ("Extensión de cadera en máquina", "Patada de glúteo en polea", 90, "Misma extensión de cadera; máquina por polea."),
    ("Abducción de cadera en máquina", "Patada de glúteo en polea", 60, "Glúteo (medio/mayor) con polea si la abductora está ocupada."),
    ("Extensión de cuádriceps", "Sentadilla búlgara", 60, "Cuádriceps con ejercicio compuesto."),
    ("Extensión de cuádriceps", "Hack squat", 62, "Cuádriceps con ejercicio compuesto guiado."),
    ("Extensión de cuádriceps", "Prensa de piernas", 62, "Cuádriceps con ejercicio compuesto guiado."),
    ("Elevación de gemelos de pie", "Elevación de gemelos sentado", 92, "Mismo gemelo; sentado trabaja más el sóleo."),
    ("Elevación de gemelos de pie", "Prensa de piernas", 55, "Gemelos en la prensa (solo punteras) si no hay máquina."),
    # ---- CORE
    ("Crunch en máquina", "Crunch en polea", 94, "Mismo crunch de recto abdominal; máquina por polea."),
    ("Crunch en máquina", "Elevación de rodillas", 74, "Recto abdominal con peso corporal."),
    ("Crunch en polea", "Elevación de rodillas", 74, "Recto abdominal con peso corporal."),
    ("Plancha", "Pallof press", 76, "Core anti-movimiento; plancha por polea."),
    ("Plancha", "Elevación de rodillas", 60, "Core con peso corporal."),
    ("Pallof press", "Crunch en polea", 55, "Core con polea, de anti-rotación a flexión de columna."),
]


try:
    from .casa_catalog import CASA_CURATED_PAIRS
except ImportError:
    from casa_catalog import CASA_CURATED_PAIRS

CURATED_PAIRS = list(CURATED_PAIRS) + list(CASA_CURATED_PAIRS)

