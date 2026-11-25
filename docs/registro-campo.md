# Registro de campo: sesiones C, D, E y F

**Versión:** 1.0. **Fecha de revisión documental:** 25 de noviembre de 2026.  
**Campaña:** 24 de noviembre de 2026, Toca, Boyacá.  
**Estado:** documento terminado para publicación por Sergio Andrés Guerrero Alba.  
**Zona horaria de las tablas:** Colombia, UTC−05:00 (`America/Bogota`).

## 1. Alcance y participantes documentados

Este registro reúne las bitácoras de validación y prueba, las exportaciones originales y la auditoría de la campaña. Distingue los horarios del protocolo, los intervalos físicos confirmados y las horas efectivamente recibidas por el sistema. La revisión es documental: no incorpora nuevas observaciones de campo [C1–C6].

La bitácora de validación identifica a «Sergio» como observador. La de prueba conserva el campo de observador sin diligenciar. El archivo posterior `observaciones-confirmadas.json` identifica al observador como `SAG` para C, D, E y F y registra que los intervalos fueron confirmados por el usuario el 24 de noviembre. El cierre técnico y el README del proyecto vinculan esos registros de validación y prueba con Sergio Andrés Guerrero Alba [C1, C2, C4, C6]. Se conserva esta secuencia de procedencia sin alterar las bitácoras originales.

Las sesiones A y B pertenecen al entrenamiento y su bitácora identifica a Juan Alejandro Castillo Arévalo como responsable de adquisición [C3]. Los recuentos auditados, el etiquetado, el entrenamiento del modelo, sus métricas y las demostraciones posteriores son resultados del equipo. Las evidencias revisadas no individualizan la ejecución personal de cada tarea técnica de procesamiento.

## 2. Montaje y protocolo de adquisición

La estación `TOCA-ESP32-01` utiliza una ESP32-S3, un AHT20 para temperatura ambiental y humedad relativa del aire, y un BMP280 para presión atmosférica. La captura se realizó por USB con un intervalo nominal de cinco segundos [C1–C5]. La documentación del sistema establece UART a 115200 baudios, 8N1 y un objeto JSON UTF-8 por línea. COM8 fue el puerto del montaje de referencia; el puerto depende del equipo [C6].

El protocolo contempla diez minutos iniciales de estabilización, ocho minutos de observación en el primer ambiente, diez minutos de traslado y estabilización y ocho minutos de observación en el segundo. Se invirtió el orden de exposición entre las dos sesiones de cada partición. Las etiquetas `greenhouse` (invernadero) y `outdoor` (exterior) proceden del entorno físico observado y confirmado, independientemente de los valores de los sensores.

Las horas de adquisición de estas sesiones tienen fuente temporal `RECEIPT`: corresponden a la recepción en el equipo, sin un reloj autónomo de adquisición acreditado en la placa. Una marca de recepción no determina por sí sola la hora exacta del traslado físico.

La ubicación municipal se documenta como Toca. No quedaron registrados en las fuentes examinadas el punto exacto de instalación, la vereda, la altura de los sensores, su orientación, la distancia a paredes o cubiertas, la exposición solar directa, la ventilación, la nubosidad ni una observación confirmada de precipitación. Se consignan como **no registrados**, sin deducirlos de las curvas o del pronóstico externo.

## 3. Horarios físicos del protocolo y de la confirmación archivada

| Sesión | Partición y sentido | Estabilización inicial programada | Observación del primer ambiente | Traslado y estabilización programados | Observación del segundo ambiente |
| --- | --- | --- | --- | --- | --- |
| C | Validación; invernadero → exterior | 15:30–15:40, invernadero | 15:40–15:48, invernadero | 15:48–15:58 | 15:58–16:06, exterior |
| D | Validación; exterior → invernadero | 16:20–16:30, exterior | 16:30–16:38, exterior | 16:38–16:48 | 16:48–16:56, invernadero |
| E | Prueba; invernadero → exterior | 17:40–17:50, invernadero | 17:50–17:58, invernadero | 17:58–18:08 | 18:08–18:16, exterior |
| F | Prueba; exterior → invernadero | 18:20–18:30, exterior | 18:30–18:38, exterior | 18:38–18:48 | 18:48–18:56, invernadero |

