"""Fichas de ejercicio (español) para los 59 ejercicios del catálogo.

Clave = nombre del ejercicio tal y como está en ``seed_exercises_v2.EXERCISES``.
El seed (``exercise_sheets.apply_exercise_sheets``) casa por nombre normalizado
(sin tildes, minúsculas), nunca por id.

Cada ficha: instructions (resumen), steps (pasos numerados), technical_cues
(claves técnicas), common_mistakes (errores frecuentes), safety_notes y
contraindications. Texto revisado a mano; si cambias algo, sube SHEET_VERSION.
"""

SHEET_VERSION = 1


def _s(instructions, steps, cues, mistakes, safety, contra):
    return {
        "instructions": instructions,
        "steps": steps,
        "technical_cues": cues,
        "common_mistakes": mistakes,
        "safety_notes": safety,
        "contraindications": contra,
    }


SHEETS = {}

# ------------------------------------------------------------------ PECHO
SHEETS["Aperturas de pecho en máquina"] = _s(
    "Aislamiento de pectoral en la máquina de contractora (pec deck). Los brazos se cierran al frente en un arco amplio y controlado.",
    [
        "Ajusta el asiento para que las asas queden a la altura del pecho, con los codos ligeramente por debajo de los hombros.",
        "Siéntate con la espalda y la cabeza pegadas al respaldo y agarra las asas con los codos algo flexionados.",
        "Junta los brazos al frente en un arco, como si abrazaras un árbol grande, hasta que las asas se acerquen.",
        "Mantén 1 segundo la contracción del pecho.",
        "Abre despacio (2-3 s) hasta notar un buen estiramiento del pecho, sin pasar la línea de los hombros.",
    ],
    ["Hombros bajos y atrás, pecho alto.", "Piensa en juntar los codos, no las manos.", "Baja la fase de apertura más lento que la de cierre."],
    ["Dejar que los hombros se adelanten al cerrar.", "Abrir demasiado y cargar el hombro en el estiramiento.", "Usar impulso con la espalda despegada del respaldo."],
    "Detén la apertura cuando notes tirantez en la parte delantera del hombro.",
    "Dolor agudo de hombro o antecedentes de luxación anterior: limita el rango de apertura o evita el ejercicio.",
)
SHEETS["Cruce de poleas"] = _s(
    "Aislamiento de pectoral con dos poleas. Los brazos se cruzan al frente manteniendo tensión continua en el cable.",
    [
        "Coloca las poleas altas (o a la altura del pecho) y agarra un asa en cada mano.",
        "Da un paso al frente con un pie, inclina un poco el tronco y deja los codos ligeramente flexionados.",
        "Cierra los brazos en un arco hacia delante y abajo hasta juntar las manos delante del pecho.",
        "Aprieta el pecho 1 segundo.",
        "Vuelve abriendo los brazos de forma controlada hasta notar el estiramiento del pectoral, sin que el peso tire de los hombros.",
    ],
    ["Mantén el ángulo del codo constante durante todo el recorrido.", "Pecho alto, escápulas atrás y abajo.", "El movimiento sale del hombro, no del codo."],
    ["Convertirlo en un press (doblar y estirar los codos).", "Usar demasiado peso y balancear el torso.", "Abrir tanto que el hombro se va hacia delante."],
    "Elige un peso con el que puedas controlar la fase de apertura. Pasos firmes, abdomen activo.",
    "Molestias de hombro al abrir en cruz: reduce el rango o sube las poleas.",
)
SHEETS["Press banca con mancuernas"] = _s(
    "Empuje horizontal con mancuernas tumbado en banco plano. Permite más rango y trabajo independiente de cada brazo que la barra.",
    [
        "Siéntate en el banco con las mancuernas sobre los muslos y túmbate llevándolas al pecho.",
        "Junta y baja las escápulas, planta los pies firmes y arquea ligeramente la zona torácica.",
        "Empuja las mancuernas hacia arriba hasta casi extender los codos, sobre la línea del pecho.",
        "Baja de forma controlada (2-3 s) hasta que los codos queden algo por debajo del pecho, con los antebrazos verticales.",
        "Repite sin rebotar ni despegar los glúteos del banco.",
    ],
    ["Codos a unos 45-60° del tronco, no abiertos en cruz.", "Muñecas rectas, antebrazos verticales.", "Escápulas fijas en el banco durante toda la serie."],
    ["Abrir los codos a 90° y cargar el hombro.", "Rebotar las mancuernas en el pecho.", "Despegar los glúteos del banco o hundir demasiado la espalda."],
    "Para soltar las mancuernas al acabar, llévalas a los muslos y siéntate; no las dejes caer. Usa seguridad si vas cerca del fallo.",
    "Dolor de hombro al bajar: acorta el recorrido o usa agarre neutro.",
)
SHEETS["Press banca plano"] = _s(
    "Empuje horizontal con barra en banco plano. Ejercicio básico de fuerza para pecho, tríceps y deltoides anterior.",
    [
        "Túmbate con los ojos bajo la barra, pies firmes en el suelo y escápulas juntas y abajo.",
        "Agarra la barra algo más ancha que los hombros y sácala del soporte con los brazos estirados.",
        "Baja la barra controlada hasta rozar la parte baja del pecho, con los codos a unos 45-60° del cuerpo.",
        "Empuja hacia arriba y ligeramente atrás hasta extender los brazos.",
        "Mantén glúteos en el banco y pies en el suelo durante toda la serie.",
    ],
    ["Muñecas apiladas sobre los codos.", "Aprieta la barra como si quisieras doblarla.", "Pecho alto y escápulas retraídas toda la serie."],
    ["Abrir los codos en 90° y cargar los hombros.", "Rebotar la barra en el pecho.", "Despegar los glúteos del banco o levantar los pies."],
    "Usa soportes de seguridad o un ayudante cuando vayas cerca del fallo. Nunca uses agarre sin pulgar.",
    "Dolor de hombro anterior o lesión de pectoral: consulta antes; usa mancuernas o máquina si la barra molesta.",
)
SHEETS["Press convergente de pecho"] = _s(
    "Press de pecho guiado en máquina con trayectoria convergente: las asas se acercan al empujar, lo que facilita trabajar el pectoral con seguridad.",
    [
        "Ajusta el asiento para que las asas queden a la altura del pecho medio.",
        "Pega la espalda al respaldo y retrae los hombros hacia atrás y abajo.",
        "Empuja las asas hacia delante hasta casi extender los codos, juntando ligeramente las manos.",
        "Pausa breve sintiendo el pecho.",
        "Vuelve despacio hasta que los codos queden a la altura del pecho, sin dejar que la pila toque el tope.",
    ],
    ["Hombros lejos de las orejas.", "Empuja con la palma, no con los dedos.", "Controla el retorno más de lo que lo empujas."],
    ["Asiento demasiado bajo o alto (carga el hombro).", "Despegar la espalda del respaldo.", "Rebotar la pila en cada repetición."],
    "Detén la serie si notas pinzamiento en el hombro; reajusta el asiento.",
    "Dolor de hombro al empujar: reduce rango o cambia a mancuernas con agarre neutro.",
)
SHEETS["Press inclinado con mancuernas 30 grados"] = _s(
    "Press con mancuernas en banco inclinado a unos 30° para enfatizar la parte superior del pectoral sin cargar demasiado el hombro.",
    [
        "Ajusta el banco a unos 30° (bajo, no a 45° o más).",
        "Siéntate con las mancuernas en los muslos y túmbate llevándolas a la altura del pecho.",
        "Escápulas juntas y abajo, pies firmes en el suelo.",
        "Empuja hacia arriba hasta casi extender los codos, con las mancuernas sobre la parte alta del pecho.",
        "Baja controlado (2-3 s) hasta notar el estiramiento del pectoral, antebrazos verticales.",
    ],
    ["Inclinación baja: a más de 45° trabaja casi solo el hombro.", "Codos a 45-60° del tronco.", "No choques las mancuernas arriba; mantén tensión."],
    ["Inclinar el banco demasiado.", "Abrir los codos y cargar el hombro.", "Rebotar abajo o arquear en exceso la lumbar."],
    "Usa pesos que controles al bajar; al terminar, apoya las mancuernas en los muslos antes de soltarlas.",
    "Dolor de hombro al bajar: reduce el rango o usa agarre neutro.",
)
SHEETS["Press inclinado en máquina"] = _s(
    "Press de pecho guiado con inclinación que enfatiza el pectoral superior. Trayectoria estable, ideal para series cercanas al fallo.",
    [
        "Ajusta el asiento para que las asas queden a la altura de la parte alta del pecho.",
        "Pega la espalda al respaldo y baja los hombros.",
        "Empuja las asas hacia arriba y delante hasta casi extender los codos.",
        "Pausa 1 segundo arriba sin bloquear los codos.",
        "Vuelve controlado hasta que las manos queden a la altura del pecho.",
    ],
    ["Hombros abajo y atrás, nunca encogidos.", "Empuja en línea con la inclinación de la máquina.", "Tempo lento al bajar."],
    ["Encoger los hombros hacia las orejas.", "Asiento demasiado alto (empuja solo hombro).", "Rebotar la pila."],
    "Si notas el hombro delantero molesto, baja el asiento un punto y reduce el peso.",
    "Pinzamiento o dolor de hombro al empujar por encima del pecho.",
)
# --------------------------------------------------------------- HOMBRO
SHEETS["Elevaciones laterales con mancuernas"] = _s(
    "Aislamiento del deltoides lateral. Se elevan los brazos a los lados hasta la altura de los hombros con una ligera inclinación del tronco.",
    [
        "De pie, mancuernas a los lados, pies al ancho de caderas y rodillas sueltas.",
        "Inclina el tronco unos 10-15° y flexiona un poco los codos.",
        "Eleva los brazos hacia los lados hasta la altura de los hombros, liderando con los codos.",
        "Pausa breve arriba, con la mano no más alta que el codo.",
        "Baja despacio (2-3 s) sin dejar que las mancuernas descansen abajo.",
    ],
    ["Piensa en llevar los codos hacia fuera, no las manos.", "Hombros lejos de las orejas.", "Peso ligero y repeticiones limpias."],
    ["Balancear el cuerpo para subir el peso.", "Encoger el trapecio.", "Subir por encima de los hombros con los codos rectos."],
    "Si notas tensión en el cuello o el trapecio, baja el peso y reduce el recorrido.",
    "Dolor de hombro al elevar el brazo: limita el recorrido por debajo de los 90°.",
)
SHEETS["Elevaciones laterales en máquina"] = _s(
    "Elevación lateral guiada que mantiene tensión constante en el deltoides lateral con una trayectoria estable.",
    [
        "Ajusta el asiento para que los hombros queden alineados con el eje de giro de la máquina.",
        "Apoya los antebrazos o codos en las almohadillas y agarra las asas con comodidad.",
        "Eleva los brazos hacia los lados hasta la altura de los hombros, empujando con los codos.",
        "Pausa 1 segundo arriba.",
        "Baja controlado sin descansar la pila entre repeticiones.",
    ],
    ["Empuja con los codos, no con las manos.", "Mantén los hombros bajos.", "Tempo lento, sin impulso."],
    ["Asiento mal ajustado (eje desalineado).", "Encoger los hombros al subir.", "Dejar caer el peso en la fase de bajada."],
    "Ajusta bien el eje de giro; si molesta el hombro, reduce el peso.",
    "Dolor de hombro al elevar el brazo lateralmente.",
)
SHEETS["Elevaciones laterales en polea"] = _s(
    "Elevación lateral unilateral con polea baja. La polea mantiene tensión constante en todo el recorrido, incluso abajo.",
    [
        "Coloca la polea baja y agarra el asa con la mano contraria al lado del cable, cruzando por delante del cuerpo.",
        "Agárrate con la otra mano a la máquina para estabilizarte y ladea el torso ligeramente.",
        "Eleva el brazo lateralmente hasta la altura del hombro con el codo ligeramente flexionado.",
        "Pausa breve arriba.",
        "Baja controlado sin perder tensión y repite; después cambia de lado.",
    ],
    ["Lidera con el codo.", "Hombro bajo, sin encoger.", "Recorrido corto y controlado vale más que mucho peso."],
    ["Balancear el torso para ayudarse.", "Subir más arriba de la altura del hombro.", "Usar demasiado peso y perder el control."],
    "Empieza con poco peso; la polea castiga el hombro si se balancea.",
    "Pinzamiento de hombro: no subas por encima de la horizontal.",
)
SHEETS["Face pull"] = _s(
    "Tracción de polea alta hacia la cara para deltoides posterior, trapecio medio y rotadores externos. Muy útil para la salud del hombro.",
    [
        "Coloca la polea a la altura de la cara o algo superior con cuerda doble.",
        "Agarra la cuerda con las palmas enfrentadas, da un paso atrás y ponte con los brazos estirados.",
        "Tira de la cuerda hacia la frente o la nariz, separando las manos y llevando los codos hacia fuera y atrás.",
        "Termina con los codos altos y las manos a los lados de la cabeza; aprieta la espalda alta 1 segundo.",
        "Vuelve controlado hasta estirar los brazos.",
    ],
    ["Codos altos, por encima de las muñecas.", "Rota los hombros hacia fuera al final del movimiento.", "Peso ligero y control total."],
    ["Tirar con mucho peso y echar el cuerpo hacia atrás.", "Codos bajos (se convierte en un remo).", "Encoger los hombros."],
    "Usa un peso moderado; el objetivo es el control, no la carga.",
    "Dolor agudo de hombro al rotar externamente.",
)
SHEETS["Press de hombro con mancuernas agarre neutro"] = _s(
    "Press vertical sentado con mancuernas y palmas enfrentadas. El agarre neutro es más amable con el hombro que el agarre pronado.",
    [
        "Siéntate en un banco con respaldo vertical y las mancuernas a la altura de los hombros, palmas enfrentadas.",
        "Pega la espalda al respaldo, abdomen firme y codos ligeramente por delante del cuerpo.",
        "Empuja las mancuernas hacia arriba hasta casi extender los codos.",
        "Pausa breve arriba sin chocar las mancuernas.",
        "Baja de forma controlada hasta que las mancuernas queden a la altura de las orejas.",
    ],
    ["Antebrazos verticales durante todo el recorrido.", "Costillas abajo, sin arquear la lumbar.", "Empuja ligeramente hacia dentro y arriba."],
    ["Arquear mucho la espalda para empujar.", "Abrir los codos hacia atrás.", "Bajar demasiado y perder el control del hombro."],
    "Si empujas pesado, usa un banco con respaldo y entra en la posición con ayuda de las rodillas.",
    "Pinzamiento de hombro o dolor al elevar los brazos por encima de la cabeza.",
)
SHEETS["Press de hombros en máquina"] = _s(
    "Press vertical guiado en máquina para deltoides con trayectoria estable y menos exigencia de estabilización.",
    [
        "Ajusta el asiento para que las asas queden a la altura de los hombros al inicio.",
        "Pega la espalda al respaldo y agarra las asas con las muñecas rectas.",
        "Empuja hacia arriba hasta casi extender los codos.",
        "Pausa breve arriba sin encoger los hombros.",
        "Baja controlado hasta la altura de las orejas.",
    ],
    ["Costillas abajo, abdomen firme.", "Hombros lejos de las orejas.", "Baja lento (2-3 s)."],
    ["Arquear la lumbar al empujar.", "Asiento demasiado bajo (carga el hombro).", "Rebotar la pila abajo."],
    "Ajusta el asiento antes de cargar peso; si el hombro pincha, baja la altura de inicio.",
    "Dolor de hombro al elevar por encima de la cabeza.",
)
SHEETS["Press militar con barra"] = _s(
    "Press vertical con barra de pie. Ejercicio de fuerza para deltoides, tríceps y estabilizadores del tronco.",
    [
        "Barra a la altura de la clavícula en el soporte, agarre algo más ancho que los hombros; sácala y da un paso atrás.",
        "Pies al ancho de caderas, glúteos y abdomen apretados, codos ligeramente por delante de la barra.",
        "Empuja la barra hacia arriba, echando la cabeza un poco atrás para dejar pasar la barra.",
        "Termina con los brazos extendidos y la barra sobre la coronilla, cabeza metida bajo la barra.",
        "Baja controlado hasta la clavícula.",
    ],
    ["Aprieta glúteos y abdomen en todo momento.", "Trayectoria vertical de la barra.", "Muñecas rectas y barra sobre el talón de la mano."],
    ["Arquear la lumbar excesivamente.", "No meter la cabeza bajo la barra arriba.", "Empujar con las piernas sin querer (se convierte en push press)."],
    "Usa soportes a la altura adecuada y no entrenes al fallo sin ayuda. Cinturón opcional en cargas altas.",
    "Dolor lumbar o de hombro al elevar los brazos por encima de la cabeza.",
)
SHEETS["Pájaros en máquina"] = _s(
    "Aislamiento del deltoides posterior en la máquina de contractora invertida (peck deck) sentado de cara al respaldo.",
    [
        "Ajusta el asiento para que las asas queden a la altura de los hombros.",
        "Siéntate de cara al respaldo con el pecho apoyado y agarra las asas con los brazos casi estirados.",
        "Abre los brazos hacia los lados y atrás en un arco hasta la altura de la espalda.",
        "Aprieta la espalda alta 1 segundo.",
        "Vuelve despacio sin dejar que la pila toque el tope.",
    ],
    ["Lidera con los codos.", "Pecho pegado al apoyo, hombros bajos.", "Usa poco peso y recorrido completo."],
    ["Tirar con el trapecio y encoger los hombros.", "Usar impulso con el tronco.", "Pasar de la línea del cuerpo cargando el hombro."],
    "Peso ligero: el deltoides posterior es pequeño y se fatiga rápido.",
    "Dolor de hombro al abrir hacia atrás.",
)
# --------------------------------------------------------------- TRÍCEPS
SHEETS["Extensión de tríceps en polea"] = _s(
    "Extensión de codo con polea alta (barra o cuerda). Ejercicio básico de aislamiento de tríceps.",
    [
        "Coloca la polea alta con barra, V o cuerda y agarra el accesorio con los codos pegados al cuerpo.",
        "Inclina el torso ligeramente y mantén los hombros bajos.",
        "Extiende los codos hasta estirar los brazos sin mover los hombros.",
        "Aprieta el tríceps 1 segundo abajo.",
        "Sube controlado hasta que los antebrazos queden por encima de la horizontal, sin despegar los codos.",
    ],
    ["Codos pegados y fijos como bisagras.", "Muñecas rectas.", "Sube lento y completo."],
    ["Mover los codos hacia delante y atrás.", "Inclinarse y empujar con el peso del cuerpo.", "Acortar el recorrido arriba."],
    "Peso con el que puedas mantener los codos quietos.",
    "Dolor de codo (epicondilitis): cambia a cuerda y agarre neutro con menos peso.",
)
SHEETS["Extensión de tríceps con cuerda"] = _s(
    "Extensión de tríceps en polea alta con cuerda. Permite abrir las manos al final para una contracción mayor.",
    [
        "Polea alta con cuerda; agárrala con las palmas enfrentadas y los codos pegados al cuerpo.",
        "Inclina ligeramente el torso y fija los hombros.",
        "Extiende los codos hacia abajo y, al final, separa las manos abriendo la cuerda.",
        "Aprieta el tríceps 1 segundo.",
        "Vuelve controlado sin mover los codos.",
    ],
    ["Codos fijos pegados a las costillas.", "Abre la cuerda al final del recorrido.", "Control en la subida."],
    ["Balancear el tronco.", "Subir los codos al final de la repetición.", "Acortar la fase de subida."],
    "Elige un peso que te permita abrir la cuerda sin ayudarte con el cuerpo.",
    "Dolor de codo o muñeca persistente.",
)
SHEETS["Extensión de tríceps por encima de la cabeza"] = _s(
    "Extensión de codo con los brazos sobre la cabeza (polea con cuerda). Estira la cabeza larga del tríceps y la trabaja de forma intensa.",
    [
        "Coloca la polea baja o media con cuerda, agarra la cuerda y da la espalda a la máquina.",
        "Lleva los codos hacia arriba y delante, pegados a la cabeza, con la cuerda detrás de la nuca.",
        "Da un paso al frente con un pie para estabilizarte y mantén el abdomen firme.",
        "Extiende los codos hasta estirar los brazos por encima de la cabeza.",
        "Vuelve controlado hasta notar el estiramiento del tríceps, sin abrir los codos.",
    ],
    ["Codos apuntando hacia delante y juntos.", "Costillas abajo, sin arquear la lumbar.", "Baja despacio para aprovechar el estiramiento."],
    ["Abrir los codos hacia los lados.", "Arquear la zona lumbar al empujar.", "Usar demasiado peso y mover los hombros."],
    "Con peso moderado; el estiramiento bajo carga es intenso para el codo.",
    "Dolor de codo o limitación de movilidad del hombro por encima de la cabeza.",
)
SHEETS["Press francés"] = _s(
    "Extensión de tríceps tumbado con barra o barra Z. La flexión del codo baja el peso hacia la frente o por detrás de la cabeza.",
    [
        "Túmbate en banco plano con la barra Z agarrada con las manos al ancho de los hombros y los brazos verticales.",
        "Mantén los codos apuntando al techo, no abiertos.",
        "Flexiona los codos y baja la barra hacia la frente o un poco por detrás de la cabeza.",
        "Extiende los codos para volver arriba, sin mover los hombros.",
        "Controla la bajada (2-3 s) y repite.",
    ],
    ["Solo se mueven los antebrazos.", "Codos estrechos y apuntando arriba.", "Muñecas neutras."],
    ["Abrir los codos en cruz.", "Convertirlo en un pullover moviendo los hombros.", "Usar demasiado peso y bajar sin control."],
    "Usa un ayudante o soportes si vas pesado; baja al ritmo que puedas parar.",
    "Dolor de codo o antecedentes de tendinopatía del tríceps.",
)
# --------------------------------------------------------------- BÍCEPS
SHEETS["Curl de bíceps en máquina"] = _s(
    "Curl con apoyo de brazos (tipo predicador) en máquina. Aísla el bíceps eliminando el balanceo.",
    [
        "Ajusta el asiento para que los codos queden alineados con el eje de la máquina y las axilas sobre el apoyo.",
        "Agarra las asas con las palmas hacia arriba.",
        "Flexiona los codos llevando las manos hacia los hombros.",
        "Aprieta el bíceps 1 segundo arriba.",
        "Baja controlado (2-3 s) hasta casi extender los codos sin soltar la tensión.",
    ],
    ["Brazos pegados al apoyo.", "No dejes caer el peso abajo.", "Muñecas rectas."],
    ["Asiento mal ajustado.", "Despegar los codos del apoyo para subir.", "Dejar caer la pila en la bajada."],
    "No extiendas del todo los codos bajo carga alta: evita tirones del bíceps.",
    "Dolor de codo o antecedentes de rotura de bíceps distal.",
)
SHEETS["Curl con mancuernas"] = _s(
    "Flexión de codo con mancuernas de pie o sentado. Ejercicio básico para el bíceps braquial.",
    [
        "De pie con una mancuerna en cada mano, palmas hacia delante y codos pegados al cuerpo.",
        "Flexiona los codos llevando las mancuernas hacia los hombros, sin mover los codos.",
        "Gira la muñeca ligeramente hacia fuera (supinación) al subir si te resulta cómodo.",
        "Aprieta arriba 1 segundo.",
        "Baja controlado (2-3 s) hasta casi extender los brazos.",
    ],
    ["Codos fijos junto al torso.", "Hombros quietos y atrás.", "Sin balanceo del tronco."],
    ["Balancear el cuerpo para subir el peso.", "Adelantar los codos al subir.", "Bajar de golpe."],
    "Si necesitas balancear, el peso es excesivo: bájalo.",
    "Dolor de codo o muñeca persistente.",
)
SHEETS["Curl inclinado con mancuernas"] = _s(
    "Curl con mancuernas en banco inclinado. Con el brazo detrás del cuerpo el bíceps se trabaja en posición de gran estiramiento.",
    [
        "Ajusta el banco a 45-60° y siéntate con la espalda apoyada y los brazos colgando.",
        "Con las palmas hacia delante, flexiona los codos sin adelantarlos.",
        "Sube hasta que los antebrazos estén casi verticales y aprieta el bíceps.",
        "Baja de forma lenta y completa, aprovechando el estiramiento.",
    ],
    ["Hombros pegados al respaldo.", "No encojas los hombros.", "Usa peso ligero para controlar el estiramiento."],
    ["Despegar la espalda del banco.", "Adelantar los codos al subir.", "Usar demasiado peso y cortar el estiramiento."],
    "Es un ejercicio exigente en la bajada: elige un peso más ligero que en el curl de pie.",
    "Dolor de hombro anterior al estirar el brazo hacia atrás.",
)
SHEETS["Curl martillo"] = _s(
    "Curl con agarre neutro (palmas enfrentadas). Trabaja braquial y braquiorradial además del bíceps.",
    [
        "De pie con una mancuerna en cada mano, palmas enfrentadas y pulgares hacia arriba.",
        "Flexiona los codos subiendo las mancuernas hacia los hombros sin girar las muñecas.",
        "Aprieta arriba 1 segundo.",
        "Baja controlado hasta casi extender los brazos.",
    ],
    ["Codos pegados al cuerpo.", "Muñeca neutra todo el recorrido.", "Sube y baja sin balanceo."],
    ["Balancear el tronco.", "Adelantar los codos.", "Girar la muñeca a mitad del recorrido."],
    "Mantén las muñecas rectas; si molestan, baja el peso.",
    "Dolor de codo o antebrazo persistente.",
)
SHEETS["Curl de bíceps en polea"] = _s(
    "Curl con polea baja (barra o cuerda). La polea mantiene tensión constante durante todo el recorrido.",
    [
        "Coloca la polea baja con barra o cuerda y agárrala con las palmas hacia arriba.",
        "Codos pegados al cuerpo y pies firmes, a una distancia de la polea que permita tensión desde abajo.",
        "Flexiona los codos llevando las manos hacia los hombros.",
        "Aprieta el bíceps arriba.",
        "Baja controlado sin perder la tensión del cable.",
    ],
    ["Codos fijos junto a las costillas.", "No dejes que la pila toque abajo.", "Costillas abajo, sin arquear la espalda."],
    ["Acercarse tanto a la polea que se pierde tensión abajo.", "Balancear el cuerpo.", "Subir los codos hacia delante."],
    "Peso con el que puedas controlar la bajada.",
    "Dolor de codo o antebrazo con el agarre de barra: prueba con cuerda.",
)
# ---------------------------------------------------------------- ESPALDA
SHEETS["Jalón al pecho agarre amplio"] = _s(
    "Tracción vertical en polea alta con agarre ancho pronado. Trabaja dorsal ancho, redondo mayor y bíceps.",
    [
        "Ajusta el cojín de los muslos y agarra la barra algo más ancha que los hombros, con las palmas hacia delante.",
        "Siéntate con el pecho alto y el tronco ligeramente inclinado hacia atrás.",
        "Baja los hombros y tira de la barra hacia la parte alta del pecho, llevando los codos hacia abajo y atrás.",
        "Aprieta la espalda 1 segundo abajo.",
        "Sube controlado hasta estirar los brazos sin que los hombros se eleven hacia las orejas.",
    ],
    ["Piensa en llevar los codos a los bolsillos.", "Pecho hacia la barra, no la barra hacia el pecho.", "Hombros abajo al empezar cada repetición."],
    ["Tirar con los brazos y no con la espalda.", "Echar el cuerpo hacia atrás y balancearse.", "Llevar la barra detrás de la nuca."],
    "No tires de la barra detrás de la nuca: sobrecarga el hombro y las cervicales.",
    "Dolor de hombro al elevar los brazos por encima de la cabeza.",
)
SHEETS["Jalón al pecho agarre neutro"] = _s(
    "Tracción vertical en polea alta con agarre neutro (palmas enfrentadas). Es más amable con hombros y codos y permite mucho recorrido del dorsal.",
    [
        "Coloca el agarre neutro (triángulo o asas paralelas) y ajusta el cojín de los muslos.",
        "Siéntate con el pecho alto, tronco ligeramente atrás y brazos estirados.",
        "Baja los hombros y tira del agarre hacia el pecho, con los codos hacia abajo y pegados a las costillas.",
        "Aprieta la espalda 1 segundo abajo.",
        "Sube controlado hasta estirar el dorsal sin elevar los hombros.",
    ],
    ["Codos hacia los bolsillos.", "Pecho alto y escápulas hacia abajo.", "Sube lento para estirar el dorsal."],
    ["Tirar con los bíceps y los hombros encogidos.", "Balancear el torso para ayudarse.", "Soltar el peso de golpe arriba."],
    "Mantén el tronco estable; si necesitas balancear, reduce el peso.",
    "Dolor de hombro al estirar los brazos por encima de la cabeza.",
)
SHEETS["Jalón unilateral en polea"] = _s(
    "Jalón a un brazo con polea alta. Permite mayor rango y corregir diferencias entre lados.",
    [
        "Coloca un asa en la polea alta y siéntate o arrodíllate de lado o de frente al cable.",
        "Agarra el asa con una mano, el brazo estirado y el hombro bajo.",
        "Tira del codo hacia el costado y abajo, acercando la mano al hombro.",
        "Aprieta el dorsal 1 segundo.",
        "Sube controlado hasta estirar completamente el brazo sin encoger el hombro.",
    ],
    ["Lidera con el codo hacia el bolsillo.", "Tronco quieto, sin rotar.", "Estira del todo el dorsal arriba."],
    ["Rotar el tronco para ayudarse.", "Tirar con el bíceps y el antebrazo.", "Encoger el hombro al estirar."],
    "Estabiliza bien la postura: arrodíllate o apóyate si el peso te desplaza.",
    "Dolor de hombro al estirar el brazo por encima de la cabeza.",
)
SHEETS["Pullover en polea"] = _s(
    "Pullover de brazos casi rectos en polea alta. Aísla el dorsal ancho con una gran fase de estiramiento.",
    [
        "Coloca la polea alta con cuerda o barra corta y ponte de pie frente a ella a un paso.",
        "Agarra con los brazos estirados por delante, algo por encima de la cabeza, e inclina ligeramente el torso.",
        "Con los codos casi rectos, lleva las manos hacia los muslos describiendo un arco.",
        "Aprieta el dorsal 1 segundo abajo.",
        "Sube despacio hasta sentir el estiramiento del dorsal, sin perder la posición del tronco.",
    ],
    ["Brazos casi rectos todo el recorrido.", "Costillas abajo, abdomen firme.", "El movimiento nace del hombro."],
    ["Doblar los codos y convertirlo en un press de tríceps.", "Arquear la lumbar al subir.", "Usar demasiado peso y balancear el cuerpo."],
    "Peso moderado y tronco estable; no fuerces el estiramiento arriba.",
    "Dolor de hombro al elevar los brazos por encima de la cabeza.",
)
SHEETS["Remo con pecho apoyado"] = _s(
    "Remo con el pecho apoyado en banco inclinado o máquina. El apoyo elimina el balanceo y protege la lumbar.",
    [
        "Ajusta el banco o la máquina para que el pecho quede apoyado y los brazos cuelguen estirados.",
        "Agarra las asas o mancuernas con los hombros relajados.",
        "Tira de los codos hacia atrás y ligeramente hacia arriba, juntando las escápulas.",
        "Aprieta la espalda 1 segundo.",
        "Baja controlado hasta estirar del todo los brazos.",
    ],
    ["Pecho siempre apoyado, sin despegarlo.", "Piensa en llevar los codos hacia atrás.", "Hombros abajo; evita el encogimiento."],
    ["Despegar el pecho del apoyo para ayudarse.", "Tirar con los bíceps en vez de con la espalda.", "Soltar el peso y no controlar la bajada."],
    "El apoyo protege la lumbar, pero mantén el cuello neutro y no encojas los hombros.",
    "Dolor de hombro al estirar los brazos hacia delante.",
)
SHEETS["Remo en máquina"] = _s(
    "Remo horizontal guiado en máquina con apoyo en el pecho. Trabaja espalda media, dorsal y deltoides posterior.",
    [
        "Ajusta el asiento y el apoyo de pecho para que los brazos queden estirados al agarrar las asas.",
        "Siéntate con el pecho apoyado y los hombros relajados.",
        "Tira de las asas hacia el torso llevando los codos atrás y juntando las escápulas.",
        "Aprieta la espalda 1 segundo.",
        "Vuelve controlado hasta estirar los brazos sin dejar que los hombros se adelanten de golpe.",
    ],
    ["Pecho apoyado y alto.", "Codos hacia atrás, cerca del cuerpo.", "Sin encoger los hombros."],
    ["Tirar con los brazos y echar el tronco hacia atrás.", "Encoger el cuello y los hombros.", "Rebotar la pila al volver."],
    "Evita que los hombros se redondeen al estirar; controla el retorno.",
    "Dolor agudo de hombro o espalda al tirar hacia atrás.",
)
SHEETS["Remo sentado en polea"] = _s(
    "Remo horizontal sentado en polea baja con agarre en V o neutro. Gran ejercicio de espalda media y dorsal.",
    [
        "Siéntate frente a la polea con los pies en los apoyos y las rodillas ligeramente flexionadas.",
        "Agarra el asa con los brazos estirados y el tronco erguido, espalda neutra.",
        "Tira del asa hacia el abdomen llevando los codos pegados atrás y juntando las escápulas.",
        "Aprieta la espalda 1 segundo.",
        "Vuelve controlado estirando los brazos, sin redondear la espalda.",
    ],
    ["Espalda recta, pecho alto.", "Tronco casi vertical, solo con un ligero balanceo controlado.", "Codos pegados al cuerpo."],
    ["Balancear mucho el tronco hacia atrás.", "Redondear la espalda al estirar.", "Tirar con los brazos y encoger los hombros."],
    "Mantén la lumbar neutra; si pierdes la postura al estirar, acorta el recorrido.",
    "Dolor lumbar agudo o hernia discal en fase aguda.",
)
SHEETS["Remo unilateral con mancuerna"] = _s(
    "Remo a una mano apoyado en un banco. Permite buen recorrido del dorsal y trabajar cada lado por separado.",
    [
        "Apoya una mano y la rodilla del mismo lado en un banco, con la espalda paralela al suelo y neutra.",
        "Agarra la mancuerna con el brazo estirado bajo el hombro.",
        "Tira de la mancuerna hacia la cadera llevando el codo hacia atrás y cerca del cuerpo.",
        "Aprieta la espalda 1 segundo arriba sin rotar el tronco.",
        "Baja controlado hasta estirar el brazo completamente.",
    ],
    ["Lidera con el codo hacia la cadera.", "Tronco quieto, sin rotar.", "Cuello neutro, mirada al suelo."],
    ["Rotar el tronco para subir más peso.", "Tirar con el bíceps y no con la espalda.", "Encoger el hombro arriba."],
    "Mantén la espalda neutra y evita tirones bruscos.",
    "Dolor lumbar o de hombro al tirar con el brazo.",
)
SHEETS["Remo unilateral en polea"] = _s(
    "Remo a un brazo en polea baja o media. La polea mantiene tensión constante y permite ajustar el ángulo de tracción.",
    [
        "Coloca la polea a la altura deseada y agarra el asa con una mano.",
        "Adopta una postura estable (en pie con una pierna adelantada o sentado) con el tronco firme.",
        "Tira del asa hacia la cadera con el codo pegado al cuerpo.",
        "Aprieta la espalda 1 segundo.",
        "Vuelve controlado hasta estirar el brazo, sin rotar el torso.",
    ],
    ["Codo hacia la cadera.", "Tronco quieto y firme.", "Estira del todo el dorsal al volver."],
    ["Rotar el tronco para ayudarse.", "Encoger el hombro al tirar.", "Soltar la tensión al volver."],
    "Busca una postura estable; si el peso te mueve, redúcelo.",
    "Dolor agudo de hombro o espalda al tirar.",
)
# --------------------------------------------------------------- PIERNA
SHEETS["Hack squat"] = _s(
    "Sentadilla guiada en máquina inclinada. Permite cargar cuádriceps y glúteos con la espalda apoyada y mucha estabilidad.",
    [
        "Colócate en la máquina con la espalda y los hombros apoyados y los pies a media altura de la plataforma, ancho de hombros.",
        "Suelta los seguros y estira las piernas sin bloquear las rodillas.",
        "Baja controlado doblando rodillas y caderas hasta unos 90° o hasta donde mantengas la pelvis pegada.",
        "Empuja la plataforma con todo el pie hasta casi extender las piernas.",
        "Al terminar, coloca de nuevo los seguros.",
    ],
    ["Talones pegados a la plataforma.", "Rodillas siguen la línea de los pies.", "Pelvis y espalda pegadas al respaldo."],
    ["Bajar tanto que se despega la pelvis del respaldo.", "Dejar que las rodillas se vayan hacia dentro.", "Bloquear las rodillas arriba con carga."],
    "Coloca siempre los seguros al terminar. Elige una profundidad que puedas controlar.",
    "Dolor de rodilla al flexionar: acorta el recorrido o prueba la prensa.",
)
SHEETS["Hip thrust"] = _s(
    "Extensión de cadera con la espalda alta apoyada en un banco. Es el ejercicio básico para el glúteo mayor.",
    [
        "Apoya la parte baja de las escápulas en el borde de un banco y coloca la barra (o la máquina) sobre las caderas, con almohadilla.",
        "Pies al ancho de caderas, rodillas dobladas a unos 90° arriba y mentón hacia el pecho.",
        "Empuja con los talones y sube las caderas hasta que el torso y los muslos queden alineados.",
        "Aprieta los glúteos 1-2 segundos arriba sin arquear la lumbar.",
        "Baja controlado hasta casi tocar el suelo y repite.",
    ],
    ["Costillas abajo, pelvis en retroversión arriba.", "Empuja con los talones.", "Mirada al frente, mentón metido."],
    ["Arquear la lumbar para subir más.", "Pies demasiado lejos o cerca (carga isquios o cuádriceps).", "Mover la barra sin proteger las caderas."],
    "Usa una almohadilla para las caderas y asegura la barra al empezar y terminar.",
    "Dolor lumbar al extender la cadera: reduce carga y rango.",
)
SHEETS["Hip thrust unilateral"] = _s(
    "Hip thrust a una pierna. Trabaja el glúteo de cada lado por separado y exige estabilidad de pelvis.",
    [
        "Apoya la parte alta de la espalda en un banco o máquina y adelanta una pierna con el pie plano en el suelo.",
        "Levanta la otra pierna con la rodilla flexionada hacia el pecho, o estirada si te resulta más cómodo.",
        "Empuja con el talón de la pierna de apoyo y sube la cadera hasta alinear torso y muslo.",
        "Aprieta el glúteo 1 segundo arriba manteniendo la pelvis nivelada.",
        "Baja controlado y completa las repeticiones antes de cambiar de pierna.",
    ],
    ["Pelvis nivelada, sin rotar.", "Empuja con todo el pie, enfocado en el talón.", "Costillas abajo."],
    ["Girar la pelvis para ayudarse.", "Arquear la lumbar arriba.", "Bajar de golpe sin control."],
    "Empieza sin peso para dominar el equilibrio; añade carga solo cuando la pelvis se mantenga nivelada.",
    "Dolor lumbar o de rodilla durante el empuje.",
)
SHEETS["Patada de glúteo en polea"] = _s(
    "Extensión de cadera con polea baja y tobillera. Aísla el glúteo mayor con tensión continua.",
    [
        "Coloca la tobillera en un tobillo y la polea baja; agárrate a la máquina con el tronco ligeramente inclinado.",
        "Mantén una ligera flexión de la rodilla de apoyo y la espalda neutra.",
        "Lleva la pierna hacia atrás y ligeramente arriba extendiendo la cadera.",
        "Aprieta el glúteo 1 segundo sin arquear la lumbar.",
        "Vuelve controlado sin dejar que el peso te tire hacia delante; completa y cambia de pierna.",
    ],
    ["El movimiento sale de la cadera, no de la lumbar.", "Pelvis cuadrada, sin rotar.", "Pierna de apoyo estable."],
    ["Arquear la lumbar para subir más la pierna.", "Rotar la cadera hacia fuera.", "Balancear la pierna con impulso."],
    "Peso moderado: si arqueas la lumbar, es demasiado.",
    "Dolor lumbar al llevar la pierna atrás.",
)
SHEETS["Peso muerto rumano"] = _s(
    "Bisagra de cadera con barra. Trabaja isquiosurales y glúteos con un gran estiramiento, manteniendo la espalda neutra.",
    [
        "De pie con la barra a la altura de los muslos, pies al ancho de caderas y rodillas ligeramente flexionadas.",
        "Empuja las caderas hacia atrás como si cerraras una puerta con el glúteo, con la barra pegada a las piernas.",
        "Baja hasta sentir el estiramiento de los isquios o hasta la mitad de la espinilla, con la espalda neutra.",
        "Empuja las caderas hacia delante y sube apretando los glúteos.",
        "Termina erguido sin arquear la lumbar.",
    ],
    ["Barra pegada al cuerpo todo el recorrido.", "Espalda neutra, pecho alto.", "El movimiento es de cadera, no de rodillas."],
    ["Redondear la espalda.", "Doblar demasiado las rodillas y convertirlo en un peso muerto convencional.", "Alejar la barra del cuerpo."],
    "Para si pierdes la neutralidad de la espalda. Empieza con peso moderado y aprende el patrón.",
    "Dolor lumbar agudo o hernia discal en fase aguda.",
)
SHEETS["Peso muerto rumano con mancuernas"] = _s(
    "Bisagra de cadera con mancuernas. Misma técnica que con barra, más fácil de aprender y ajustar.",
    [
        "De pie con una mancuerna en cada mano frente a los muslos, pies al ancho de caderas.",
        "Flexiona ligeramente las rodillas y empuja las caderas hacia atrás, con las mancuernas pegadas a las piernas.",
        "Baja hasta sentir el estiramiento de los isquios, con la espalda neutra.",
        "Sube empujando las caderas hacia delante y apretando los glúteos.",
        "Termina erguido sin arquear la lumbar.",
    ],
    ["Mancuernas pegadas al cuerpo.", "Cadera hacia atrás, rodillas casi fijas.", "Mirada al frente y espalda neutra."],
    ["Redondear la espalda al bajar.", "Flexionar demasiado las rodillas.", "Separar las mancuernas del cuerpo."],
    "Elige un peso con el que mantengas la espalda neutra; no bajes más de lo que tu movilidad permite.",
    "Dolor lumbar agudo o hernia discal en fase aguda.",
)
SHEETS["Prensa de piernas"] = _s(
    "Empuje de piernas en máquina inclinada a 45°. Trabaja cuádriceps y glúteos con la espalda apoyada.",
    [
        "Siéntate con la espalda y los glúteos pegados al respaldo y los pies a media altura de la plataforma, ancho de hombros.",
        "Suelta los seguros y estira las piernas sin bloquear las rodillas.",
        "Baja controlado doblando rodillas y caderas hasta unos 90°, sin que la pelvis se despegue del asiento.",
        "Empuja la plataforma con todo el pie hasta casi extender las piernas.",
        "Al terminar, coloca de nuevo los seguros.",
    ],
    ["Pelvis pegada al asiento.", "Rodillas alineadas con los pies.", "No bloquear las rodillas arriba."],
    ["Bajar tanto que la pelvis se despega y la lumbar se redondea.", "Dejar que las rodillas se vayan hacia dentro.", "Bloquear las rodillas arriba con cargas altas."],
    "Coloca siempre los seguros al terminar. Evita cargas que te impidan controlar la bajada.",
    "Dolor de rodilla o lumbar al flexionar: reduce recorrido o carga.",
)
SHEETS["Prensa unilateral"] = _s(
    "Prensa de piernas con una sola pierna. Corrige desequilibrios entre piernas y exige estabilidad de cadera.",
    [
        "Siéntate en la prensa con la espalda y los glúteos pegados y un pie en el centro de la plataforma.",
        "Suelta los seguros y estira la pierna sin bloquear la rodilla.",
        "Baja controlado doblando rodilla y cadera hasta unos 90°, con la rodilla alineada con el pie.",
        "Empuja con todo el pie hasta casi extender la pierna.",
        "Completa las repeticiones y cambia de pierna.",
    ],
    ["Pelvis nivelada, sin rotar.", "Rodilla en línea con el pie.", "Usa menos peso del que moverías con dos piernas."],
    ["Dejar que la rodilla se vaya hacia dentro.", "Despegar la pelvis del asiento.", "Cargar demasiado peso y perder el control."],
    "Reduce mucho la carga respecto a la prensa con dos piernas. Coloca los seguros al terminar.",
    "Dolor de rodilla o cadera durante el movimiento.",
)
SHEETS["Sentadilla búlgara"] = _s(
    "Sentadilla unilateral con el pie trasero elevado en un banco. Gran ejercicio para cuádriceps y glúteos con carga moderada.",
    [
        "Apoya el empeine del pie trasero en un banco y adelanta el otro pie unos 60-70 cm.",
        "Con una mancuerna en cada mano (o sin peso), mantén el tronco erguido y el abdomen firme.",
        "Baja doblando la rodilla delantera hasta que el muslo quede casi paralelo al suelo.",
        "Mantén la rodilla alineada con el pie y el talón apoyado.",
        "Empuja con el pie delantero para subir; completa las repeticiones y cambia de pierna.",
    ],
    ["Peso en el talón y el medio pie delantero.", "Tronco erguido o ligeramente inclinado.", "Rodilla delantera sigue la línea del pie."],
    ["Pie delantero demasiado cerca (rodilla muy adelantada).", "Dejar que la rodilla se vaya hacia dentro.", "Apoyarse en la pierna trasera para subir."],
    "Empieza sin peso para encontrar el equilibrio. Banco estable y a una altura cómoda.",
    "Dolor de rodilla o cadera al bajar: acorta el recorrido o cambia a prensa unilateral.",
)
SHEETS["Sentadilla goblet"] = _s(
    "Sentadilla sujetando una mancuerna o kettlebell junto al pecho. Ideal para aprender el patrón de sentadilla.",
    [
        "Sujeta una mancuerna vertical con ambas manos junto al pecho, codos hacia abajo.",
        "Pies algo más anchos que los hombros y puntas ligeramente abiertas.",
        "Baja doblando rodillas y caderas a la vez con el pecho alto, hasta una profundidad cómoda.",
        "Mantén los talones apoyados y las rodillas alineadas con los pies.",
        "Sube empujando el suelo hasta quedar erguido.",
    ],
    ["Pecho alto, mancuerna pegada al torso.", "Rodillas siguen la línea de los pies.", "Peso en todo el pie."],
    ["Redondear la espalda al bajar.", "Levantar los talones.", "Dejar que las rodillas colapsen hacia dentro."],
    "Empieza con poco peso; la mancuerna cerca del cuerpo te ayuda a mantener la postura.",
    "Dolor de rodilla o cadera al bajar: reduce profundidad.",
)
SHEETS["Sentadilla libre"] = _s(
    "Sentadilla con barra sobre la espalda. Ejercicio básico de fuerza para piernas y tronco.",
    [
        "Coloca la barra sobre los trapecios (o algo más baja), agarra a una anchura cómoda y sácala del soporte.",
        "Pies al ancho de hombros, puntas ligeramente abiertas, abdomen firme y pecho alto.",
        "Baja doblando rodillas y caderas a la vez, manteniendo la espalda neutra y los talones apoyados.",
        "Llega a una profundidad en la que la espalda no se redondee.",
        "Sube empujando el suelo con todo el pie hasta quedar erguido.",
    ],
    ["Respira y aprieta el abdomen antes de bajar.", "Rodillas siguen la línea de los pies.", "Pecho alto y mirada al frente."],
    ["Redondear la espalda abajo.", "Dejar que las rodillas se vayan hacia dentro.", "Subir primero la cadera y echar el torso adelante."],
    "Usa soportes de seguridad a la altura adecuada y no entrenes al fallo sin ellos.",
    "Dolor lumbar o de rodilla: reduce carga y profundidad; valora prensa o hack squat.",
)
SHEETS["Zancadas"] = _s(
    "Zancadas con mancuernas o con el peso corporal, avanzando o atrás. Trabaja cuádriceps y glúteos de forma unilateral.",
    [
        "De pie con una mancuerna en cada mano (o sin peso), pies al ancho de caderas.",
        "Da un paso largo al frente (o atrás) manteniendo el tronco erguido.",
        "Baja doblando ambas rodillas hasta que la rodilla trasera roce casi el suelo.",
        "Empuja con el pie delantero para volver a la posición inicial.",
        "Alterna las piernas en cada repetición o completa un lado y cambia.",
    ],
    ["Paso suficientemente largo para que la rodilla delantera no pase mucho los dedos.", "Tronco erguido, abdomen firme.", "Peso en el pie delantero."],
    ["Paso demasiado corto (rodilla muy adelantada).", "Inclinar el torso hacia delante.", "Dejar que la rodilla se vaya hacia dentro."],
    "Si pierdes el equilibrio, apóyate en una pared o usa zancadas estáticas.",
    "Dolor de rodilla al bajar: acorta el recorrido o prueba zancadas hacia atrás.",
)
SHEETS["Step-up"] = _s(
    "Subida a un cajón o banco con una pierna. Trabaja glúteos y cuádriceps de forma unilateral y funcional.",
    [
        "Coloca un cajón o banco estable de modo que, con el pie encima, la rodilla quede a unos 90°.",
        "Sujeta una mancuerna en cada mano y sube con un pie completo sobre el cajón.",
        "Empuja con la pierna de arriba hasta quedar erguido, sin impulsarte con la pierna de abajo.",
        "Baja controlado apoyando primero el pie de atrás.",
        "Completa las repeticiones y cambia de pierna.",
    ],
    ["El trabajo lo hace la pierna de arriba.", "Pie completo sobre el cajón.", "Tronco erguido y pelvis nivelada."],
    ["Impulsarse con la pierna de abajo.", "Dejar caer el cuerpo en la bajada.", "Cajón demasiado alto que fuerza la postura."],
    "Usa un cajón estable y una altura que controles; añade peso poco a poco.",
    "Dolor de rodilla al subir: baja la altura del cajón.",
)
SHEETS["Extensión de cadera en máquina"] = _s(
    "Extensión de cadera en máquina o con apoyo (tipo patada de glúteo). Aísla el glúteo mayor.",
    [
        "Ajusta la máquina y apoya el pecho o las manos de forma estable; coloca el pie en la plataforma o rodillo.",
        "Mantén el core firme y la espalda neutra.",
        "Empuja con la pierna hacia atrás extendiendo la cadera.",
        "Aprieta el glúteo 1 segundo arriba sin arquear la lumbar.",
        "Vuelve controlado y repite; después cambia de pierna.",
    ],
    ["El movimiento sale de la cadera.", "Pelvis cuadrada, sin rotar.", "No uses la lumbar para ganar rango."],
    ["Arquear la lumbar para subir más.", "Rotar la cadera hacia fuera.", "Balancear la pierna con impulso."],
    "Peso moderado; si notas la lumbar, reduce el peso y el rango.",
    "Dolor lumbar al extender la cadera.",
)
SHEETS["Abducción de cadera en máquina"] = _s(
    "Abducción de cadera sentado en máquina. Aísla el glúteo medio y menor.",
    [
        "Siéntate con la espalda pegada y las almohadillas por fuera de los muslos o rodillas.",
        "Ajusta el rango inicial para que sea cómodo y agarra las asas.",
        "Abre las piernas empujando las almohadillas hacia fuera.",
        "Pausa 1 segundo en la apertura máxima.",
        "Vuelve controlado sin dejar que la pila toque el tope.",
    ],
    ["Pelvis y espalda pegadas al respaldo.", "Empuja con las rodillas, no con los pies.", "Control en la vuelta."],
    ["Balancear el tronco para ganar impulso.", "Despegar la pelvis del asiento.", "Usar rangos demasiado cortos o dejar caer el peso."],
    "Ajusta el rango inicial; no fuerces una apertura que moleste la cadera.",
    "Dolor de cadera o ingle al abrir las piernas.",
)
SHEETS["Curl femoral"] = _s(
    "Flexión de rodilla en máquina de curl femoral (tumbado o sentado según la máquina). Trabaja los isquiosurales.",
    [
        "Ajusta el rodillo para que quede sobre los tobillos, por encima del talón, y alinea la rodilla con el eje.",
        "Agarra las asas y mantén la cadera apoyada.",
        "Flexiona las rodillas llevando los talones hacia los glúteos.",
        "Aprieta los isquios 1 segundo.",
        "Vuelve controlado (2-3 s) sin dejar que la pila toque el tope.",
    ],
    ["Cadera pegada, sin levantarla.", "Rodillas alineadas con el eje de la máquina.", "Baja lento para estirar los isquios."],
    ["Levantar la cadera para ayudarse.", "Usar impulso y rebotar la pila.", "Recorrido corto o mal ajustado."],
    "Ajusta bien el rodillo; si hay molestia en la rodilla, reduce el rango.",
    "Calambres frecuentes o antecedente de rotura de isquios: empieza con poco peso.",
)
SHEETS["Curl femoral sentado"] = _s(
    "Curl femoral en máquina sentado. La cadera flexionada estira los isquiosurales y permite un buen trabajo del músculo.",
    [
        "Ajusta el respaldo y el rodillo para que quede sobre los tobillos, y fija el cojín de los muslos.",
        "Siéntate con la espalda pegada y las piernas estiradas.",
        "Flexiona las rodillas llevando los talones hacia abajo y atrás.",
        "Aprieta los isquios 1 segundo.",
        "Vuelve controlado hasta estirar las piernas.",
    ],
    ["Espalda pegada al respaldo.", "Rodillas alineadas con el eje de la máquina.", "Tempo lento al subir."],
    ["Despegar la espalda para ayudarse.", "Rebotar la pila.", "Mal ajuste del rodillo."],
    "Ajusta bien el cojín de los muslos para evitar que la pierna se levante.",
    "Dolor de rodilla durante la flexión o antecedentes de lesión de isquios.",
)
SHEETS["Curl femoral tumbado"] = _s(
    "Curl femoral en máquina tumbado boca abajo. Trabaja los isquiosurales con la cadera extendida.",
    [
        "Túmbate boca abajo con las rodillas justo en el borde del banco y el rodillo sobre los tobillos.",
        "Agarra las asas y mantén las caderas pegadas al banco.",
        "Flexiona las rodillas llevando los talones hacia los glúteos.",
        "Aprieta los isquios 1 segundo.",
        "Baja controlado (2-3 s) sin dejar caer la pila.",
    ],
    ["Cadera siempre pegada al banco.", "Rodillas alineadas con el eje.", "Tempo lento al bajar."],
    ["Levantar la cadera para ayudarse.", "Balancear el cuerpo.", "Recorrido incompleto."],
    "No dejes que la pila caiga al bajar: protege la rodilla y los isquios.",
    "Dolor de rodilla durante la flexión.",
)
SHEETS["Extensión de cuádriceps"] = _s(
    "Extensión de rodilla en máquina. Aísla el cuádriceps con carga controlada.",
    [
        "Ajusta el respaldo para que la rodilla quede alineada con el eje de la máquina y el rodillo sobre el empeine.",
        "Siéntate con la espalda pegada y agarra las asas.",
        "Extiende las rodillas hasta casi bloquear las piernas.",
        "Aprieta el cuádriceps 1 segundo arriba.",
        "Baja controlado (2-3 s) sin dejar que la pila toque el tope.",
    ],
    ["Rodillas alineadas con el eje.", "Aprieta el cuádriceps arriba.", "Baja lento."],
    ["Rebotar la pila abajo.", "Usar impulso y despegar la cadera.", "Mal ajuste del rodillo o del respaldo."],
    "Rango cómodo; si la rodilla molesta, reduce el peso.",
    "Dolor femororrotuliano o de rodilla: acorta el rango y reduce la carga.",
)
SHEETS["Elevación de gemelos de pie"] = _s(
    "Elevación de talones de pie en máquina. Trabaja principalmente el gastrocnemio (gemelo).",
    [
        "Colócate en la máquina con los hombros bajo las almohadillas y la parte delantera de los pies en el borde de la plataforma.",
        "Mantén las piernas casi estiradas.",
        "Sube a la punta de los pies lo más alto que puedas.",
        "Pausa 1 segundo arriba.",
        "Baja controlado hasta estirar el gemelo completamente y repite.",
    ],
    ["Rango completo: estira abajo, sube arriba.", "Rodillas casi extendidas.", "Sin rebotes."],
    ["Rebotar sin estirar abajo.", "Doblar las rodillas para ayudar.", "Usar un rango corto."],
    "Controla la fase de bajada; evita rebotes sobre el tendón de Aquiles.",
    "Dolor en el tendón de Aquiles.",
)
SHEETS["Elevación de gemelos sentado"] = _s(
    "Elevación de talones sentado en máquina. Con la rodilla flexionada se trabaja sobre todo el sóleo.",
    [
        "Siéntate en la máquina con las rodillas bajo la almohadilla y la parte delantera de los pies en la plataforma.",
        "Suelta el seguro y baja los talones para estirar los gemelos.",
        "Sube a la punta de los pies lo más alto que puedas.",
        "Pausa 1 segundo arriba.",
        "Baja controlado hasta estirar y repite.",
    ],
    ["Rango completo abajo y arriba.", "Sin rebotes.", "Peso en la parte delantera del pie."],
    ["Rebotar sin estirar abajo.", "Usar un rango corto.", "Cargar peso y soltar la fase de bajada."],
    "Controla la bajada y evita rebotes bruscos en el tendón de Aquiles.",
    "Dolor en el tendón de Aquiles.",
)
# ------------------------------------------------------------------ CORE
SHEETS["Plancha"] = _s(
    "Plancha frontal isométrica sobre antebrazos. Trabaja el core, sobre todo recto abdominal y transverso, y se mide en segundos.",
    [
        "Apoya los antebrazos en el suelo con los codos bajo los hombros y las piernas estiradas.",
        "Apoya la punta de los pies y levanta el cuerpo formando una línea recta de cabeza a talones.",
        "Aprieta abdomen y glúteos y mantén las costillas hacia abajo.",
        "Mira al suelo, cuello neutro, y respira con normalidad.",
        "Mantén el tiempo objetivo sin que la cadera suba ni baje.",
    ],
    ["Aprieta glúteos y abdomen.", "Empuja el suelo con los antebrazos.", "Cuenta los segundos y respira."],
    ["Hundir la lumbar (cadera caída).", "Subir la cadera como una pirámide.", "Contener la respiración."],
    "Para la serie si pierdes la postura o notas dolor lumbar.",
    "Dolor lumbar o de hombro: acorta el tiempo o prueba con las rodillas apoyadas.",
)
SHEETS["Crunch en polea"] = _s(
    "Flexión de columna con polea alta y cuerda. Permite añadir carga progresiva al recto abdominal.",
    [
        "Arrodíllate frente a la polea alta y agarra la cuerda a ambos lados de la cabeza.",
        "Cadera sobre las rodillas y espalda ligeramente redondeada.",
        "Enrolla el tronco llevando los codos hacia las rodillas y acortando la distancia entre costillas y pelvis.",
        "Aprieta el abdomen 1 segundo.",
        "Vuelve controlado sin extender la cadera.",
    ],
    ["El movimiento viene de las costillas hacia la pelvis.", "Cadera quieta.", "Respira al subir y expulsa el aire al bajar."],
    ["Tirar con los brazos y echar el cuerpo adelante.", "Mover las caderas hacia atrás.", "Usar demasiado peso y perder el control."],
    "Mantén la cadera fija; si no sientes el abdomen, baja el peso.",
    "Dolor lumbar o hernia discal en fase aguda.",
)
SHEETS["Crunch en máquina"] = _s(
    "Crunch abdominal en máquina. Trayectoria guiada para trabajar el recto abdominal con carga ajustable.",
    [
        "Ajusta el asiento y siéntate agarrando las asas según el modelo de máquina.",
        "Mantén la espalda pegada y los pies apoyados.",
        "Flexiona el tronco llevando las costillas hacia la pelvis.",
        "Aprieta el abdomen 1 segundo.",
        "Vuelve controlado sin dejar que la pila toque el tope.",
    ],
    ["Enrolla el tronco, no tires de los brazos.", "Respira al volver.", "Cadera pegada al asiento."],
    ["Tirar con los brazos y la cadera.", "Rebotar la pila.", "Usar demasiado peso y acortar el recorrido."],
    "Peso moderado y recorrido controlado.",
    "Dolor lumbar agudo o hernia discal.",
)
SHEETS["Pallof press"] = _s(
    "Press anti-rotación con polea o banda. Trabaja el core aguantando la fuerza que intenta girar el tronco; se mide en repeticiones o segundos de mantenimiento.",
    [
        "Coloca la polea a la altura del pecho y ponte de lado a ella, a un paso, con las dos manos sujetando el asa al pecho.",
        "Pies al ancho de caderas, rodillas ligeramente flexionadas y abdomen firme.",
        "Extiende los brazos al frente sin que el tronco gire hacia la polea.",
        "Mantén 2-3 segundos con los brazos estirados.",
        "Vuelve el asa al pecho de forma controlada y repite; después cambia de lado.",
    ],
    ["Cadera y hombros cuadrados al frente.", "Costillas abajo, abdomen firme.", "Resiste la rotación, no la provoques."],
    ["Dejar que el tronco gire hacia la polea.", "Inclinarse hacia atrás.", "Usar demasiado peso y perder la postura."],
    "Empieza con poco peso para controlar la postura; el ejercicio es de estabilidad, no de fuerza máxima.",
    "Dolor lumbar agudo: reduce la carga y el tiempo de mantenimiento.",
)
SHEETS["Elevación de rodillas"] = _s(
    "Elevación de rodillas colgado de una barra o apoyado en torre de rodillas. Trabaja el recto abdominal y los flexores de cadera.",
    [
        "Cuélgate de una barra con agarre firme o apóyate en una torre con los antebrazos, el cuerpo vertical.",
        "Activa el abdomen y evita balancear el cuerpo.",
        "Sube las rodillas hacia el pecho enrollando la pelvis hacia las costillas.",
        "Aprieta el abdomen 1 segundo arriba.",
        "Baja despacio sin balancearte y repite.",
    ],
    ["Enrolla la pelvis hacia las costillas (retroversión).", "Sin balanceo, movimiento lento.", "Hombros activos, sin encoger el cuello."],
    ["Balancear las piernas con impulso.", "Subir solo con los flexores de cadera sin enrollar la pelvis.", "Encoger los hombros hacia las orejas."],
    "Si te cuelgas de una barra, activa los hombros para protegerlos y evita tirones del agarre.",
    "Dolor de hombro o lumbar al colgarse o al enrollar la pelvis.",
)
