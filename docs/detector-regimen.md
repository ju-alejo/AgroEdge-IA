# Corrección del detector para cambios de ambiente

En la campaña USB del 23 de noviembre de 2026 se reprodujeron **las 645 marcas de la versión 0.2.1 y el texto de sus campos `issues`**. La regla comparaba cada variable con la media y la desviación muestral de hasta 60 lecturas `VALID` de la última hora en la misma estación, origen y sesión. Aplicaba un mínimo de 15 lecturas, pisos de dispersión de 0,25 °C, 1 punto porcentual y 0,35 hPa, y un umbral estricto de 3,5 desviaciones. [Bitácora de campo y diagnóstico de recepción](campana-01-2026-11-23.md)

| Variables indicadas en `issues` | Registros originales |
| --- | ---: |
| Temperatura y humedad relativa | 628 |
| Solo temperatura | 11 |
| Solo humedad relativa | 6 |
| Presión, fallo físico o dato ausente | 0 |

Hubo nueve alertas iniciales en las secuencias 54–62 y **636 consecutivas** en las secuencias 1132–1767. La primera del segundo tramo llegó a las **19:24:54,900 en Bogotá** y marcó la caída de temperatura. Desde esa fila hasta el cierre, la referencia conservó exactamente las secuencias **1072–1131**. El traslado quedó registrado en la bitácora hacia las 19:24. La línea de base quedó anclada porque el cambio produjo lecturas `ANOMALY` y la consulta excluía esas lecturas de la referencia.

## Regla en la ruta normal de ingestión

La validación de unidades, valores finitos, rangos y ausencias precede al análisis estadístico. Una lectura `INVALID` o `MISSING` conserva su calidad y se excluye de la prueba de cambio. Mientras la referencia anterior siga activa, los picos se marcan y quedan fuera de ella. La aplicación continúa utilizando una ventana de hasta 60 lecturas en la última hora.

La referencia se renueva solo al encontrar diez mediciones completas, consecutivas y de cadencia comparable con la referencia. Nueve intervalos dentro del bloque deben estar entre 0,6 y 1,6 veces la mediana de al menos cinco pares consecutivos de la referencia. Se requiere que al menos dos variables rebasen juntas el umbral de 3,5 desviaciones en una dirección consistente durante todo el bloque. La amplitud de cada variable dentro del bloque se limita a tres veces su piso de dispersión para exigir coherencia. Así, un pico aislado, un cambio persistente de un solo canal y una ráfaga rápida de recepción conservan su tratamiento de revisión.

La lectura que confirma el cambio queda como `ANOMALY` y añade el motivo de renovación a `issues`. Las diez mediciones coherentes sembrarán la nueva referencia a partir de la lectura siguiente, sin mezclar la línea de base anterior. El marcador queda en el registro ya admitido y la referencia se reconstruye al reabrir SQLite. El detector continúa aceptando el esquema histórico, sin migración ni escrituras retroactivas. En una captura planificada, documentar el cambio y comenzar con un nuevo ID de sesión permite iniciar una referencia independiente. Con el firmware actual, un nuevo arranque emite ese ID.

Una señal atípica dentro de los rangos puede reflejar ambiente o instrumento. Si dos sensores presentan un sesgo coordinado y estable, la confirmación estadística requiere contraste con el registro de campo o con un instrumento de referencia. La cadencia sirve para decidir si un bloque puede renovar la referencia. Las horas de recepción y sus incidencias se conservan como evidencia temporal independiente.

## Resultado del replay real

La reproducción usa `Store.ingest` en SQLite en memoria. Detectó un cambio a las **19:27:36,658**, en la secuencia **1164**. La secuencia 1165 volvió a estar dentro de la referencia recién renovada. El evento ocurrió durante la adaptación del sensor y no cambia el corte provisional de 19:31 del protocolo de campo.

| Fase | Marcas 0.2.1 | Puntos atípicos v2 | Renovaciones v2 | Sin alerta estadística v2 |
| --- | ---: | ---: | ---: | ---: |
| Antes del traslado | 9 | 9 | 0 | 1.062 |
| Banda de traslado | 2 | 2 | 0 | 22 |
| Adaptación exterior | 71 | 30 | 1 | 40 |
| Después del corte provisional | 563 | 22 | 0 | 541 |
| Total | **645** | **63** | **1** | **1.665** |

