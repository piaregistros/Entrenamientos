"""Fichas en español de los ejercicios nuevos de casa (Fase 12).

Se fusionan con ``SHEETS`` en ``exercise_sheets_data``. Clave = nombre exacto
del ejercicio en ``casa_catalog.CASA_EXERCISES``.
"""

def _s(instructions, steps, cues, mistakes, safety, contra):
    return {
        "instructions": instructions,
        "steps": steps,
        "technical_cues": cues,
        "common_mistakes": mistakes,
        "safety_notes": safety,
        "contraindications": contra,
    }


CASA_SHEETS = {}

CASA_SHEETS['Press landmine'] = _s(
    'Empuje diagonal con un extremo de la barra anclado en el landmine (o en una esquina). Más amable con el hombro que el press militar porque la trayectoria no es vertical pura.',
    [
        'Ancla un extremo de la barra en el landmine (o en una esquina protegida) y carga el otro.',
        'Colócate de pie o con una rodilla al suelo, agarra el extremo a la altura del hombro, core activo.',
        'Empuja la barra arriba y al frente siguiendo su ángulo natural, sin encoger el hombro.',
        'Estira el brazo arriba y baja de forma controlada hasta el hombro.',
        'Termina la serie y cambia de brazo.',
    ],
    ['Costillas abajo, abdomen apretado.', 'El brazo y el tronco forman una línea al final.', 'No arquees la lumbar para llegar más alto.'],
    ['Encoger el hombro hacia la oreja.', 'Arquear la espalda baja.', 'Dejar caer la barra sin control.'],
    'Si no tienes base landmine, protege la esquina y la barra con una toalla. Empieza con poco peso para pillar la trayectoria.',
    'Dolor de hombro al ir por encima de la cabeza: acorta el recorrido o usa la variante de rodilla al suelo.',
)

CASA_SHEETS['Remo landmine (Meadows)'] = _s(
    'Remo unilateral con la barra anclada en el landmine, agarrada por el extremo (remo Meadows). Trabaja dorsal y espalda media con un rango largo y un buen estiramiento.',
    [
        'Ancla la barra y colócate de lado, pies firmes, cadera atrás y tronco inclinado casi paralelo al suelo.',
        'Agarra el extremo de la barra con una mano (puedes usar una agarre o el mismo mango).',
        'Tira del codo hacia atrás, cerca del cuerpo, hasta que la mano quede a la altura de la cadera.',
        'Aprieta la espalda 1 segundo y baja controlado hasta estirar el dorsal.',
        'Termina las repeticiones y cambia de lado.',
    ],
    ['Espalda neutra, no redondees la lumbar.', 'El codo guía el movimiento, no el bíceps.', 'El tronco permanece quieto: no gires al tirar.'],
    ['Incorporarse en cada repetición.', 'Abrir el codo en cruz.', 'Usar demasiado peso y recortar el estiramiento.'],
    'Apoya la mano libre en el muslo si te falta estabilidad. Carga los discos con cuidado: el extremo de la barra queda cerca del suelo.',
    'Molestias lumbares: reduce la inclinación del tronco o cambia a remo con mancuerna apoyando la rodilla en un banco.',
)

CASA_SHEETS['Sentadilla landmine'] = _s(
    'Sentadilla con la barra anclada, sostenida a la altura del pecho. Es más fácil de aprender que la sentadilla trasera y carga bien cuádriceps y glúteos.',
    [
        'Ancla la barra y sujeta el extremo con las dos manos a la altura del pecho, codos abajo.',
        'Pies a la anchura de los hombros o un poco más, puntas ligeramente afuera.',
        'Baja sentándote entre los talones, pecho alto, hasta que los muslos queden al menos paralelos al suelo.',
        'Empuja el suelo con los pies y vuelve arriba sin que te lleve la barra hacia delante.',
        'Mantén los talones plantados durante toda la serie.',
    ],
    ['Pecho alto y codos cerca del cuerpo.', 'Las rodillas siguen la línea de los pies.', 'El peso se reparte en todo el pie, no solo en las puntas.'],
    ['Dejar que la barra te empuje y te desequilibre hacia delante.', 'Levantar los talones.', 'Redondear la lumbar abajo.'],
    'Empieza ligero para pillar el equilibrio. Si el landmine está bajo, da un pequeño paso atrás para que la barra no te empuje.',
    'Dolor de rodilla en el fondo: acorta el recorrido o abre un poco más la postura.',
)

