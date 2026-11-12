"""Vídeos de YouTube verificados para los 59 ejercicios del catálogo.

Cada entrada se comprobó el 2026-11-12 con el endpoint oEmbed de YouTube
(https://www.youtube.com/oembed?url=...&format=json -> HTTP 200) y se revisó que el
título corresponde al ejercicio. ``review`` marca los casos con título genérico.
Nunca se inventa una URL: un ejercicio sin vídeo fiable se deja fuera de VIDEOS
y se anota en WITHOUT_VIDEO.
"""

VERIFIED_AT = "2026-11-12"

WITHOUT_VIDEO = []

VIDEOS = {
    'Abducción de cadera en máquina': {'video_id': '2vCRMi-lgJ4', 'title': 'Abducción de cadera en máquina -Técnica correcta📝✅ Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Aperturas de pecho en máquina': {'video_id': 'qeKeh-bywRw', 'title': '🏋️ Máquina de Aperturas para Pectoral Paso a Paso', 'channel': 'Entrenador Personal - Malagaentrena', 'review': None},
    'Cruce de poleas': {'video_id': 'WNtBIde3Qks', 'title': 'Deja de Arruinar El Cruce de Poleas PECHO ¡FORMA CORRECTA!', 'channel': 'ATHLEAN-X Español', 'review': None},
    'Curl de bíceps en máquina': {'video_id': 'gqLp6MFRYgI', 'title': '💪 CURL DE BÍCEPS EN MÁQUINA: técnica perfecta y segura🎯', 'channel': 'Vitar Club', 'review': None},
    'Curl femoral': {'video_id': 'IkX7c-HyFoU', 'title': 'Como 😱 CURL FEMORAL para FEMORAL🍑 - Análisis Biomecánico EN 1 MINUTO 📍', 'channel': 'WeFitPlace', 'review': 'título genérico (análisis biomecánico en 1 minuto)'},
    'Curl femoral sentado': {'video_id': 'CBCPBnMzsMI', 'title': 'Curl Femoral Sentado en Máquina 🏋️\u200d♂️ | Técnica Correcta', 'channel': 'Vitar Club', 'review': None},
    'Curl femoral tumbado': {'video_id': '9xbBr5Ytl8c', 'title': 'Cómo Hacer Curl Femoral Tumbado en Máquina 💪 | Técnica Correcta', 'channel': 'Vitar Club', 'review': None},
    'Elevaciones laterales con mancuernas': {'video_id': 'TP6P8-gojO8', 'title': 'ELEVACIONES LATERALES con mancuernas - Tutorial completo', 'channel': 'Toni Lloret', 'review': None},
    'Elevaciones laterales en máquina': {'video_id': 'NkRQI9rrRN8', 'title': 'Elevaciones Laterales en Máquina -  Hombro Lateral', 'channel': 'Zonapablo', 'review': None},
    'Elevaciones laterales en polea': {'video_id': 'fKxKgslS408', 'title': 'Cómo Hacer Elevaciones Laterales en Polea para Hombros Imponentes', 'channel': 'Andres Vazquez Personal Trainer', 'review': None},
    'Extensión de cuádriceps': {'video_id': 'Q2-N3JmOQvI', 'title': 'Extensión de rodilla en Máquina -Técnica correcta📝✅ Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Extensión de tríceps en polea': {'video_id': 'HAS8uy73HqM', 'title': 'Extensión de Tríceps en Polea - Técnica Perfecta- Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Face pull': {'video_id': 'X-xCQ1gh-kA', 'title': 'Cómo Hacer Face Pull Correctamente 💪 ¡Evita lesiones! con Powerexplosive', 'channel': 'HSNstore.com', 'review': None},
    'Hack squat': {'video_id': 'P5GKCErO54g', 'title': 'Sentadilla Hack', 'channel': 'Fitness Consciente', 'review': None},
    'Hip thrust': {'video_id': 'aMntMBkmv0g', 'title': 'Hip thrust -Técnica correcta📝✅ Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Jalón al pecho agarre amplio': {'video_id': 'WakfOFnr5oM', 'title': 'JALÓN al PECHO con AGARRE AMPLIO 💪 Técnica PERFECTA para ESPALDA ANCHA', 'channel': 'Tandem Fitness', 'review': None},
    'Jalón al pecho agarre neutro': {'video_id': 'VUJYixXx5I8', 'title': 'Jalón al Pecho con Polea Alta Cerrado Agarre Neutro', 'channel': 'Zonapablo', 'review': None},
    'Jalón unilateral en polea': {'video_id': 'qUmBAKXevS4', 'title': '👉 JALÓN UNILATERAL POLEA ALTA 💪 | Técnica Correcta, Errores y Consejos', 'channel': 'Vitar Club', 'review': None},
    'Patada de glúteo en polea': {'video_id': 'EIst_zqP2dg', 'title': 'PATADA DE GLÚTEO - TÉCNICA CORRECTA para AUMENTAR GLÚTEOS', 'channel': 'Galvistrainer', 'review': None},
    'Peso muerto rumano': {'video_id': 'rjvlSfZ-PQw', 'title': 'Cómo Hacer PESO MUERTO RUMANO Perfecto (paso a paso)', 'channel': 'Fit Generation', 'review': None},
    'Peso muerto rumano con mancuernas': {'video_id': 'yxLk9X5C7RU', 'title': 'Peso Muerto Rumano Con Mancuernas - Sin Dolor De Espalda', 'channel': 'DrVíctorLópez', 'review': None},
    'Plancha': {'video_id': 'd0atctiI7Vw', 'title': 'Cómo hacer la 𝗣𝗟𝗔𝗡𝗖𝗛𝗔 𝗣𝗘𝗥𝗙𝗘𝗖𝗧𝗔 por PRIMERA VEZ', 'channel': 'DeportesUncomo', 'review': None},
    'Prensa de piernas': {'video_id': 'hl-EJUQ2yuc', 'title': 'PRENSA PARA PIERNAS - LEG PRESS - Técnica correcta en 3 minutos ✅', 'channel': 'Galvistrainer', 'review': None},
    'Press banca con mancuernas': {'video_id': 'jWnGhz1f5D4', 'title': 'Press de pecho con mancuernas en 2 minutos: la técnica correcta', 'channel': 'Gym Topz', 'review': None},
    'Press banca plano': {'video_id': 'jlFl7WJ1TzI', 'title': 'Cómo hacer press de banca CORRECTAMENTE para incrementar tus músculos (5 pasos sencillos)', 'channel': 'Jeremy Ethier en Español', 'review': None},
    'Press convergente de pecho': {'video_id': 'N7DjfGB8-xY', 'title': 'Press de pecho en máquina', 'channel': 'Fitness Consciente', 'review': 'título genérico (press de pecho en máquina)'},
    'Press de hombro con mancuernas agarre neutro': {'video_id': '7vNw_ZbF99A', 'title': 'PRESS DE HOMBRO "AGARRE NEUTRO" CON MANCUERNAS', 'channel': 'DrVíctorLópez', 'review': None},
    'Press de hombros en máquina': {'video_id': 'A20O8ZMn190', 'title': 'Press de hombros en máquina', 'channel': 'Fitness Consciente', 'review': None},
    'Press inclinado con mancuernas 30 grados': {'video_id': 'MkMf308jXww', 'title': 'MEJORA tu press INCLINADO con MANCUERNAS | GFit Coach', 'channel': 'Guillermo Fernández', 'review': None},
    'Press inclinado en máquina': {'video_id': 'XTfRuAWB_Ho', 'title': 'Press inclinado en máquina: así SÍ crece el pecho alto', 'channel': 'Sergio Tejeda', 'review': None},
    'Press militar con barra': {'video_id': 'xM2FGQuhZAY', 'title': 'Press Militar con Barra de Pie | PowerExplosive', 'channel': 'HSNstore.com', 'review': None},
    'Pullover en polea': {'video_id': '9YQ1YXKko8s', 'title': '✅ PULLOVER con CUERDA en POLEA ALTA | Hazlo BIEN así |', 'channel': 'Manuel Escalera', 'review': None},
    'Pájaros en máquina': {'video_id': 'NTJpVVa6zLo', 'title': 'Cómo hacer PAJAROS en MÁQUINA correctamente ✅', 'channel': 'Vida en Forma', 'review': None},
    'Remo con pecho apoyado': {'video_id': 'LDxVARwqzy4', 'title': 'TECNICA REMO DE PECHO APOYADO', 'channel': 'Gabriel Fischman', 'review': None},
    'Remo en máquina': {'video_id': 'FOusO8JMU3Q', 'title': 'Remo horizontal en máquina', 'channel': 'Fitness Consciente', 'review': None},
    'Remo sentado en polea': {'video_id': 'JtTusrYzAos', 'title': 'Remo sentado en polea: Cómo hacerlo correctamente', 'channel': 'EresFitness', 'review': None},
    'Remo unilateral con mancuerna': {'video_id': 'IKoEsubNp9E', 'title': '¿Cómo hacer REMO MANCUERNA unilateral?', 'channel': 'Powerbeards', 'review': None},
    'Remo unilateral en polea': {'video_id': 'OyzbjhYxciY', 'title': 'Remo unilateral en polea apoyado: así SÍ trabaja la espalda', 'channel': 'Sergio Tejeda', 'review': None},
    'Sentadilla búlgara': {'video_id': 'x_k90ghjPPw', 'title': 'CÓMO HACER UNA SENTADILLA BULGARA (Bulgarian Split Squat) | Ejercicios para aumentar masa muscular', 'channel': 'Maria Baptista Fitness', 'review': None},
    'Sentadilla goblet': {'video_id': 'FoQsAJ1n0Mk', 'title': 'Sentadilla goblet', 'channel': 'Fitness Consciente', 'review': None},
    'Sentadilla libre': {'video_id': 'qsAkuNORgmk', 'title': 'Cómo hacer sentadillas CORRECTAMENTE (4 pasos sencillos)', 'channel': 'Jeremy Ethier en Español', 'review': None},
    'Zancadas': {'video_id': '1O543yIxtIY', 'title': 'CÓMO HACER LA ZANCADA O LUNGE CORRECTAMENTE', 'channel': 'Isabel onmytrainingshoes', 'review': None},
    'Hip thrust unilateral': {'video_id': 'DFIVNdnVrEk', 'title': 'Hip thrust a una pierna', 'channel': 'Fitness Consciente', 'review': None},
    'Prensa unilateral': {'video_id': 'TnqZH4K28WE', 'title': 'Prensa a una Pierna', 'channel': 'Zonapablo', 'review': None},
    'Step-up': {'video_id': 'CpKJ1B4iNwc', 'title': 'STEP UPS - TÉCNICA CORRECTA EXPLICADA- Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Extensión de cadera en máquina': {'video_id': '5gcunI9uI6M', 'title': 'COMO HACER LA EXTENSIÓN DE CADERA EN MÁQUINA', 'channel': 'FHI.ONLINE', 'review': None},
    'Elevación de gemelos de pie': {'video_id': 'R9eS_1An8L0', 'title': 'GEMELO EN MÁQUINA DE PIE', 'channel': 'Miguel Pancorbo Gutiérrez', 'review': 'canal pequeño; título correcto pero poco contrastado'},
    'Elevación de gemelos sentado': {'video_id': '-ClDK8lLPas', 'title': '🦵Elevaciones de TALONES sentado en máquina🔥Técnica correcta para ganar masa muscular', 'channel': 'Vitar Club', 'review': None},
    'Curl con mancuernas': {'video_id': 'qERAhN-qpaU', 'title': 'Haz CRECER tus BRAZOS así | Curl bíceps con mancuernas | GFit Coach', 'channel': 'Guillermo Fernández', 'review': None},
    'Curl inclinado con mancuernas': {'video_id': 'swtxf1aJXaY', 'title': 'Curl de bíceps en banco inclinado con mancuernas', 'channel': 'Fitness Consciente', 'review': None},
    'Curl martillo': {'video_id': 'znTSJ_2zJN0', 'title': 'Curl martillo con mancuernas: la técnica PERFECTA', 'channel': 'Sergio Tejeda', 'review': None},
    'Curl de bíceps en polea': {'video_id': 'OGI2K-Qc2z0', 'title': 'Curl de bíceps en polea: sube solo hasta los 90 GRADOS', 'channel': 'Sergio Tejeda', 'review': None},
    'Extensión de tríceps con cuerda': {'video_id': 'uZg6VtRhwQY', 'title': 'Tríceps en Polea con Cuerdas / Tips Claves', 'channel': 'Zonapablo', 'review': None},
    'Extensión de tríceps por encima de la cabeza': {'video_id': 'X_NJobViynU', 'title': 'EXTENSIÓN DE TRÍCEP POR ENCIMA DE LA CABEZA CON SOGA | EN POLEA ALTA', 'channel': 'Nutriólogo Conrado 👨\u200d⚕️', 'review': None},
    'Press francés': {'video_id': 'PTO862T8U7Y', 'title': 'PRESS FRANCES TECNICA CORRECTA', 'channel': 'Entrenamiento Diferencial', 'review': None},
    'Crunch en polea': {'video_id': 'ui3iEsYbXtI', 'title': 'Crunches abdominales en polea - Técnica correcta✅ - Galvistrainer', 'channel': 'Galvistrainer', 'review': None},
    'Crunch en máquina': {'video_id': 'yEiI4EYIiB0', 'title': 'Crunch en maquina', 'channel': 'Ammfit', 'review': None},
    'Pallof press': {'video_id': 'c-byXbLkWzY', 'title': 'Press Pallof con Banda o Polea / Ejercicio de Core isométrico', 'channel': 'Zonapablo', 'review': None},
    'Elevación de rodillas': {'video_id': 'naR7Qldgxrg', 'title': 'Elevación de rodillas colgado: así SÍ trabaja el abdomen', 'channel': 'Sergio Tejeda', 'review': 'variante colgado; el equipo del catálogo es «Peso corporal»'},
}
