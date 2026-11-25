# AgroEdge IA · Campaña de exposición y TensorFlow Lite Micro

## Evidencia de campo y calidad

El 24 de noviembre se registraron 2.823 lecturas USB de AHT20 y BMP280 en seis arranques. El respaldo se creó por la API de backup de SQLite desde la fuente en modo de solo lectura, incluyendo las transacciones del WAL ya confirmadas. Pasó `integrity_check` y obtuvo SHA-256 `4b31d22ed54b6dff9cd8e37a398f0ade531850fdcc52dfe3eb5da7e390f60116`. Los cinco pares CSV/Excel coinciden por ID y por todos los campos exportados con el respaldo. Se conserva el dataset v2 del día 23 como campaña piloto independiente.

| Sesión | Partición | Lecturas | VALID | ANOMALY |
| --- | --- | ---: | ---: | ---: |
| A | Entrenamiento | 585 | 521 | 64 |
| B | Entrenamiento | 443 | 430 | 13 |
| C | Validación | 448 | 390 | 58 |
| D | Validación | 463 | 424 | 39 |
| E | Prueba | 435 | 413 | 22 |
| F | Prueba | 449 | 427 | 22 |

Los `sessionId` completos se conservan en el CSV de auditoría junto a los límites, los conteos por sesión y los archivos originales. [Sesiones auditadas](C:/AgroEdge/output/evidencia/campana-exposicion-2026-11-24/sesiones.csv)

Las 884 lecturas de E y F coinciden con el total mostrado en el dashboard. Las seis medianas entre recepciones fueron de 5,006 s, con extremos de 4,897 y 5,116 s y frecuencia efectiva próxima a 0,19976 Hz. Hubo cero duplicados de ID, secuencia u hora, cero saltos internos de secuencia y cero ráfagas bajo el criterio de 4–8 s. Las primeras secuencias fueron 79, 23, 92, 63, 6 y 2. Los 259 números previos que declara el puente corresponden al prefijo ausente al conectar; la captura no permite identificar su causa. Se observaron 15,52–30,93 °C, 43,45–81,47 % y 735,08–739,22 hPa, dentro de los límites físicos aplicados. Las 218 banderas `ANOMALY` son desviaciones estadísticas y conservan sus `issues`. Se preservaron también los intervalos fuera de observación.

## Etiquetas y particiones

Los intervalos de A y B salen de la bitácora de entrenamiento, que deja pendiente la ubicación exacta. Los de C–F se contrastaron con sus bitácoras y la confirmación del usuario, con el observador `SAG` en Toca. El etiquetado conserva `greenhouse` y `outdoor`. La lluvia y las condiciones de campo no registradas permanecen desconocidas. Se avanzó el primer inicio útil hasta diez minutos después de la primera recepción si quedaba menos tiempo. En F, el exterior quedó etiquetado desde las 18:30:19,750. El fin de entrenamiento se fijó a las 10:01 porque A termina a las 10:00:13. El fin de validación quedó a las 17:00, con D hasta las 16:59:22 y E desde las 17:39:53. Las zonas y los cortes están registrados explícitamente. Se conservó el embargo de 30 minutos y cada arranque quedó íntegro en su partición.

| Partición | Etiquetadas invernadero/exterior | Ventanas invernadero/exterior | Filas usadas en ventanas |
| --- | ---: | ---: | ---: |
| Entrenamiento | 186 / 178 | 31 / 28 | 354 |
| Validación | 191 / 182 | 31 / 30 | 366 |
| Prueba | 192 / 188 | 32 / 31 | 378 |

Las ventanas tienen seis registros consecutivos, sin filas compartidas y con calidad `VALID`. Hay dos eventos de origen por clase y partición. La separación por sesiones evita compartir datos del mismo arranque y preserva la evaluación temporal en un solo día.

### Incidencia C

El intervalo de traslado y estabilización de 15:48–15:58 tuvo 120 lecturas. Entre 15:52:36,242 y 15:57:21,577 el detector marcó 58 consecutivas, un tramo de 4 min 45,335 s entre marcas. La última registró la renovación de la referencia. Las siguientes seis quedaron `VALID`, desde 15:57:26,583 hasta 15:57:51,614. El fin físico de la perturbación y su causa quedaron sin determinar. La temperatura llegó a 30,93 °C, la presión a 737,37 hPa y la humedad bajó a 43,45 %. La fase confirmada de exterior desde 15:58 aportó 16 ventanas completas. Esto describe recuperación de la validez estadística. Las señales siguieron evolucionando durante la observación y esa variación permanece en validación. El modelo int8 acertó 12 de las 16 ventanas de exterior de C y 4 de 14 en el exterior de D. La diferencia entre dos sesiones no permite aislar el efecto de la perturbación. [Procedimiento del detector adaptativo](detector-regimen.md)