CASA_SHEETS['Peso muerto con trap bar'] = _s(
    'Peso muerto con barra hexagonal (bear bar / trap bar). La carga queda en línea con el cuerpo, con más trabajo de cuádriceps y menos estrés lumbar que el peso muerto convencional.',
    [
        'Métete dentro de la barra, pies a la anchura de la cadera, agarra las asas (las bajas si hay dos alturas).',
        'Baja la cadera, pecho alto, escápulas abajo, brazos estirados.',
        'Empuja el suelo con los pies y estira cadera y rodillas a la vez hasta quedar de pie.',
        'Aprieta glúteos arriba, sin inclinarte atrás.',
        'Baja la barra de forma controlada, dejando que las rodillas se adelanten un poco al llegar abajo.',
    ],
    ['La espalda queda neutra de principio a fin.', 'Empuja el suelo, no tires de la barra con los brazos.', 'La cadera y las rodillas se estiran juntas.'],
    ['Redondear la lumbar al despegar.', 'Estirar las rodillas antes que la cadera (o al revés).', 'Encoger el cuello o mirar al techo con agresividad.'],
    'Usa straps si el agarre falla antes que las piernas. Asegúrate de que hay espacio libre alrededor de la jaula.',
    'Dolor lumbar agudo: baja el peso, revisa la postura o cambia a un rumano con menos carga.',
)

CASA_SHEETS['Press inclinado con barra'] = _s(
    'Empuje de pectoral superior con barra en banco inclinado (unos 30 grados). Usa los seguros de la jaula o un observador.',
    [
        'Inclina el banco unos 30 grados y colócalo en la jaula, con los seguros a una altura que te proteja.',
        'Túmbate, pies firmes, escápulas juntas y abajo, ojos bajo la barra.',
        'Agarra la barra algo más ancha que los hombros, despéjala y bájala de forma controlada a la parte alta del pecho.',
        'Empuja hacia arriba hasta casi estirar los brazos, sin despegar la espalda del banco.',
        'Al terminar, deja la barra en los soportes con control.',
    ],
    ['Inclinación de 30°, no de 45° o más (si no, trabaja más el hombro).', 'Codos a unos 45-60° del tronco.', 'Muñecas apiladas sobre los codos.'],
    ['Inclinar el banco demasiado y convertir el ejercicio en un press militar tumbado.', 'Rebotar la barra en el pecho.', 'Despegar los glúteos del banco.'],
    'Coloca siempre los seguros. Si entrenas solo, no vayas al fallo absoluto.',
    'Dolor de hombro al bajar: reduce el rango o baja un poco la inclinación.',
)

CASA_SHEETS['Dominadas'] = _s(
    'Tracción vertical con el peso del cuerpo, agarre prono y un poco más ancho que los hombros. Si no llegas a las repeticiones, usa una goma de asistencia; si te sobran, añade lastre.',
    [
        'Cuelga de la barra con las manos en pronación, algo más anchas que los hombros, cuerpo tenso.',
        'Tira de los codos hacia abajo y atrás hasta que la barbilla rebase la barra.',
        'Aprieta la espalda 1 segundo arriba, sin encogerte.',
        'Baja de forma controlada hasta estirar los brazos.',
        'Evita balancearte: si hace falta, flexiona un poco las rodillas y cruza los pies.',
    ],
    ['Pecho hacia la barra, no la barbilla hacia delante.', 'Hombros abajo, lejos de las orejas.', 'Abdomen y glúteos activos para no balancear.'],
    ['Llegar arriba con un tirón de cadera (kipping) si no es lo que buscas.', 'Encoger el cuello.', 'Bajar en caída libre.'],
    'Si aún no puedes hacer el mínimo, únete una goma a un pie o a la rodilla. No sueltes de golpe al fallar.',
    'Dolor de hombro o codo: prueba el agarre neutro, que suele sentar mejor.',
)

