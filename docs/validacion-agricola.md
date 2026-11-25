# Validación agrícola de AgroEdge IA

**Versión:** 1.0. **Fecha de revisión documental:** 25 de noviembre de 2026.  
**Estado:** documento terminado para revisión y publicación por Sergio Andrés Guerrero Alba.  
**Alcance:** caracterización descriptiva de 40 respuestas y su relación con el propósito de AgroEdge IA. Los resultados corresponden al equipo; publicar este documento no equivale a atribuir a Sergio la aplicación individual de las 40 encuestas.

## 1. Contexto agrícola documentado

AgroEdge IA se desarrolla para el monitoreo agroclimático en Toca, Boyacá. Su documentación técnica plantea que las condiciones del dispositivo dentro de un invernadero y al aire libre pueden diferir del pronóstico municipal. La estación registra temperatura ambiental, humedad relativa del aire y presión atmosférica, y permite consultar esos registros junto con información meteorológica externa [A4, A5].

Las respuestas suministradas sitúan el problema agrícola en cultivos de papa, cebolla y otras hortalizas, y frutales u otros cultivos. También describen decisiones de riego basadas en observación directa, horarios y pronósticos. Esta caracterización corresponde al grupo encuestado. Las fuentes examinadas no permiten establecer la distribución municipal de cultivos, la superficie sembrada, la disponibilidad total de agua ni la representatividad estadística de la muestra.

La finalidad agrícola del sistema es aportar información ambiental para contrastarla con la observación del lote y el criterio agronómico. El proyecto prescinde de sensores de humedad del suelo. La humedad relativa del aire no representa una medición de agua disponible para las raíces. El modelo final clasifica perfiles de exposición de invernadero y exterior; su evaluación no acredita predicción local de lluvia, cálculo de necesidades hídricas ni control automático del riego [A4, A5].

## 2. Instrumento y datos disponibles

El instrumento original es `Encuesta de Validación en Campo - AgroEdge IA.pdf`, de dos páginas. Contiene ocho preguntas cerradas distribuidas en tres bloques. Incluye espacios para fecha, vereda y número de encuesta, y propone su aplicación en campo o mediante Google Forms. La duración inferior a tres minutos es una intención expresada en el instrumento; no se dispone de una medición del tiempo real de aplicación [A2].

| Bloque | Preguntas | Aspectos consultados |
| --- | --- | --- |
| A. Perfil y gestión actual del agua | P1–P3 | Cultivo principal, criterio para decidir el riego y uso de bombeo o reservorio. |
| B. Evidencia del problema | P4–P6 | Riego seguido de lluvia en los últimos seis meses, afectación percibida de costos y confianza en los pronósticos para la vereda. |
| C. Validación de la solución | P7–P8 | Utilidad percibida de un dispositivo local y disposición a probarlo o adquirirlo bajo condiciones de bajo costo y facilidad de uso. |

La fuente numérica es `resultados_encuesta.csv`: 40 registros, un identificador de fila y ocho variables de respuesta. Se comprobaron 40 identificadores distintos, ausencia de respuestas vacías en P1–P8 y una categoría consignada por pregunta en cada registro. El archivo no contiene nombres, teléfonos, fechas de aplicación ni veredas individuales. Los identificadores internos no se reproducen en este documento [A1].

El libro `Encuesta_Validacion_AgroEdge_IA.xlsx` contiene las hojas «Resultados por pregunta», «Respuestas individuales» y «CSV original». Se contrastaron sus frecuencias y su copia de las categorías originales con el CSV. El PDF se utilizó para comprobar los enunciados y las opciones del instrumento [A1–A3]. El libro es una presentación de los mismos datos y no constituye una segunda muestra.

No consta en estas fuentes la fecha efectiva de aplicación, el método de selección de participantes, el número de personas contactadas, la distribución por vereda, la modalidad utilizada ni quién aplicó cada encuesta. Esos aspectos permanecen como **no documentados**. No se asigna retrospectivamente un diseño de muestreo.

## 3. Análisis descriptivo de las 40 respuestas

Se calcularon frecuencias absolutas por categoría y porcentajes mediante `100 × frecuencia / 40`, sin ponderación. Cada respuesta representa 2,5 puntos porcentuales. Se conservaron las categorías del CSV; únicamente se restituyeron tildes y expresiones del instrumento para facilitar la lectura. Las categorías combinadas permanecen agrupadas.