## Selección y evaluación

R3 en la página 4 de los lineamientos exige un modelo ligero como TensorFlow Lite o TFLite Micro y documentar la conversión y sus diferencias. Se mantuvo el C++ de centroides como referencia y se entrenó una regresión lineal regularizada con una sola capa densa de tres entradas y un resultado. Usa media de temperatura, media de humedad y diferencia de presión. Se compararon la clase mayoritaria, el centroide de humedad, los centroides completos y este modelo lineal. El ajuste y la calibración int8 usaron exclusivamente las 59 ventanas de entrenamiento. Se seleccionó por exactitud balanceada int8 en validación, con macro-F1 como desempate, y se guardaron la elección y la huella del modelo antes de calcular las métricas de prueba. [Lineamientos del Proyecto Integrador](C:/AgroEdge/Lineamientos_Proyecto_Integrador.pdf) · [Conversión a LiteRT para microcontroladores](https://developers.google.com/edge/litert/microcontrollers/build_convert)

| Modelo | Exactitud balanceada, validación | Exactitud balanceada, prueba |
| --- | ---: | ---: |
| Clase mayoritaria | 50,0 % | 50,0 % |
| Humedad int8 | 26,7 % | 50,0 % |
| Centroides C++ int8 | 26,7 % | 50,0 % |
| Lineal float32 | 88,3 % | 50,0 % |
| Lineal TFLite int8 | 76,7 % | 100,0 % |

| Modelo evaluado | Exactitud | Macro-F1 | Matriz, filas observadas y columnas predichas |
| --- | ---: | ---: | --- |
| TFLite float32, validación | 88,5 % | 88,3 % | `[[31, 0], [7, 23]]` |
| TFLite int8, validación | 77,0 % | 75,6 % | `[[31, 0], [14, 16]]` |
| TFLite float32, prueba | 50,8 % | 33,7 % | `[[32, 0], [31, 0]]` |
| TFLite int8, prueba | 100,0 % | 100,0 % | `[[32, 0], [0, 31]]` |

El orden de clase es invernadero, exterior. En validación, el int8 obtuvo precisión, recall y F1 de 68,9 %, 100 % y 81,6 % para invernadero, y 100 %, 53,3 % y 69,6 % para exterior. En prueba las tres métricas fueron 100 % para ambas clases, sobre dos arranques del mismo día. El cambio float32/int8 en exactitud balanceada fue −11,7 puntos en validación y +50,0 en prueba. El trayecto int8 incluye el redondeo de características que usa el firmware y la cuantización de tensores de TFLite. En validación se saturaron cero de 183 componentes. En prueba se saturaron 43 de 189, todos de humedad, en 12 ventanas de invernadero y las 31 de exterior. El límite superior de representación equivale a 69,98 % de humedad relativa. El salto de métricas es sensible a ese recorte. Hace falta probar el comportamiento en otros días, instalaciones y rangos ambientales antes de usarlo como evidencia de generalización.

El FlatBuffer int8 pesa 1.160 bytes frente a 1.000 bytes de la versión float32. En este grafo pequeño el empaquetado de parámetros de cuantización incrementa el tamaño total. Entrada y salida son int8 y el único operador es `FULLY_CONNECTED` v4. El SHA-256 int8 es `2c4870d61d3ff2e82ff1972d112372b69e370c5cb7c352df54ab6d7d3534333d`. El puntaje mostrado por el firmware expresa la magnitud del margen cuantizado. La arena reservada en el candidato ocupa 4.096 bytes. [Cuantización de enteros](https://developers.google.com/edge/litert/conversion/tensorflow/quantization/post_training_quantization) · [Chirale TensorFlow Lite Micro v2.0.0](https://github.com/spaziochirale/Chirale_TensorFlowLite/tree/v2.0.0)

## Reproducción

La evidencia está en `C:/AgroEdge/output/evidencia/campana-exposicion-2026-11-24`. Incluye `auditoria.json`, `sesiones.csv`, tres gráficas, `incidencia-C.json`, el respaldo, el etiquetado, datos por ventana, la comparación de modelos y el log de compilación. La confirmación de campo transcrita se conserva en `observaciones-confirmadas.json`. Para repetir, usa carpetas nuevas y el respaldo existente. El entorno de entrenamiento fue Python 3.12.12 con TensorFlow 2.20.0, NumPy 2.5.5 y Matplotlib 3.10.7 para las gráficas.

```powershell
$e = 'C:/AgroEdge/output/evidencia/campana-exposicion-2026-11-24'
$r = 'C:/AgroEdge/output/evidencia/reproduccion-exposicion-2026-11-24'
$py = '.venv/r5-python/Scripts/python.exe'
$tf = '.venv/tflm-python/Scripts/python.exe'
& $py -m scripts.audit_exposure_campaign data/agroedge.sqlite C:/AgroEdge/Dataset $r --snapshot "$e/agroedge-respaldo.sqlite"
& $py -m scripts.label_exposure_campaign $r "$e/observaciones-confirmadas.json" "$r/etiquetado"
$env:TF_NUM_INTEROP_THREADS = '1'
$env:TF_NUM_INTRAOP_THREADS = '1'
$env:TF_ENABLE_ONEDNN_OPTS = '0'
& $tf -m scripts.train_tflm_exposure "$r/auditoria.json" "$r/etiquetado/etiquetas-exposicion.csv" "$r/modelo-tflm"
& $tf -m scripts.plot_exposure_campaign $r
```

En el sketch sin `tflm_model_data.h` se conserva el prototipo. Para compilar el candidato se copia el sketch a un directorio de ensayo y se agrega allí el encabezado generado. La biblioteca Arduino se fijó en la versión 2.0.0, revisión `46da2f989205a9216229d38cd3d1c657d79d6781`, y el núcleo Arduino ESP32 en 4.0.0. El perfil UART a 240 MHz replica el usado para el respaldo recuperable, con perfil Flash de 4 MiB, partición de aplicación de 1.310.720 bytes y PSRAM deshabilitada. La placa tiene 16 MiB físicos de Flash según el ensayo anterior. [Respaldo y banco anterior](campana-01-2026-11-23.md#validación-física-tinyml)

| Resultado de compilación | Prototipo de regresión | Candidato TFLite Micro |
| --- | ---: | ---: |
| Programa informado por Arduino | 367.617 B | 400.937 B |
| RAM estática sobre 327.680 B del perfil | 24.464 B | 28.952 B (8,84 %) |
| Arena reservada | 0 B | 4.096 B incluidos en la RAM estática |

El candidato ocupa 401.088 bytes como imagen de aplicación, equivalente al 30,60 % de la partición y al 2,39 % de la Flash física. El SHA-256 de la imagen es `1a3b357c4876c3a445255819aa66a3ddc3d013b1457adb94abca833522118de5`. Se confirmó que el binario contiene intacto el FlatBuffer. Con permiso del usuario se cargó por COM8, manteniendo los mismos segmentos de arranque y la tabla de particiones. `esptool` verificó por hash los cuatro segmentos escritos. El chip se identificó como ESP32-S3 revisión v0.2 con 8 MiB de PSRAM integrada, deshabilitada en este perfil.

```powershell
git clone --depth 1 --branch v2.0.0 https://github.com/spaziochirale/Chirale_TensorFlowLite.git .venv/tflm-libs/Chirale_TensorFLowLite
New-Item -ItemType Directory .venv/tflm-repro | Out-Null
Copy-Item -Recurse hardware/esp32_tinyml .venv/tflm-repro/esp32_tinyml
Copy-Item "$r/modelo-tflm/tflm_model_data.h" .venv/tflm-repro/esp32_tinyml/
$perfil = (Get-Content .venv/fase-a/candidato/build.options.json -Raw | ConvertFrom-Json).fqbn
arduino-cli compile --fqbn $perfil --libraries .venv/tflm-libs --build-path .venv/tflm-repro/build .venv/tflm-repro/esp32_tinyml
```

## Banco físico del 24 de noviembre

El firmware declaró `TFLITE_MICRO` y `TRAINED`. Las seis lecturas consecutivas de secuencias 6–11 trajeron temperaturas de 21,60–21,63 °C, humedad de 66,47–66,73 % y presión de 737,21–737,27 hPa. Las seis incluyeron la clase estimada `Perfil de invernadero`. Se reprodujeron los 63 vectores de prueba con cero discrepancias de clase y cero discrepancias en el logit int8 respecto al intérprete TFLite de referencia en PC.

| Magnitud medida | Candidato TFLite Micro |
| --- | ---: |
| Invocaciones medidas y de calentamiento | 256 y 16, cero fallos |
| CPU | 240 MHz, núcleo 1 |
| Ciclos por inferencia, media ± desviación muestral | 2.081,676 ± 130,901 |
| Ciclos máximos | 3.201 |
| Latencia por ciclos, media ± desviación muestral | 8,674 ± 0,545 µs |
| Latencia máxima por ciclos | 13,338 µs |
| Lote con sobrecarga de medición | 3.416 µs, 74.941 inferencias/s |
| Arena utilizada / reservada | 532 B / 4.096 B (12,99 %) |
| Heap interno libre actual / mínimo / total | 345.508 B / 340.020 B / 392.000 B |
| Uso pico del heap interno | 13,26 % |
| Stack mínimo libre de la tarea | 5.896 B |

El banco mide preparación de la entrada, `Invoke()` y determinación de la clase sin adquisición I²C ni transporte USB. En el flujo real las seis invocaciones informaron 76–93 µs con el temporizador de microsegundos y el cálculo de puntuación. La comparación con el prototipo de 0,443 µs corresponde a dos tramos de trabajo distintos. La versión TFLite Micro suma 33.520 bytes de imagen y 4.488 de RAM estática respecto al binario del prototipo físico anterior. La compatibilidad del modelo con un RP2040 es plausible por el grafo de un operador, su arena pequeña, los periféricos USB/I²C y sus 264 KiB de SRAM y 2 MiB de Flash. El port y la comparación cuantitativa de latencia y consumo en RP2040 quedan sin medir. [Banco del prototipo](campana-01-2026-11-23.md#validación-física-tinyml) · [Especificaciones Pico y Pico W](https://www.raspberrypi.com/products/raspberry-pi-pico/)

Con `P = V × I` y `E = P × t` para los 8,67365 µs medidos se estiman 1,886259 µJ a 65,9 mA, 2,327054 µJ a 81,3 mA y 3,088427 µJ a 107,9 mA. Se usaron 3,3 V y 240 MHz. Son estimaciones teóricas para el chip durante la inferencia. El consumo de la placa incluye los sensores, el regulador, el puente USB y cualquier PSRAM habilitada. La medición eléctrica directa sigue pendiente. [ESP32-S3 Series Datasheet v2.2, tablas 5-7 y 5-9](https://documentation.espressif.com/esp32_s3_datasheet_en.pdf) · [Datos del banco](C:/AgroEdge/output/evidencia/campana-exposicion-2026-11-24/modelo-tflm/benchmark-fisico.json)

### Recepción real en AgroEdge IA

La instancia Next.js de ensayo recibió por COM8 las secuencias 21–26 con temperatura, humedad, presión e inferencia `REAL/USB`. La API de historial y el dashboard recuperaron el mismo `modelVersion` y marcaron la hora del resultado como `RECEIPT`. En la secuencia 26 se mostró `Perfil de invernadero`, puntuación 0,506 y 70 µs de latencia en el flujo USB. Las seis clasificaciones se conservaron en la SQLite de ensayo después de cerrar el puente y reiniciar la instancia. Al cerrar ese ensayo, antes de la demostración manual, se comprobó la integridad de ambas bases en modo de solo lectura y cero filas de ese modelo en la base de campo. La misma verificación HTTP devolvió una edición NOAA y 48 horas de contexto de Toca, con cinco horas vigentes al momento de la prueba. [Captura del dashboard](C:/AgroEdge/output/evidencia/campana-exposicion-2026-11-24/modelo-tflm/integracion-usb/dashboard-tinyml-fisico.png)

Pasaron 27 pruebas Python, 11 de Node, TypeScript, compilación Next.js, la integración HTTP con exportación CSV/Excel y los fixtures USB y Wi-Fi, el render del boletín NOAA y el índice Java. La repetición del entrenamiento produjo los mismos SHA-256 de ambos FlatBuffers y de los vectores de prueba. También se reprodujeron los diagnósticos de saturación y validación por sesión.

```powershell
$m = "$e/modelo-tflm"
& $py hardware/verify_tinyml.py --port COM8 --check-stream --stream-inferences 6 --expect-backend TFLITE_MICRO --vectors "$m/test-vectors.json" --out "$r/benchmark-fisico.json"
& $py scripts/estimate_esp32_energy.py "$r/benchmark-fisico.json" "$r/estimacion-energetica.json"
```

## Demostración manual en AgroEdge IA

El 24 de noviembre se observó el cambio de perfil después de trasladar físicamente la estación del invernadero al exterior. Las tres filas se verificaron en `data/agroedge.sqlite` en modo de solo lectura. Todas son inferencias `REAL/USB` de `exposure-tflm-2c4870d61d3f`, registradas con la hora de recepción en Bogotá. Las ventanas de la campaña permanecen congeladas en 59 de entrenamiento, 61 de validación y 63 de prueba. Las lecturas de demostración pertenecen a una sesión ajena a las seis sesiones experimentales y se conservan como evidencia de funcionamiento.

| Recepción en Bogotá | Secuencia | Clase mostrada | Puntuación | Latencia | Evidencia |
| --- | ---: | --- | ---: | ---: | --- |
| 20:29:59 | 582 | Perfil de invernadero | 0,506 | 71 µs | Registro comunicado por el usuario y confirmado en SQLite |
| 20:30:34 | 589 | Perfil de invernadero | 0,506 | 89 µs | [Captura de invernadero](C:/AgroEdge/output/evidencia/Demostracion_Final/R3_TinyML_Invernadero.png) y SQLite |
| 20:31:24 | 599 | Perfil exterior | 0,153 | 89 µs | [Captura de exterior](C:/AgroEdge/output/evidencia/Demostracion_Final/R3_TinyML_Exterior.png) y SQLite |

### Significado de la puntuación

El modelo produce un valor de salida cuantizado `q` de tipo `int8`. Su punto cero `z` es `1`. El firmware calcula el margen con signo `m = q − z`. Si `m > 0`, asigna el perfil exterior. Si `m ≤ 0`, asigna el perfil de invernadero. El dashboard redondea a tres decimales la puntuación que recibe del firmware, `|q − z| / 255`. Es una distancia al umbral de decisión en unidades normalizadas, sin calibración probabilística. La clase se determina por el signo, que la puntuación omite. [Cálculo en el firmware](../hardware/esp32_tinyml/inference.h#L49) · [Formato en el dashboard](../components/datacity/views.tsx#L47)

En los registros de invernadero el margen fue de 129 niveles (`q = −128`), que da `129/255 = 0,505882`, la puntuación máxima posible con el punto cero de este modelo. En exterior, el margen fue de 39 niveles (`q = 40`), equivalente a `39/255 = 0,152941`. Los valores de `q` se reconstruyeron a partir de la clase y de la puntuación guardada con seis decimales en SQLite.

### Alcance de cada latencia

| Medición | Qué cronometra | Resultado |
| --- | --- | --- |
| Dashboard (`inferenceUs`) | Tiempo transcurrido en la ESP32-S3 con `esp_timer_get_time()` alrededor de la inferencia sobre una ventana de lecturas reales. Incluye la codificación de la entrada, `Invoke()`, la clase y la puntuación. La ventana ya está calculada al iniciar el cronómetro y el envío USB ocurre después. | 71 y 89 µs en los registros de la demostración |
| Benchmark aislado | Ciclos de CPU alrededor de la llamada con vectores ya preparados y 16 invocaciones de calentamiento. El banco consume el índice de clase como resultado. Divide la media de 2.081,676 ciclos por 240 MHz. | 8,674 µs de media en 256 invocaciones |

La marca horaria del dashboard indica cuándo el PC recibió el registro. Para calcular el tiempo físico de respuesta haría falta la hora exacta del traslado. Estas evidencias sólo contienen las horas de recepción. [Tramo medido en el flujo USB](../hardware/esp32_tinyml/esp32_tinyml.ino#L138) · [Medición aislada](../hardware/esp32_tinyml/benchmark.h#L25) · [Verificación reproducible](C:/AgroEdge/output/evidencia/Demostracion_Final/verificacion-demostracion-2026-11-24.json)

## R1–R8

| Requisito | Estado |
| --- | --- |
| R1 | Caso agroclimático local documentado. Falta evidencia directa del beneficiario. |
| R2 | Adquisición e inferencia real en placa por USB, con seis resultados consecutivos verificados también en el dashboard. Wi-Fi conserva el contrato probado por HTTP. |
| R3 | Modelo ligero int8 entrenado, congelado y ejecutado en TFLite Micro en placa. Paridad completa de los 63 vectores y cambio de perfil observado en la demostración manual. |
| R4 | Seis sesiones propias, etiquetas de campo y evaluación separada reproducidas. La generalización espacial y temporal sigue pendiente. |
| R5 | Ejecución automática NOAA y deduplicación comprobadas. Toca tiene captura HTTPS y dashboard verificados, y su actualización diaria quedó programada. [Evidencia R5](r5-verificacion.md#ejecución-automática-y-deduplicación--24-de-noviembre-de-2026) |
| R6 | Ventana circular en el edge e índices SQLite y Java del boletín. |
| R7 | Banco en placa, uso de memoria, comparación del prototipo y estimación teórica. Pendiente la medición eléctrica directa. |
| R8 | Evidencias técnicas reunidas en Markdown y datos reproducibles. Informe académico en pausa. |