CASA_SHEETS['Dominadas agarre neutro'] = _s(
    'Tracción vertical con agarre neutro (palmas enfrentadas). Suele ser más cómoda para hombros y codos que las dominadas pronas.',
    [
        'Cuelga de las asas paralelas, palmas enfrentadas, brazos estirados y cuerpo tenso.',
        'Tira de los codos hacia abajo y atrás hasta que la barbilla rebase las asas.',
        'Aprieta la espalda 1 segundo.',
        'Baja controlado hasta la extensión de los brazos.',
        'Mantén las piernas quietas, sin balanceo.',
    ],
    ['Pecho alto, hombros lejos de las orejas.', 'Los codos se mantienen más cerca del cuerpo que en el agarre amplio.', 'Bajada de 2-3 segundos.'],
    ['Encoger los trapecios.', 'Cortar el recorrido arriba o abajo.', 'Balancear las piernas para ganar inercia.'],
    'Usa goma de asistencia o lastre según te falten o te sobren repeticiones. Los straps ayudan si el agarre falla.',
    'Molestias de codo: no bloquees de golpe abajo y revisa que no te balanceas.',
)

CASA_SHEETS['Fondos en paralelas'] = _s(
    'Empuje de pecho y tríceps en las barras de fondos. Inclina un poco el tronco para cargar más el pectoral; más erguido, más tríceps.',
    [
        'Sujétate a las paralelas con los brazos estirados, hombros abajo, pecho alto.',
        'Inclina un poco el tronco hacia delante y baja flexionando los codos hasta que los hombros queden algo por debajo de los codos.',
        'Empuja para volver arriba sin encogerte.',
        'Mantén las piernas ligeramente flexionadas y el cuerpo tenso.',
        'Si no llegas al mínimo, usa una goma de asistencia o acorta el recorrido.',
    ],
    ['Hombros abajo, lejos de las orejas.', 'Los codos se mantienen relativamente cerca del cuerpo.', 'No rebotes en el fondo.'],
    ['Bajar demasiado y cargar el hombro en un estiramiento agresivo.', 'Encoger el cuello.', 'Balancear las piernas.'],
    'Empieza con el recorrido que controles. El lastre se añade con un cinturón cuando ya haces el máximo de reps con holgura.',
    'Dolor anterior de hombro: acorta la bajada o cambia a press banca / landmine.',
)

CASA_SHEETS['Remo invertido en TRX'] = _s(
    'Remo con el peso del cuerpo en cintas de suspensión. Cuanto más horizontal esté el cuerpo, más difícil es el ejercicio.',
    [
        'Ancla el TRX de forma segura (en la jaula) y agarra las asas, cuerpo en línea de cabeza a talones.',
        'Cuélgate con los brazos estirados, escápulas activas, abdomen tenso.',
        'Tira del pecho hacia las asas, juntando los omoplatos.',
        'Baja de forma controlada hasta estirar los brazos, sin hundir la cadera.',
        'Para facilitar, acerca los pies al punto de anclaje (más vertical); para endurecer, atrévete a quedar más horizontal.',
    ],
    ['Cuerpo en tabla: no dejes caer la cadera ni la subas.', 'Los codos pasan cerca del cuerpo.', 'El cuello queda alineado con la espalda.'],
    ['Encoger los hombros hacia las orejas.', 'Usar solo los brazos y no la espalda.', 'Dejar que la lumbar se hunda.'],
    'Comprueba que el anclaje del TRX aguanta tu peso antes de la primera serie.',
    'Molestias de hombro o muñeca: ajusta la altura de las asas o el ángulo del cuerpo.',
)

CASA_SHEETS['Swing con kettlebell'] = _s(
    'Bisagra de cadera explosiva con kettlebell (swing ruso: la campana llega a la altura del pecho, no por encima de la cabeza). Es el remate de Casa B.',
    [
        'Coloca la kettlebell un poco por delante, pies un poco más anchos que la cadera.',
        'Agarra el asa con las dos manos, espalda neutra, y « hikéa » la campana entre las piernas.',
        'Estira la cadera de un golpe seco (como un empujón de cadera) y deja que la kettlebell suba hasta la altura del pecho.',
        'Los brazos van relajados: no es un front raise.',
        'Deja que la campana vuelva entre las piernas y encadena el siguiente hip drive.',
    ],
    ['La potencia sale de la cadera, no de los brazos.', 'Costillas abajo, no arquees la lumbar arriba.', 'Al final, el cuerpo queda en tabla, no en hiperextensión.'],
    ['Levantar la kettlebell con los hombros (un press o un raise).', 'Redondear la lumbar en el hiké.', 'Subir la campana por encima de la cabeza (swing americano) si aún no controlas el ruso.'],
    'Empieza con una kettlebell ligera para pillar el ritmo. Asegúrate de tener espacio libre delante y detrás.',
    'Dolor lumbar: para, revisa la bisagra (cadera atrás, tibia vertical) y baja de peso.',
)