Las 22 alertas después del corte se conservan para revisión. Doce corresponden a temperatura, cuatro a humedad y seis a ambas variables. Las 351 filas con incertidumbre de recepción siguen marcadas por separado, incluso cuando sus valores están dentro de la referencia revisada. No hay fallos físicos registrados en esta campaña. Las pruebas de regresión sí ejercitan mediciones ausentes y fuera de rango.

El dataset derivado en `C:/AgroEdge/Dataset/2026-11-23_Sesion_01_procesado_v2` contiene los **1.729 IDs** y conserva íntegros los campos de la versión v1. Añade calidad y motivos v2, revisión temporal y versión del detector. Conserva `UNASSIGNED_PILOT` en todas las filas. `NO_STATISTICAL_FLAG` describe el resultado de la regla estadística. La elegibilidad para aprendizaje sigue dependiendo de evidencia de campo y de tiempos, ventanas y particiones válidas. `resumen.json` documenta la línea de base congelada, el evento de renovación y los hashes de la copia SQLite y de v1. La gráfica `comparacion-detector.png` representa las ráfagas sin unir los tramos de hora de recepción incierta.

## Reproducción y preparación del entrenamiento

```powershell
$v1 = 'C:/AgroEdge/Dataset/2026-11-23_Sesion_01_procesado_v1'
$salida = 'C:/AgroEdge/Dataset/2026-11-23_Sesion_01_replay_verificacion'
node scripts/replay-anomalies.mjs "$v1/respaldo/agroedge-2026-11-23.sqlite" "$v1/dataset" $salida
python scripts/plot-anomaly-replay.py $salida "$salida/comparacion-detector.png"
```

El replay requiere Node 24 y las dependencias fijadas en el proyecto. La gráfica se generó con Matplotlib 3.11.2. Pasaron 11 pruebas de Node, 20 de Python y la prueba del índice Java. Los casos nuevos cubren la aceptación del régimen, la persistencia tras reapertura, la separación por sesión, el pico aislado, la desviación de un solo sensor, la ráfaga, la ausencia y el rango físico. TypeScript, la compilación de producción, el flujo HTTP y el panel NOAA se verificaron en una copia aislada. Dos replays produjeron los mismos hashes y el cotejo de solo lectura confirmó que las 1.729 filas de SQLite original coinciden con la copia anterior a la prueba.

La campaña conserva cero etiquetas independientes de precipitación. Para entrenar hacen falta capturas exteriores con montaje estable en tres bloques cronológicos. Cada partición necesita al menos dos eventos independientes y diez ventanas utilizables por clase, con 30 minutos de margen después de cada corte. Registra explícitamente intervalos de lluvia y ausencia observada con un reloj sincronizado y un código de evento. Excluye traslado, adaptación, incidencias de recepción y eventos con evidencia ambigua. El entrenador existente ofrece `--audit-only` para revisar la cobertura antes de fijar pesos. El resultado de esa auditoría para la campaña 01 es `ready: false`.

## Seguimiento de requisitos

| Requisito | Evidencia y pendiente |
| --- | --- |
| R1 | Contexto regional y traslado documentados. Faltan sitio exacto y evidencia del beneficiario. |
| R2 | Inferencia preliminar verificada previamente en la ESP32-S3 y por USB. |
| R3 | Núcleo int8 verificado en placa. Pendientes entrenamiento, contraste float/int8 y evaluación del modelo entrenado. |
| R4 | Campaña propia preservada y reproducida con calidad v1 y v2. Faltan sesiones y observaciones independientes de lluvia. |
| R5 | NOAA, Open-Meteo y cliente Java conservan las rutas verificadas. Sigue pendiente registrar el resultado de la primera consulta diaria programada de NOAA. |
| R6 | Buffer embebido e índices SQLite/Java comprobados. El detector usa el orden por sesión y secuencia de SQLite para recomponer la referencia. |
| R7 | Flash, RAM, ciclos, latencia y rendimiento preliminares medidos. Faltan energía y mediciones del modelo entrenado. |
| R8 | Evidencia técnica en Markdown y datos reproducibles. Los borradores se conservan y el trabajo académico está suspendido por instrucción del usuario. |