| Pregunta | Respuesta | Frecuencia | Porcentaje |
| --- | --- | ---: | ---: |
| P1. Cultivo principal | Papa | 23 | 57,5 % |
| P1 | Cebolla / hortalizas | 11 | 27,5 % |
| P1 | Frutales / otros | 6 | 15,0 % |
| P2. Decisión del momento de riego | Observación directa | 24 | 60,0 % |
| P2 | Horario o calendario fijo | 10 | 25,0 % |
| P2 | Pronóstico en celular o noticias | 6 | 15,0 % |
| P3. Uso de bombeo | Sí, motobomba / sistema de bombeo | 31 | 77,5 % |
| P3 | No, riego por gravedad o lluvia directa | 9 | 22,5 % |
| P4. Riego seguido de lluvia en los últimos seis meses | Frecuentemente, varias veces al mes | 23 | 57,5 % |
| P4 | Ocasionalmente, una o dos veces al mes | 15 | 37,5 % |
| P4 | Rara vez o nunca | 2 | 5,0 % |
| P5. Afectación percibida de costos | Mucho | 28 | 70,0 % |
| P5 | Moderadamente | 9 | 22,5 % |
| P5 | Poco o nada | 3 | 7,5 % |
| P6. Confianza en pronósticos tradicionales | Poco confiables | 31 | 77,5 % |
| P6 | Medianamente confiables | 6 | 15,0 % |
| P6 | Muy confiables / no los consulta | 3 | 7,5 % |
| P7. Utilidad de un dispositivo local | Totalmente de acuerdo | 29 | 72,5 % |
| P7 | De acuerdo, según facilidad de uso | 8 | 20,0 % |
| P7 | No lo ve necesario | 3 | 7,5 % |
| P8. Disposición a probar o adquirir | Sí, definitivamente | 33 | 82,5 % |
| P8 | Tal vez, si observa resultados primero | 4 | 10,0 % |
| P8 | No, por costos o preferencia por manejo manual | 3 | 7,5 % |

**Fuente:** recálculo sobre [A1], contrastado con [A2, A3]. Cada pregunta suma 40 respuestas y 100,0 %.

En P3, el enunciado menciona bombeo o reservorio, pero las opciones distinguen bombeo frente a gravedad o lluvia directa. Por ello, el 77,5 % describe la opción de bombeo y no permite estimar por separado cuántas personas disponen de reservorio. En P6, «Muy confiables / no los consulta» reúne dos situaciones diferentes: sus tres respuestas no pueden repartirse entre ambas ni presentarse íntegramente como confianza alta.

## 4. Interpretación en relación con AgroEdge IA

### 4.1. Prácticas de riego y uso de recursos

La observación directa aparece en 24 respuestas y el horario fijo en 10. En conjunto, 34 de 40 registros (85,0 %) seleccionan una de estas dos opciones. Esto respalda la pertinencia de ofrecer información ambiental comprensible que pueda incorporarse a las prácticas declaradas. El instrumento registra el criterio principal seleccionado; no demuestra que estas personas nunca consulten otras fuentes.

El uso declarado de bombeo en 31 respuestas (77,5 %) muestra que los costos de operación resultan pertinentes para este grupo. La pregunta P5 reúne tanto el riego previo a una lluvia como las épocas de verano: 28 personas (70,0 %) señalan una afectación alta y 9 (22,5 %) una afectación moderada. Las 37 respuestas combinadas (92,5 %) expresan una preocupación económica, sin cuantificar combustible, electricidad, mano de obra, agua perdida o ahorro atribuible al sistema.

### 4.2. Coincidencia del riego con lluvia posterior

En P4, 23 personas reportan que regaron y a las pocas horas llovió frecuentemente, y 15 ocasionalmente. Son 38 respuestas (95,0 %) en esas dos categorías. El hallazgo describe experiencias recordadas durante los seis meses consultados. No es un registro instrumental de lluvia ni permite calcular el volumen de agua aplicado innecesariamente o atribuir una causa a cada episodio.

AgroEdge IA permite revisar el pronóstico externo junto con el historial ambiental del dispositivo. Esta función responde al problema expresado, pero su beneficio efectivo para programar el riego requiere una evaluación agrícola adicional con mediciones de uso de agua, costos y resultados del cultivo.

### 4.3. Confianza en el pronóstico y necesidad de contexto local

Las 31 respuestas de baja confianza en los pronósticos (77,5 %) apoyan la conveniencia de mostrar claramente la fuente, la fecha de captura y la escala de la información meteorológica. Son valoraciones de los encuestados; no equivalen a una medición del error de los proveedores de pronóstico.

La estación mide condiciones en su ubicación, mientras que Open-Meteo y Eltiempoen.net aportan pronósticos externos. NOAA aporta contexto estacional ENSO. El sistema conserva estas procedencias por separado. Ninguna de esas fuentes sustituye las etiquetas físicas de exposición utilizadas para evaluar el modelo [A4, A5].

### 4.4. Utilidad percibida y disposición de uso