CASA_SHEETS['Sentadilla goblet con kettlebell'] = _s(
    'Sentadilla sosteniendo una kettlebell pegada al pecho. Sirve como alternativa a la sentadilla goblet con mancuerna y encaja con los pesos fijos de las kettlebells.',
    [
        'Sujeta la kettlebell por el asa o por los «cuernos», pegada al pecho, codos abajo.',
        'Pies a la anchura de los hombros o un poco más, puntas ligeramente afuera.',
        'Baja entre los talones, pecho alto, hasta que los codos pasen por dentro de las rodillas.',
        'Empuja el suelo y vuelve arriba sin perder la kettlebell pegada al pecho.',
        'Mantén los talones plantados.',
    ],
    ['La kettlebell permanece pegada al esternón.', 'Las rodillas siguen la línea de los pies.', 'Respira arriba y aguanta el aire al bajar si vas pesado.'],
    ['Inclinar el tronco hacia delante y despegar los talones.', 'Dejar que los codos se abran y se te escape la campana.', 'Redondear la lumbar en el fondo.'],
    'Si el peso siguiente de kettlebell se hace largo, quédate más repeticiones en el actual (doble progresión).',
    'Dolor de rodilla o muñeca: cambia la forma de agarrar (cuernos en vez de asa) o acorta el fondo.',
)

CASA_SHEETS['Press de hombro con kettlebell'] = _s(
    'Empuje vertical de un brazo con kettlebell, en posición de rack (la campana apoyada en el antebrazo). El core trabaja para no inclinarte.',
    [
        'Lleva la kettlebell a la posición de rack: campana en el antebrazo, muñeca recta, codo cerca del cuerpo.',
        'Pies firmes, abdomen apretado, costillas abajo.',
        'Empuja la kettlebell arriba hasta estirar el brazo, junto a la cabeza, sin inclinarte al lado contrario.',
        'Baja de forma controlada hasta el rack.',
        'Termina el lado y cambia de brazo. El peso que apuntas es el de esa kettlebell (una). ',
    ],
    ['Muñeca recta, no doblada hacia atrás.', 'Glúteos y abdomen activos para no arquear la lumbar.', 'El brazo termina junto a la oreja, no delante.'],
    ['Inclinar el tronco para ayudar el press.', 'Encoger el hombro arriba.', 'Empezar el press con la campana suelta, fuera del rack.'],
    'Aprende primero a limpiar la kettlebell al rack con poco peso. Si te falta movilidad, prueba el press landmine.',
    'Dolor de hombro o muñeca: reduce el peso o cambia a landmine.',
)

CASA_SHEETS['Extensión de tríceps en TRX'] = _s(
    'Extensión de codo con el peso del cuerpo en el TRX. Cuanto más horizontal, más difícil.',
    [
        'Agarra las asas con los brazos estirados a la altura de la frente, cuerpo en línea.',
        'Dobla solo los codos y deja que las manos se acerquen a la frente, sin hundir la cadera.',
        'Estira los brazos para volver a la posición inicial.',
        'Mantén los codos a la misma anchura, sin que se abran a los lados.',
        'Acerca o aleja los pies del anclaje para regular la dificultad.',
    ],
    ['Solo se mueven los codos; hombros y tronco quedan fijos.', 'Cuerpo en tabla.', 'Bajada controlada, sin dejar caer la cabeza entre los brazos de golpe.'],
    ['Abrir los codos en cruz.', 'Hundir la cadera.', 'Acercar las manos a la cara moviendo los hombros, no los codos.'],
    'Comprueba el anclaje. Si te resulta muy exigente, ponte más vertical.',
    'Molestias de codo: reduce el rango o cambia a la extensión con goma.',
)