**Fuentes:** programación en [C1, C2] e intervalos de observación confirmados en [C4]. La confirmación posterior respalda los intervalos de observación indicados; no aporta una medición independiente, al segundo, de todos los traslados.

En D, la bitácora registra un nuevo inicio a las 16:20 y presenta los horarios siguientes como previstos. El archivo de confirmación posterior respalda los intervalos 16:30–16:38 y 16:48–16:56. En E y F, la bitácora original también distingue la programación de las horas visibles en la aplicación. Esta revisión utiliza la confirmación archivada para las etiquetas y la auditoría para las marcas de recepción; no modifica retrospectivamente esas anotaciones.

## 4. Recepción efectiva y calidad de los registros

| Sesión | Primera recepción local | Última recepción local | Lecturas | `VALID` | `ANOMALY` | Secuencias recibidas | Prefijo ausente declarado |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| C | 15:30:04,636 | 16:07:22,298 | 448 | 390 | 58 | 92–539 | 91 |
| D | 16:20:49,696 | 16:59:22,448 | 463 | 424 | 39 | 63–525 | 62 |
| E | 17:39:53,373 | 18:16:05,977 | 435 | 413 | 22 | 6–440 | 5 |
| F | 18:20:19,750 | 18:57:42,435 | 449 | 427 | 22 | 2–450 | 1 |
| Total C–F | — | — | 1.795 | 1.654 | 141 | — | 159 |

**Fuente:** [C5]. Las 911 lecturas de C y D se reservan para validación; las 884 de E y F, para prueba. Los totales incluyen estabilización, traslados y recepción posterior al último intervalo etiquetado.

La mediana entre recepciones fue de 5,006 segundos en cada sesión. La auditoría registra cero duplicados de ID y secuencia, cero horas de recepción repetidas, cero saltos internos de secuencia y cero intervalos menores de cuatro o mayores de ocho segundos en C–F. El prefijo ausente declarado corresponde a secuencias anteriores a la primera recibida; su causa no está determinada y no equivale a un salto dentro de la captura conservada.

| Sesión | Identificador íntegro de sesión |
| --- | --- |
| C | `s3-3474caac85d8-96246952-bcc18acb` |
| D | `s3-3474caac85d8-34a3dc08-d7cc6ab0` |
| E | `s3-3474caac85d8-5c03d59c-7ba7ec79` |
| F | `s3-3474caac85d8-bd920141-229e7950` |

### Rangos medidos en cada sesión completa

| Sesión | Temperatura ambiental (°C) | Humedad relativa del aire (%) | Presión de estación (hPa) |
| --- | --- | --- | --- |
| C | 20,97–30,93 | 43,45–64,38 | 735,08–737,37 |
| D | 18,31–22,26 | 61,38–69,25 | 735,46–735,88 |
| E | 15,87–22,15 | 61,81–79,39 | 736,19–736,65 |
| F | 15,52–20,63 | 68,25–81,47 | 736,58–737,02 |

**Fuente:** mínimos y máximos de `measurements` en [C5]. Son rangos de toda la sesión, incluidas sus transiciones. No son promedios por ambiente ni mediciones de humedad del suelo. La presión corresponde a la estación; no se presenta como presión reducida al nivel del mar.

La bitácora de E describe un descenso de temperatura y un aumento de humedad después del traslado al exterior. La de F describe el cambio inverso tras volver al invernadero. Sus cifras aproximadas proceden de la lectura visual de gráficas. Los rangos anteriores se toman de la auditoría numérica y no convierten esas aproximaciones visuales en mediciones puntuales exactas [C2, C5].

## 5. Incidencia de la sesión C

Durante el traslado de invernadero a exterior, la bitácora registró un aumento de temperatura y presión, seguido por una disminución de humedad relativa. También consignó una recuperación posterior de estabilidad y la falta de una causa identificada con certeza [C1].

El análisis archivado del tramo de 15:48–15:58 contiene 120 lecturas: 62 `VALID` y 58 `ANOMALY`. En ese intervalo, la temperatura varió entre 22,42 y 30,93 °C, la humedad entre 43,45 y 64,31 % y la presión entre 735,08 y 737,37 hPa [C7].