En P7, 29 respuestas expresan acuerdo total y 8 acuerdo condicionado a la facilidad de uso: 37 de 40 (92,5 %) en conjunto. P8 registra 33 respuestas afirmativas (82,5 %), 4 condicionales (10,0 %) y 3 negativas (7,5 %). La diferencia entre ambas preguntas debe conservarse: utilidad percibida y disposición declarada no son la misma variable.

P7 y P8 describen una solución hipotética con avisos para regar o esperar, bajo costo y facilidad de uso. La respuesta favorable a esa propuesta no demuestra que el sistema actual emita recomendaciones agronómicas validadas, que las personas hayan utilizado el prototipo o que exista una intención de compra a un precio definido. La inferencia TinyML y la adquisición USB pueden operar localmente; la actualización de fuentes meteorológicas externas necesita conectividad.

Como interpretación para el diseño, los resultados justifican priorizar lectura sencilla de las variables, trazabilidad de las fuentes y demostraciones comprensibles de funcionamiento. Son orientaciones derivadas del análisis, no testimonios adicionales ni funciones cuya eficacia agrícola haya sido probada por la encuesta.

## 5. Alcance y limitaciones

Los 40 registros sustentan una descripción del grupo consultado. La falta de información sobre selección y cobertura impide generalizar porcentajes a todos los productores de Toca o calcular un margen de error de muestreo defendible. Las preguntas recogen percepciones y recuerdos; no documentan un ensayo antes/después del uso de AgroEdge IA.

Las opciones combinadas de P6 y P8 limitan la interpretación de confianza, costos y preferencia por el manejo manual. El lenguaje favorable de la solución en P7 y P8 puede influir en las respuestas. No se documentan pruebas de usabilidad, adopción sostenida, disposición a pagar por un importe específico, reducción del consumo energético, ahorro de agua o aumento de producción.

## 6. Contribuciones y alcance de la publicación

El conjunto de encuestas y los resultados técnicos se presentan como evidencia del equipo de AgroEdge IA. La documentación existente identifica a Sergio como observador de los intervalos confirmados de las sesiones C–F; esa contribución experimental se describe en `registro-campo.md` [A4, A5]. Los archivos de encuesta no individualizan al encuestador ni permiten atribuir a Sergio las 40 aplicaciones, el diseño completo del instrumento o la elaboración original del consolidado.

Este documento reúne y verifica fuentes existentes para facilitar la contribución académica que Sergio publique desde su cuenta. No contiene respuestas individuales, información de contacto ni testimonios atribuidos a productores.

## 7. Referencias a los originales

Las rutas son localizadores del archivo examinado en el equipo de preparación. No implican que los originales privados deban incorporarse al repositorio público.

- **[A1]** `C:\AgroEdge\resultados_encuesta.csv`. Fuente primaria del recuento de 40 respuestas.
- **[A2]** `C:\AgroEdge\Encuesta de Validación en Campo - AgroEdge IA.pdf`. Instrumento, páginas 1 y 2.
- **[A3]** `C:\AgroEdge\Encuesta_Validacion_AgroEdge_IA.xlsx`. Hojas «Resultados por pregunta», «Respuestas individuales» y «CSV original»; presentación derivada de [A1].
- **[A4]** `C:\AgroEdge\AgroEdge-IA\README.md`, `MATRIZ_DE_REQUISITOS.md` y `docs\cierre-tecnico-2026-11-24.md`. Contexto, funciones, resultados y atribuciones documentadas.
- **[A5]** `C:\AgroEdge\output\AgroEdge_IA_Evidencias_Informe_Final.zip`, entradas `README.md`, `00_Guia/Resultados_y_Limitaciones.md`, `03_Campana_Final/observaciones-confirmadas.json` y `06_Version_Congelada/version.json`. Corte técnico del 24 de noviembre de 2026; versión 0.2.1 y commit de referencia `d045786a1b0dd12cf3b312f07d1910b114a40c60`.

### Identificación SHA-256 de las fuentes principales

| Fuente | SHA-256 |
| --- | --- |
| CSV de respuestas [A1] | `e936d136a78675eeef52551289f88e0cabfd42e4be1c9c01e5ac5e91991680df` |
| Instrumento PDF [A2] | `7156fa6dd8e7714cb21e467caa2cee80a808baf99c214023914e63e81c24d7a7` |
| Consolidado XLSX [A3] | `ddc525f1a140684bb57a77877fcf1d2908ffd72b2a89f617a2881a418c937440` |
| Paquete definitivo [A5] | `a6162b5dc036b0de37a2adf99dc042e0b22f9f99395346e8929c3098a54c064a` |

**Control de esta revisión:** recuentos y porcentajes recalculados; categorías contrastadas con el instrumento y el libro; fuentes consultadas sin modificación. Los datos de aplicación ausentes se consignan como no documentados y no requieren completar este archivo para identificar el alcance de sus resultados.