CASA_SHEETS['Extensión de tríceps con goma'] = _s(
    'Extensión de codo con una goma anclada arriba (en la jaula). Sustituye a la extensión en polea cuando entrenas en casa.',
    [
        'Ancla la goma en un punto alto de la jaula y agárrala con las dos manos, codos pegados al cuerpo.',
        'Partiendo con los codos a 90° o un poco más cerrados, estira los brazos hacia abajo.',
        'Aprieta el tríceps 1 segundo abajo.',
        'Vuelve de forma controlada sin dejar que los codos se adelanten.',
        'Si la goma queda floja, acórtata (hárdale un nudo o acércate al anclaje) o usa una más firme.',
    ],
    ['Codos fijos junto a las costillas.', 'Muñecas neutras.', 'El movimiento es solo de extensión de codo.'],
    ['Balancear el tronco para rematar.', 'Abrir los codos.', 'Usar una goma tan ligera que no haya tensión arriba.'],
    'Ancla la goma en un punto sólido de la jaula, no en un disco suelto.',
    'Dolor de codo: no bloquees de golpe y reduce la tensión de la goma.',
)

CASA_SHEETS['Face pull con goma'] = _s(
    'Tracción a la cara con goma anclada a la altura de la cabeza o un poco más arriba. Cuida el deltoides posterior y la espalda alta, igual que el face pull de polea.',
    [
        'Ancla la goma a la altura de la cara y agárrala con las dos manos, pulgares hacia ti.',
        'Da un paso atrás hasta que haya tensión en la goma, con los brazos estirados al frente.',
        'Tira hacia la cara abriendo los codos a la altura de los hombros, y rota las manos atrás (como un «doble bíceps» corto).',
        'Aprieta omóplatos y deltoides posterior 1 segundo.',
        'Vuelve controlado sin perder la tensión.',
    ],
    ['Codos altos, a la altura de los hombros.', 'No encogas el cuello.', 'La goma debe mantener tensión al final del recorrido.'],
    ['Convertirlo en un remo bajo (codos pegados a las costillas).', 'Usar tanto cuerpo que el ejercicio se vuelve un balanceo.', 'La goma floja al final.'],
    'Ancla la goma a la jaula, a la altura de la cara. Si se queda corta, da medio paso atrás, no tires desde los pies inestables.',
    'Molestias de hombro: baja un poco la altura del anclaje y no forces la rotación final.',
)

CASA_SHEETS['Salto al cajón'] = _s(
    'Salto pliométrico al cajón. Sirve como remate; no hace falta cargar peso. Elige una altura a la que llegues cómodo y aterrices suave.',
    [
        'Colócate frente al cajón, pies a la anchura de la cadera, a un cuarto de paso de distancia.',
        'Flexiona un poco cadera y rodillas y balancea los brazos atrás.',
        'Salta al cajón y aterriza con los dos pies a la vez, rodillas semiflexionadas, pecho alto.',
        'Ponte de pie arriba y baja con un paso atrás (no saltes hacia atrás si el cajón es alto).',
        'Para y recomponte entre saltos si pierdes calidad.',
    ],
    ['Aterriza suave, no de rígido.', 'Mira el cajón, no te lances de lejos.', 'Extiende cadera, rodillas y tobillos al despegar.'],
    ['Elegir un cajón demasiado alto y aterrizar de cuclillas profundas e inestables.', 'Bajar de un salto hacia atrás.', 'Dejar que las rodillas se vayan hacia dentro al aterrizar.'],
    'Empieza por el lado bajo del cajón. Deja espacio libre alrededor y comprueba que el cajón no resbala.',
    'Molestias de rodilla, tendón de Aquiles o si no controlas el aterrizaje: cambia a step-up o omite el remate.',
)

CASA_SHEETS['Cuerda de combate'] = _s(
    'Ondas con la cuerda de combate, por tiempo. Es un remate de acondicionamiento para hombros, antebrazos y core. Apunta los segundos de cada serie.',
    [
        'Colócate con los pies firmes, rodillas semiflexionadas, una punta de la cuerda en cada mano.',
        'Mantén el abdomen tenso y genera ondas alternas (un brazo sube mientras el otro baja) o simultáneas.',
        'Las ondas deben llegar cerca del anclaje, no quedarse a medio camino.',
        'Respira de forma continua: no aguantes la respiración.',
        'Al terminar el tiempo, deja la cuerda y descansa.',
    ],
    ['El movimiento sale de los hombros y el core, no solo de las muñecas.', 'Pecho alto, no te encorves.', 'Ritmo constante mejor que un sprint que se muere a los 10 s.'],
    ['Ponerse rígido y encoger el cuello.', 'Golpear el suelo con las puntas de forma descontrolada.', 'Enderezar las rodillas y cargar la lumbar.'],
    'Asegúrate de que la cuerda está bien anclada y de que no hay nadie en su radio. El suelo no debe ser resbaladizo.',
    'Molestias de hombro o lumbar: reduce el tiempo o la amplitud de las ondas.',
)