| Aspecto | Resultado documentado |
| --- | --- |
| Primera bandera de la secuencia de alarmas | 15:52:36,242 |
| Última bandera consecutiva | 15:57:21,577 |
| Cantidad de lecturas consecutivas con alarma | 58 |
| Tiempo entre primera y última bandera | 285,335 s; 4 min 45,335 s |
| Renovación de la referencia estadística | Registrada en la última bandera, 15:57:21,577 |
| Primeras seis lecturas consecutivas `VALID` posteriores | 15:57:26,583–15:57:51,614 |
| Intervalo físico confirmado de exterior | 15:58–16:06 |
| Lecturas y ventanas conservadas en ese intervalo de exterior | 96 lecturas `VALID`; 16 ventanas |
| Causa física y hora exacta del fin físico de la perturbación | No determinadas |

La duración entre banderas mide el comportamiento del detector. No establece el comienzo o el final exactos del fenómeno físico. La recuperación de `VALID` acredita que el detector volvió a aceptar las muestras conforme a su referencia estadística; no demuestra por sí sola estabilidad física completa ni descarta todas las perturbaciones.

Una bandera `ANOMALY` significa desviación estadística. No acredita un sensor averiado, un episodio de lluvia o una clase de exposición. Los registros originales y sus banderas se conservaron. Las 16 ventanas del exterior posterior de C permanecieron en validación; no se retiraron para mejorar las métricas.

El modelo final int8 acertó 12 de las 16 ventanas de exterior de C y 4 de las 14 de exterior de D [C8]. Es una comparación entre dos sesiones con condiciones distintas; no permite aislar un efecto causal de la incidencia de C sobre el desempeño.

## 6. Tratamiento de las sesiones para evaluar el modelo

Los periodos de traslado y estabilización permanecen en la evidencia original, pero se excluyen del ventaneo de clasificación. Se utilizan ventanas de seis registros consecutivos `VALID`, sin compartir lecturas, agrupadas por sesión y dentro del intervalo físico etiquetado. Las sesiones permanecen completas en su partición: A–B en entrenamiento, C–D en validación y E–F en prueba. El cierre documenta un embargo temporal de 30 minutos entre particiones [C6, C8].

El procesamiento avanzó el inicio útil de la primera observación cuando era necesario completar diez minutos desde la primera recepción. Por eso los inicios usados fueron 15:40:04,636 para C, 16:30:49,696 para D y 18:30:19,750 para F. En E, el intervalo confirmado de 17:50 comienza después de esos diez minutos. Estos ajustes son decisiones de procesamiento conservadas en la cobertura; no son correcciones de las horas físicas de campo.

| Sesión | Lecturas etiquetadas invernadero / exterior | Ventanas invernadero / exterior | Total de ventanas | Registros usados en ventanas |
| --- | ---: | ---: | ---: | ---: |
| C | 95 / 96 | 15 / 16 | 31 | 186 |
| D | 96 / 86 | 16 / 14 | 30 | 180 |
| E | 96 / 96 | 16 / 16 | 32 | 192 |
| F | 96 / 92 | 16 / 15 | 31 | 186 |

**Fuente:** `etiquetado/cobertura.csv` [C8]. Las lecturas etiquetadas que no completan una ventana permanecen conservadas. C–D aportan 61 ventanas y E–F, 63.

La auditoría de C–F identifica salidas del prototipo `humidity-prototype-1` durante la captura. En F hay cuatro lecturas iniciales sin clasificación de ese prototipo. Las etiquetas de exposición se asignaron por observación física y el modelo final `exposure-tflm-2c4870d61d3f` se evaluó posteriormente sobre las ventanas obtenidas de estos registros. No se presenta el modelo definitivo como instalado durante las sesiones C–F ni se utilizan las salidas del prototipo como verdad de campo [C5, C6].

