# Copiar a CT105 y ejecutar contra data/entrenamiento.db
import json, sqlite3

DATA = {
"Curl martillo": {
  "instructions": "Agarre neutro (palmas enfrentadas). Flexión de codo sin balanceo.",
  "steps": ["Mancuernas a los lados, pulgares arriba.", "Flexiona sin adelantar el codo.", "Aprieta arriba.", "Baja completo."],
  "technical_cues": ["Hombros bajos.", "El braquial trabaja más que en el curl clásico."],
  "common_mistakes": ["Balancear el tronco.", "Girar la muñeca a mitad de recorrido."],
  "safety_notes": "Codos estables.",
  "contraindications": "Dolor de codo: baja carga.",
},
"Curl de bíceps en polea": {
  "instructions": "Polea baja. Flexión de codo con tensión continua.",
  "steps": ["Barra o cuerda en polea baja.", "Codos fijos al costado.", "Flexiona hasta el pecho.", "Baja sin perder el cable tenso."],
  "technical_cues": ["No dejes que el peso descanse abajo.", "Costillas quietas."],
  "common_mistakes": ["Acercarse demasiado a la polea.", "Usar la lumbar."],
  "safety_notes": "Tensión continua.",
  "contraindications": "Molestia de codo: cambia a mancuerna.",
},
"Curl inclinado con mancuernas": {
  "instructions": "Banco 45–60°. Brazos caídos. Gran estiramiento de bíceps.",
  "steps": ["Siéntate inclinado, omóplatos en el banco.", "Deja colgar los brazos.", "Flexiona sin despegar la espalda.", "Baja hasta estirar."],
  "technical_cues": ["No encojas el hombro.", "Rango largo abajo."],
  "common_mistakes": ["Sentarse demasiado vertical.", "Empezar el movimiento con un tirón."],
  "safety_notes": "Carga más ligera que el curl de pie.",
  "contraindications": "Pinzamiento de hombro: no fuerces el estiramiento.",
},
"Curl de bíceps en máquina": {
  "instructions": "Apoyo del brazo. Solo flexiona el codo.",
  "steps": ["Ajusta el asiento para que el codo quede en el eje.", "Agarra y flexiona.", "Baja controlado."],
  "technical_cues": ["No despegues los brazos del apoyo."],
  "common_mistakes": ["Asiento demasiado bajo o alto.", "Impulso."],
  "safety_notes": "Evitar balanceos.",
  "contraindications": "Dolor de codo o hombro.",
},
"Pallof press": {
  "instructions": "Anti-rotación. Empujas el mango al frente sin girar el tronco.",
  "steps": ["De lado a la polea, mango al pecho.", "Pies firmes, pelvis quieta.", "Extiende los brazos al frente.", "Aguanta 1–2 s y vuelve."],
  "technical_cues": ["Costillas abajo.", "No dejes que la polea te gire."],
  "common_mistakes": ["Cadera que se adelanta.", "Carga de remo."],
  "safety_notes": "Core rígido, no lumbar arqueada.",
  "contraindications": "Dolor lumbar agudo: para.",
},
"Extensión de cuádriceps": {
  "instructions": "Máquina. Extiende la rodilla con control.",
  "steps": ["Ajusta el rodillo sobre el empeine.", "Espalda pegada.", "Extiende hasta casi bloquear.", "Baja en 2–3 s."],
  "technical_cues": ["No rebotes abajo.", "Aprieta el cuádriceps arriba."],
  "common_mistakes": ["Impulso.", "Asiento que deja la rodilla fuera del eje."],
  "safety_notes": "Rango cómodo.",
  "contraindications": "Dolor anterior de rodilla: acorta el rango.",
},
"Hack squat": {
  "instructions": "Máquina inclinada. Sentadilla guiada.",
  "steps": ["Espalda y hombros en el respaldo.", "Pies a media plataforma.", "Suelta topes y baja.", "Empuja sin despegar la lumbar."],
  "technical_cues": ["Talones pegados.", "Profundidad que permita pelvis estable."],
  "common_mistakes": ["Rodillas que colapsan.", "Bajar hasta perder el sacro."],
  "safety_notes": "Pelvis estable.",
  "contraindications": "Molestia de rodilla o cadera: acorta rango o usa prensa.",
},
"Prensa unilateral": {
  "instructions": "Una pierna en la plataforma. Mismo criterio que la prensa.",
  "steps": ["Una planta centrada.", "Baja controlado.", "Empuja sin girar la cadera."],
  "technical_cues": ["Cadera cuadrada al respaldo."],
  "common_mistakes": ["Dejar que la pelvis rote.", "Bloquear de golpe."],
  "safety_notes": "Menos carga que a dos piernas.",
  "contraindications": "Igual que prensa.",
},
"Sentadilla goblet": {
  "instructions": "Mancuerna o kettlebell al pecho. Sentadilla profunda controlada.",
  "steps": ["Peso pegado al esternón.", "Pies algo más abiertos que cadera.", "Baja entre las rodillas.", "Sube empujando el suelo."],
  "technical_cues": ["Codos dentro de las rodillas.", "Pecho alto."],
  "common_mistakes": ["Dejar caer el peso adelante.", "Rodillas hacia dentro."],
  "safety_notes": "Útil si la barra no sienta bien.",
  "contraindications": "Dolor de rodilla: reduce profundidad.",
},
"Sentadilla libre": {
  "instructions": "Barra alta o media. Sentadilla con torso estable.",
  "steps": ["Barra sobre trapecio, pies estables.", "Aire y braceo.", "Cadera atrás y abajo.", "Sube sin perder la espalda."],
  "technical_cues": ["Rodillas siguen los pies.", "No despegues los talones."],
  "common_mistakes": ["Buenos días (solo cadera).", "Rodillas que ceden.", "Mirar al techo."],
  "safety_notes": "Profundidad que mantenga lumbar neutra.",
  "contraindications": "Dolor lumbar o de rodilla no controlado.",
},
"Press de hombros en máquina": {
  "instructions": "Empuje vertical guiado.",
  "steps": ["Asiento para que los agarres salgan a la altura de las orejas.", "Empuja arriba.", "Baja hasta el hombro."],
  "technical_cues": ["No arquees la lumbar contra el respaldo."],
  "common_mistakes": ["Asiento demasiado bajo.", "Rebotar abajo."],
  "safety_notes": "Recorrido cómodo.",
  "contraindications": "Pinzamiento: cambia a agarre neutro con mancuernas.",
},
"Press militar con barra": {
  "instructions": "De pie o sentado. Barra desde la clavícula hacia arriba.",
  "steps": ["Barra a la clavícula, agarre un poco más ancho que hombros.", "Empuja arriba pasando cerca de la cara.", "Baja controlado."],
  "technical_cues": ["Glúteo y abdomen firmes.", "Cabeza atrás al pasar la barra."],
  "common_mistakes": ["Impulso excesivo de piernas si es estricta.", "Arco lumbar."],
  "safety_notes": "Mejor sentado si falla el core.",
  "contraindications": "Hombro irritado: agarre neutro.",
},
"Elevaciones laterales en máquina": {
  "instructions": "Brazos a los lados, elevación hasta la línea del hombro.",
  "steps": ["Ajusta almohadillas sobre el brazo, no sobre el codo solo.", "Eleva hasta la horizontal.", "Baja lento."],
  "technical_cues": ["Cuello largo.", "Carga moderada."],
  "common_mistakes": ["Encoger trapecio.", "Usar impulso."],
  "safety_notes": "Carga ligera.",
  "contraindications": "Tensión de cuello: baja peso.",
},
"Elevaciones laterales en polea": {
  "instructions": "Polea baja cruzada o al lado. Elevación lateral con tensión continua.",
  "steps": ["Cable en la mano contraria o la misma.", "Eleva hasta el hombro.", "Baja sin perder tensión."],
  "technical_cues": ["Codo ligeramente flexionado."],
  "common_mistakes": ["Subir por encima de la oreja.", "Girar el tronco."],
  "safety_notes": "Ideal para no balancear.",
  "contraindications": "Igual que laterales con mancuerna.",
},
"Pájaros en máquina": {
  "instructions": "Apertura posterior. Deltoides posterior.",
  "steps": ["Pecho al apoyo.", "Abre los brazos atrás.", "Aprieta 1 s.", "Vuelve lento."],
  "technical_cues": ["No encoger el cuello.", "Piensa en separar los agarres, no en tirar."],
  "common_mistakes": ["Carga de remo.", "Usar lumbar."],
  "safety_notes": "Peso ligero.",
  "contraindications": "Molestia de hombro: reduce rango.",
},
"Jalón al pecho agarre amplio": {
  "instructions": "Agarre prono ancho. Tiro al pecho alto.",
  "steps": ["Muslos bloqueados.", "Inicia con dorsal.", "Barra al pecho alto.", "Sube controlado."],
  "technical_cues": ["Pecho al encuentro de la barra.", "No detrás de la nuca."],
  "common_mistakes": ["Balanceo.", "Solo flexión de brazos."],
  "safety_notes": "Nunca detrás de la cabeza.",
  "contraindications": "Hombro sensible: agarre neutro.",
},
"Jalón unilateral en polea": {
  "instructions": "Un brazo. Tiro hacia la costilla.",
  "steps": ["Agarre a un mango.", "Tira el codo a la cadera.", "Estira arriba sin perder el hombro bajo."],
  "technical_cues": ["El tronco no gira de más."],
  "common_mistakes": ["Convertirlo en un crunch lateral."],
  "safety_notes": "Control del torso.",
  "contraindications": "Igual que jalón.",
},
"Pullover en polea": {
  "instructions": "De pie, polea alta. Llevas el mango a los muslos con brazos casi rectos.",
  "steps": ["Un paso atrás, torso inclinado 20°.", "Brazos largos.", "Lleva el mango a los muslos apretando dorsal.", "Vuelve con control."],
  "technical_cues": ["Codos semifijos.", "No conviertas en press de tríceps."],
  "common_mistakes": ["Doblar mucho el codo.", "Usar solo el pecho."],
  "safety_notes": "Hombros empaquetados.",
  "contraindications": "Molestia anterior de hombro: para.",
},
"Remo unilateral en polea": {
  "instructions": "Un mango. Tiro a la cadera.",
  "steps": ["Posición de split suave.", "Tira el mango a la cadera.", "Estira adelante sin redondear."],
  "technical_cues": ["Codo raso."],
  "common_mistakes": ["Girar todo el tronco."],
  "safety_notes": "Torso estable.",
  "contraindications": "Dolor de hombro o lumbar.",
},
"Remo en máquina": {
  "instructions": "Pecho o asiento según máquina. Tiro horizontal.",
  "steps": ["Ajusta el asiento al pecho.", "Tira atrás.", "Aprieta omóplatos.", "Estira."],
  "technical_cues": ["No encoger trapecio alto."],
  "common_mistakes": ["Recorrido corto.", "Impulso de lumbar."],
  "safety_notes": "Control escapular.",
  "contraindications": "Molestia de hombro.",
},
"Remo sentado en polea": {
  "instructions": "Sentado, cable al ombligo o bajo pecho.",
  "steps": ["Pies en la plataforma, rodillas blandas.", "Tira hacia el abdomen bajo.", "Inclínate mínimo.", "Estira."],
  "technical_cues": ["Pecho alto.", "Hombros lejos de las orejas."],
  "common_mistakes": ["Balanceo de 45°.", "Redondear la lumbar al estirar."],
  "safety_notes": "Espalda neutra.",
  "contraindications": "Lumbar irritable: pecho apoyado.",
},
"Elevación de gemelos de pie": {
  "instructions": "Extensión de tobillo de pie.",
  "steps": ["Antepié en el escalón, talón al aire.", "Baja el talón.", "Sube a la punta.", "Pausa arriba."],
  "technical_cues": ["Rodillas casi extendidas, no bloqueadas de golpe."],
  "common_mistakes": ["Rebotar abajo.", "Usar solo el impulso."],
  "safety_notes": "Rango que no pinche el Aquiles.",
  "contraindications": "Tendón de Aquiles irritado: rango corto.",
},
"Elevación de gemelos sentado": {
  "instructions": "Rodilla flexionada. Más sóleo.",
  "steps": ["Muslos bajo el almohadillado.", "Baja el talón.", "Sube a la punta."],
  "technical_cues": ["Pausa de 1 s arriba."],
  "common_mistakes": ["Recorrido corto.", "Impulso."],
  "safety_notes": "Carga moderada.",
  "contraindications": "Igual que de pie.",
},
"Extensión de cadera en máquina": {
  "instructions": "Empuje de cadera atrás o abajo según máquina.",
  "steps": ["Ajusta el rodillo.", "Extiende la cadera sin arquear lumbar.", "Vuelve lento."],
  "technical_cues": ["Piensa en empujar con el glúteo."],
  "common_mistakes": ["Usar solo la lumbar.", "Rango enorme."],
  "safety_notes": "Pelvis controlada.",
  "contraindications": "Dolor lumbar: hip thrust o patada ligera.",
},
"Hip thrust unilateral": {
  "instructions": "Una pierna. Misma línea que el hip thrust.",
  "steps": ["Una planta en el suelo.", "Extiende la cadera.", "Baja sin perder el banco."],
  "technical_cues": ["Cadera a la misma altura."],
  "common_mistakes": ["Rotar la pelvis.", "Empujar con la lumbar."],
  "safety_notes": "Menos carga.",
  "contraindications": "Igual que hip thrust.",
},
"Patada de glúteo en polea": {
  "instructions": "Tobillera. Extensión de cadera atrás.",
  "steps": ["Cara a la polea, torso estable.", "Lleva el pie atrás sin arquear.", "Vuelve sin perder tensión."],
  "technical_cues": ["Rodilla semiflexionada."],
  "common_mistakes": ["Coger impulso con el tronco.", "Lumbar en hiperlordosis."],
  "safety_notes": "Core firme.",
  "contraindications": "Lumbar sensible.",
},
"Abducción de cadera en máquina": {
  "instructions": "Abre las rodillas contra la resistencia.",
  "steps": ["Espalda pegada.", "Abre.", "Cierra controlado."],
  "technical_cues": ["No despegues el sacro."],
  "common_mistakes": ["Carga de press.", "Rebotar."],
  "safety_notes": "Rango cómodo.",
  "contraindications": "Pinzamiento de cadera: reduce amplitud.",
},
"Step-up": {
  "instructions": "Sube a un cajón con una pierna. Baja controlado.",
  "steps": ["Cajón a la altura de la tibia o un poco menos.", "Pie entero arriba.", "Sube sin impulsarte con la de abajo.", "Baja en 2 s."],
  "technical_cues": ["Rodilla delante sigue el pie."],
  "common_mistakes": ["Cajón demasiado alto.", "Empujar con la pierna de abajo."],
  "safety_notes": "Empieza bajo.",
  "contraindications": "Inestabilidad de rodilla: zancada estática o prensa uni.",
},
"Curl femoral tumbado": {
  "instructions": "Boca abajo. Talones a glúteos.",
  "steps": ["Caderas pegadas al banco.", "Flexiona.", "Baja lento."],
  "technical_cues": ["No despegues la cadera."],
  "common_mistakes": ["Impulso.", "Arquear lumbar."],
  "safety_notes": "Sin tirones.",
  "contraindications": "Tirón de isquio: rango corto.",
},
"Peso muerto rumano con mancuernas": {
  "instructions": "Igual que el RDL de barra, con mancuernas a los lados.",
  "steps": ["Mancuernas junto a los muslos.", "Cadera atrás.", "Baja hasta sentir isquio.", "Extiende cadera."],
  "technical_cues": ["Mancuernas pegadas al muslo."],
  "common_mistakes": ["Redondear.", "Doblar demasiado la rodilla."],
  "safety_notes": "Espalda neutra.",
  "contraindications": "Igual que RDL.",
},
"Aperturas de pecho en máquina": {
  "instructions": "Apertura horizontal. Estiramiento de pectoral.",
  "steps": ["Codos semiflexionados.", "Abre hasta estirar sin dolor.", "Cierra apretando el pecho."],
  "technical_cues": ["No bloquees el codo."],
  "common_mistakes": ["Rango excesivo atrás.", "Carga de press."],
  "safety_notes": "Hombros empaquetados.",
  "contraindications": "Pinzamiento: reduce apertura.",
},
"Cruce de poleas": {
  "instructions": "Poleas altas o medias. Cruce al frente o abajo.",
  "steps": ["Un paso adelante.", "Brazos abiertos.", "Cruza hasta juntar las manos.", "Vuelve estirando el pecho."],
  "technical_cues": ["Pecho alto.", "Codos fijos en un ángulo."],
  "common_mistakes": ["Empujar con tríceps solo.", "Balanceo."],
  "safety_notes": "Tensión continua.",
  "contraindications": "Hombro sensible: cruce más bajo.",
},
"Press banca con mancuernas": {
  "instructions": "Como el press de barra, con más libertad de muñeca.",
  "steps": ["Omóplatos juntos.", "Baja a los costados del pecho.", "Empuja arriba."],
  "technical_cues": ["Muñecas encima de los codos."],
  "common_mistakes": ["Bajar en cruz.", "Chocar las mancuernas con golpe."],
  "safety_notes": "Control al recoger las mancuernas.",
  "contraindications": "Igual que banca.",
},
"Press convergente de pecho": {
  "instructions": "Máquina convergente. Empuje al frente.",
  "steps": ["Asiento para que los agarres salgan a media pecera.", "Empuja.", "Vuelve sin perder el pecho."],
  "technical_cues": ["Omóplatos estables."],
  "common_mistakes": ["Asiento alto (más hombro).", "Rebote."],
  "safety_notes": "Recorrido cómodo.",
  "contraindications": "Molestia de hombro.",
},
"Press inclinado en máquina": {
  "instructions": "Empuje en banco inclinado guiado.",
  "steps": ["Asiento a la altura del pecho alto.", "Empuja.", "Baja controlado."],
  "technical_cues": ["No despegues la espalda."],
  "common_mistakes": ["Asiento mal ajustado."],
  "safety_notes": "Igual que inclinado.",
  "contraindications": "Igual que inclinado.",
},
"Crunch en máquina": {
  "instructions": "Flexión de tronco contra resistencia.",
  "steps": ["Agarra y flexiona costillas hacia pelvis.", "Vuelve sin perder tensión."],
  "technical_cues": ["No tires de cuello."],
  "common_mistakes": ["Usar solo los brazos.", "Rango enorme de lumbar."],
  "safety_notes": "Movimiento corto.",
  "contraindications": "Lumbar aguda: plancha o Pallof.",
},
"Crunch en polea": {
  "instructions": "De rodillas, polea alta. Flexión de costillas.",
  "steps": ["Cuerda detrás de la cabeza o al frente.", "Cierra el abdomen.", "Vuelve."],
  "technical_cues": ["Cadera quieta."],
  "common_mistakes": ["Flexión de cadera (se vuelve jalón de cadera)."],
  "safety_notes": "Core, no cuello.",
  "contraindications": "Igual que crunch máquina.",
},
"Elevación de rodillas": {
  "instructions": "Colgado o apoyado. Rodillas al pecho.",
  "steps": ["Estabiliza el tronco.", "Sube rodillas.", "Baja lento."],
  "technical_cues": ["No balancear."],
  "common_mistakes": ["Impulso de piernas.", "Encoger trapecio."],
  "safety_notes": "Hombros empaquetados si vas colgado.",
  "contraindications": "Hombro o lumbar irritable.",
},
"Extensión de tríceps por encima de la cabeza": {
  "instructions": "Estiramiento largo de tríceps. Mancuerna o cuerda.",
  "steps": ["Codos arriba.", "Baja el peso detrás de la cabeza.", "Extiende."],
  "technical_cues": ["Codos juntos.", "Costillas abajo."],
  "common_mistakes": ["Abrir los codos.", "Arquear lumbar."],
  "safety_notes": "Rango que no pinche el hombro.",
  "contraindications": "Hombro o codo sensibles: polea baja.",
},
"Press francés": {
  "instructions": "Tumbado. Barra o mancuernas. Solo antebrazo.",
  "steps": ["Brazos verticales.", "Baja hacia la frente o detrás de la cabeza.", "Extiende."],
  "technical_cues": ["Codos fijos."],
  "common_mistakes": ["Mover el hombro.", "Abrir en cruz."],
  "safety_notes": "Carga controlada.",
  "contraindications": "Dolor de codo.",
},
}