CASA_SHEETS['Remo ergómetro'] = _s(
    'Remo en máquina de remo (ergómetro), por tiempo. Es el remate opcional de Casa A. Apunta los segundos de la serie (5-8 min). Resistencia media (unas 5-6 en un Concept2).',
    [
        'Ajusta el reposapiés (correas a la altura del metatarso) y agarra el mango.',
        'La palada tiene tres tiempos: piernas, tronco y brazos al tirar; al volver, brazos, tronco y piernas.',
        'Mantén la espalda neutra, hombros abajo, y no encoges al final del tiro.',
        'Busca un ritmo constante (unas 22-26 paladas por minuto) más que un sprint.',
        'Al terminar el tiempo, suelta el mango con control y relaja los pies.',
    ],
    ['Las piernas hacen la mayor parte del trabajo.', 'No despegues los talones al final ni redondees la lumbar al recoger.', 'El mango llega al cuerpo a la altura de las costillas bajas, no al cuello.'],
    ['Tirar solo con la espalda y los brazos, con las piernas flojas.', 'Abrir los codos en cruz.', 'Dar paladas demasiado largas y perder la postura.'],
    'Si no tienes cuentatiempos a la vista, usa el reloj de la app o el del ergómetro. Hidrátate si hace calor en casa.',
    'Dolor lumbar: reduce el alcance hacia delante y revisa que no redondeas la espalda.',
)

CASA_SHEETS['Paseo del granjero con kettlebells'] = _s(
    'Caminar con una kettlebell pesada en cada mano, tronco erguido. Es el remate de Casa C; se apunta el tiempo (30-45 s). Si no tienes un par igual, usa las dos más cercanas.',
    [
        'Coloca las dos kettlebells a los lados, bisagra de cadera para agarrarlas y ponte de pie.',
        'Hombros abajo, pecho alto, abdomen apretado, mirada al frente.',
        'Camina con pasos cortos y firmes, sin inclinarte a un lado.',
        'Al terminar el tiempo (o la distancia), deja las kettlebells con la misma bisagra, no las sueltes de pie.',
        'Si se te acaba el espacio, date la vuelta con cuidado y sigue.',
    ],
    ['Costillas abajo, no arquees la lumbar.', 'Las kettlebells pegan a los muslos, no se balancean.', 'Aprieta el asa como si quisieras romperla.'],
    ['Inclinarte hacia el lado de la kettlebell más pesada.', 'Encoger los hombros a las orejas.', 'Soltar las campanas en el último paso, de cualquier manera.'],
    'Despeja un pasillo. Usa straps solo si el agarre limita mucho antes que el core. El peso que apuntas es el de UNA kettlebell (o indica las dos en la nota si son distintas).',
    'Molestias lumbares o de agarre agudo: reduce el tiempo o el peso.',
)

CASA_SHEETS['Elevación de piernas colgado'] = _s(
    'Flexión de cadera colgado de la barra, con las piernas lo más estiradas que puedas. Más exigente que la elevación de rodillas.',
    [
        'Cuelga de la barra (agarre prono o neutro), hombros activos (no te cuelgues muerto), cuerpo quieto.',
        'Con las piernas estiradas (o algo flexionadas si te falta control), súbelas hasta al menos la horizontal.',
        'Si puedes, acerca los pies a la barra sin balancearte.',
        'Baja de forma controlada, sin dejar que el cuerpo se convierta en un péndulo.',
        'Si el agarre falla, usa straps o termina la serie en elevación de rodillas.',
    ],
    ['El movimiento sale del abdomen y los flexores de cadera, no de un balanceo.', 'Hombros abajo, lejos de las orejas.', 'Bajada de 2-3 segundos.'],
    ['Usar inercia y adelantar la lumbar.', 'Encoger solo las rodillas y no subir la cadera.', 'Soltarte de golpe al fallar el agarre.'],
    'Asegúrate de que no hay nadie debajo. Si aún no controlas las piernas estiradas, quédate en elevación de rodillas.',
    'Dolor de hombro o lumbar en el descenso: reduce el rango o flexiona las rodillas.',
)