La campaña completa produjo 2.823 lecturas y 183 ventanas: 59 de entrenamiento, 61 de validación y 63 de prueba. Son resultados del equipo sobre una estación y un solo día. Los resultados del modelo requieren conservar sus limitaciones de validación y la saturación int8 de humedad en prueba; se documentan también en `validacion-funcional.md` [C6, C8].

## 7. Localización de las evidencias originales

| Referencia | Ruta original y contenido |
| --- | --- |
| [C1] | `C:\AgroEdge\Dataset\2026-11-24_Validacion\Observaciones.txt`; `Validacion_Sesion_C.csv`, `Validacion_Sesion_C.xlsx`, `Validacion_Sesion_D.csv`, `Validacion_Sesion_D.xlsx`, `Temperatura.png`, `Humedad.png` y `Presion.png` en la misma carpeta. |
| [C2] | `C:\AgroEdge\Dataset\2026-11-24_Prueba\Observaciones.txt`; pares `Prueba_Sesion_E.csv/.xlsx` y `Prueba_Sesion_F.csv/.xlsx`; gráficas `Prueba_Sesion_E_Temperatura.png`, `Prueba_Sesion_E_Humedad.png`, `Prueba_Sesion_E_Presion.png` y sus equivalentes de F, en esa carpeta. |
| [C3] | `C:\AgroEdge\Dataset\2026-11-24_Entrenamiento\Observaciones.txt`. Atribución y protocolo de A–B. |
| [C4] | `C:\AgroEdge\output\evidencia\campana-exposicion-2026-11-24\observaciones-confirmadas.json`. Transcripción de la confirmación de intervalos y observador `SAG`. |
| [C5] | `C:\AgroEdge\output\evidencia\campana-exposicion-2026-11-24\auditoria.json`, `sesiones.csv`, `series-auditadas.csv` y `agroedge-respaldo.sqlite`. Recepción, conciliación y calidad. |
| [C6] | `C:\AgroEdge\AgroEdge-IA\docs\cierre-tecnico-2026-11-24.md` y `C:\AgroEdge\AgroEdge-IA\README.md`. Procesamiento, atribuciones y resultados técnicos. |
| [C7] | `C:\AgroEdge\output\evidencia\campana-exposicion-2026-11-24\incidencia-C.json` y `grafica-validacion.png`. Análisis de la perturbación. |
| [C8] | En la carpeta de campaña: `etiquetado\cobertura.csv`, `etiquetado\etiquetas-exposicion.csv`, `modelo-tflm\ventanas.json`, `modelo-tflm\validacion-por-sesion.json` y `modelo-tflm\evaluacion-prueba.json`. |

El paquete definitivo es `C:\AgroEdge\output\AgroEdge_IA_Evidencias_Informe_Final.zip`. Contiene las exportaciones en `02_Datasets/2026-11-24_exportaciones/`, los derivados auditados en `03_Campana_Final/` y la referencia de versión en `06_Version_Congelada/version.json`. Su corte técnico es el commit `d045786a1b0dd12cf3b312f07d1910b114a40c60`. Los localizadores permiten rastrear la evidencia sin exigir que las bases o los archivos privados se publiquen en GitHub.

## 8. Comprobaciones de esta revisión

Se contrastaron por SHA-256 las bitácoras y los pares CSV/XLSX originales de validación y prueba con las copias del paquete definitivo: coinciden. También coinciden las copias locales de la confirmación, la tabla de sesiones, la incidencia C y el respaldo de campaña. Se verificaron las 325 entradas del manifiesto global del ZIP sin discrepancias. El respaldo se abrió con SQLite en modo `ro` e `immutable`; `PRAGMA integrity_check` devolvió `ok`.

- SHA-256 del paquete definitivo: `a6162b5dc036b0de37a2adf99dc042e0b22f9f99395346e8929c3098a54c064a`.
- SHA-256 del respaldo `agroedge-respaldo.sqlite`: `4b31d22ed54b6dff9cd8e37a398f0ade531850fdcc52dfe3eb5da7e390f60116`.

La revisión comprueba consistencia documental e integridad de los archivos. Los datos físicos no registrados se mantienen explícitamente como tales. No se añadieron observaciones ni se modificaron datos, banderas, bitácoras, modelo, firmware o paquetes definitivos.