def main():
    conn = sqlite3.connect("data/entrenamiento.db")
    cols = {r[1] for r in conn.execute("PRAGMA table_info(exercises)")}
    for col in ("steps", "technical_cues", "common_mistakes", "video_url"):
        if col not in cols:
            conn.execute(f"ALTER TABLE exercises ADD COLUMN {col} TEXT")
    ok = miss = 0
    for name, d in DATA.items():
        cur = conn.execute(
            """UPDATE exercises SET instructions=?, safety_notes=?, contraindications=?,
               steps=?, technical_cues=?, common_mistakes=? WHERE name=?""",
            (
                d["instructions"], d["safety_notes"], d["contraindications"],
                json.dumps(d["steps"], ensure_ascii=False),
                json.dumps(d["technical_cues"], ensure_ascii=False),
                json.dumps(d["common_mistakes"], ensure_ascii=False),
                name,
            ),
        )
        if cur.rowcount:
            print("ok", name)
            ok += 1
        else:
            print("NO ESTÁ", name)
            miss += 1
    conn.commit()
    rows = conn.execute(
        "SELECT COUNT(*) FROM exercises WHERE is_active=1 AND steps IS NOT NULL AND steps != '' AND steps != '[]'"
    ).fetchone()[0]
    print(f"nuevos ok={ok} no_encontrados={miss} con_pasos={rows}")
    conn.close()

if __name__ == "__main__":
    main()