CASA_SHEETS['Elevación de gemelos en jaula'] = _s(
    'Elevación de talones de pie, con la barra en la espalda, sobre un escalón o el disco. Sustituye a la máquina de gemelos de pie.',
    [
        'Coloca la barra en la jaula a la altura de la sentadilla y un disco o un escalón firme bajo los metatarsos.',
        'Carga la barra sobre los trapecios, como en una sentadilla, y colócate en el borde con los talones al aire.',
        'Baja el talón hasta un estiramiento cómodo del gemelo.',
        'Sube hasta ponerte de puntillas y aprieta 1 segundo.',
        'Haz el movimiento a dos piernas; si te sobra control, puedes hacerlo a una.',
    ],
    ['Rodillas quietas, casi estiradas pero no bloqueadas de golpe.', 'El peso cae sobre el metatarso, no sobre los dedos torcidos.', 'Bajada lenta.'],
    ['Rebotar en el estiramiento.', 'Doblar las rodillas y convertir el ejercicio en un cuarto de sentadilla.', 'Poner un apoyo inestable.'],
    'Usa los seguros de la jaula. El escalón o el disco deben estar inmóviles.',
    'Molestias de Aquiles: reduce el estiramiento de la bajada y el peso.',
)

CASA_SHEETS['Remo con barra'] = _s(
    'Remo con barra de pie, tronco inclinado (remo Pendlay o remo clásico, según prefieras parar o no la barra en el suelo). Tracción horizontal pesada para casa.',
    [
        'Pies a la anchura de la cadera, bisagra de cadera hasta dejar el tronco casi paralelo al suelo, espalda neutra.',
        'Agarra la barra (prono, un poco más ancha que los hombros) con los brazos estirados.',
        'Tira de la barra hacia el abdomen bajo, juntando los omóplatos, con los codos cerca del cuerpo.',
        'Baja controlado hasta estirar los brazos (o hasta el suelo, si haces Pendlay).',
        'El tronco permanece quieto: no uses la lumbar para dar el último tirón.',
    ],
    ['Espalda neutra, pecho alto aunque estés inclinado.', 'La barra viaja pegada a las piernas.', 'Aprieta la espalda arriba, no solo los brazos.'],
    ['Incorporarse en cada repetición.', 'Redondear la lumbar.', 'Tirar hacia el pecho con los codos en cruz, con poco peso de espalda.'],
    'Empieza más ligero que en el peso muerto. Si la lumbar se cansa antes que la espalda, apóyate en un banco (o cambia a remo con mancuerna / landmine).',
    'Dolor lumbar: reduce la inclinación, el peso, o elige remo landmine o TRX.',
)

CASA_SHEETS['Pallof press con goma'] = _s(
    'Press anti-rotación con goma anclada a la altura del pecho. El objetivo es que el tronco no gire, no mover mucho peso.',
    [
        'Ancla la goma a la altura del pecho y colócate de lado, pies firmes, con tensión en la goma.',
        'Sujeta la goma con las dos manos a la altura del esternón.',
        'Estira los brazos al frente y aguanta 1-2 segundos sin dejar que el tronco rote hacia el anclaje.',
        'Vuelve las manos al pecho y repite. Termina el lado y cámbiate.',
        'Si es demasiado fácil, aléjate del anclaje o usa una goma más firme.',
    ],
    ['Caderas y hombros miran al frente, no hacia la goma.', 'Costillas abajo, glúteos activos.', 'Los brazos se estiran, el tronco no se mueve.'],
    ['Girar el tronco al estirar los brazos.', 'Encoger el hombro de la goma.', 'Pies inestables o demasiado juntos.'],
    'Ancla la goma a un pilar de la jaula, no a un objeto que se pueda volcar.',
    'Molestias lumbares: reduce la tensión y comprueba que no arqueas la espalda.',
)
