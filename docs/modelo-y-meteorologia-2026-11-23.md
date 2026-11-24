# AgroEdge IA · Modelo de exposición y contexto meteorológico

## R3 y R4 · Piloto con mediciones propias

El piloto `exposure-pilot-d28443a228a8` aprende dos perfiles de exposición de la campaña S01 del 23 de noviembre de 2026. La anotación de campo del traslado cerca de las 19:24 permite identificar invernadero y exterior. El ajuste usó 197 ventanas de seis lecturas USB distintas, 168 de invernadero y 29 de exterior. Excluyó los primeros cinco minutos, la transición y la estabilización provisional, los intervalos de recepción incierta y las filas sin calidad revisada `VALID`. La campaña completa conserva sus 1.729 registros y sus banderas originales. [Dataset v2 y replay del detector](detector-regimen.md)

| Exposición | Ventanas de ajuste | Centroide `int8` |
| --- | ---: | --- |
| Invernadero | 168 | `(2, 13, 0)` |
| Exterior | 29 | `(-5, 33, 0)` |

Cada clase ocupa tres bytes de pesos. El vector usa la media de temperatura menos 20 °C, la media de humedad relativa menos 50 puntos y la variación de presión en pasos de 0,05 hPa. Los dos centroides de presión se redondearon a cero. La contribución de esa característica a la distancia es igual para ambas clases en este piloto. La campaña combina una sola sesión, un traslado y distintas horas del día. Los seis vectores exportados prueban paridad del firmware con Python y proceden del ajuste. La validación y la prueba independiente siguen pendientes.

- **Exposición.** Es el objetivo viable con las anotaciones actuales. Compara los centroides completos con la clase mayoritaria y con un centroide que solo use humedad. El entrenador calcula ambas referencias en las particiones independientes cuando se cumplen los mínimos. Considera añadir la tendencia de temperatura o un árbol pequeño si los errores de validación muestran perfiles que esos centroides no separan. Decide antes de abrir la prueba.
- **Lluvia observada.** Es un segundo objetivo y requiere anotaciones contemporáneas en exterior. La campaña S01 carece de ellas. La exposición, la humedad, la predicción de Open-Meteo y el boletín ENSO quedan fuera del proceso de etiquetado de lluvia.
- **Decisiones agrícolas.** Presenta la exposición estimada junto al ambiente medido, el pronóstico horario y el boletín estacional. Los datos ayudan a elegir cuándo inspeccionar las condiciones del lote o reconsiderar el horario de riego.

El piloto compiló para ESP32-S3 a 240 MHz con Arduino ESP32 4.0.0, UART USB, perfil Flash de 4 MiB y PSRAM desactivada. Arduino informó 367.405 bytes de programa y 24.464 bytes de RAM estática. El binario de aplicación ocupa 367.552 bytes de una partición de 1.310.720 bytes. Su SHA-256 es `92b742eec42c89b2f32413d5155f06060f0311e1b62f8b5ff8a01a2856aa925d`. La compilación y el encabezado están fuera del directorio del firmware operativo. La escritura y validación física de este binario requieren autorización expresa. El prototipo de humedad anterior ya se verificó físicamente y tiene respaldo recuperable. [Validación anterior](campana-01-2026-11-23.md#validación-física-tinyml)

```powershell
$py = '.venv/r5-python/Scripts/python.exe'
$s01 = 'C:/AgroEdge/Dataset/2026-11-23_Sesion_01_procesado_v2'
& $py -m scripts.train_exposure_pilot $s01 'C:/AgroEdge/output/evidencia/modelo-exposicion-piloto-s01'
```

Usa una carpeta nueva al repetir la orden. `fit.json` registra las filas exactas de cada ventana, los SHA-256 del CSV y del resumen v2, los centroides float e int8 y el alcance `fit_only`. `model.h`, `paridad-dispositivo.json` y `SHA256SUMS.txt` acompañan el resultado. El banco del piloto debe comprobar seis lecturas consecutivas y la inferencia en placa, los seis vectores y las 256 búsquedas después de 16 de calentamiento. Guarda aparte el benchmark y el comprobante de ingreso USB en una base de ensayo.

```powershell
# Compilar sin cambiar el encabezado que usa el firmware del repositorio.
$piloto = 'C:/AgroEdge/output/evidencia/modelo-exposicion-piloto-s01'
New-Item -ItemType Directory .venv/exposure-replay | Out-Null
Copy-Item -Recurse hardware/esp32_tinyml .venv/exposure-replay/esp32_tinyml
Copy-Item "$piloto/model.h" .venv/exposure-replay/esp32_tinyml/model.h
$perfil = (Get-Content .venv/exposure-s01/build/build.options.json -Raw | ConvertFrom-Json).fqbn
arduino-cli compile --fqbn $perfil --build-path '.venv/exposure-replay/build' .venv/exposure-replay/esp32_tinyml
```

## Protocolo de campo del martes 24 de noviembre

Cada bloque corresponde a una partición. Realiza **dos arranques independientes** de la ESP32 por bloque, cada uno con dos exposiciones. Coloca la estación en el primer entorno antes de arrancar. Espera **10 minutos**, registra **8 minutos continuos** de observación estable, traslada la estación sin reiniciarla, espera **10 minutos** y registra **8 minutos** en el segundo entorno. Mantén el mismo soporte ventilado, sin radiación ni lluvia directas, altura y protección en ambos lugares. En el segundo arranque invierte el orden para que ambas clases aparezcan al inicio y al final. Los dos arranques, incluidos los cuatro periodos de estabilización, toman unos 72 minutos.

| Partición | Hora en Bogotá | Orden de exposición |
| --- | --- | --- |
| Entrenamiento | 07:00–09:00 | A invernadero → exterior. B exterior → invernadero. |
| Validación | 11:00–13:00 | C invernadero → exterior. D exterior → invernadero. |
| Prueba | 15:00–17:00 | E invernadero → exterior. F exterior → invernadero. |

1. Sincroniza el reloj del PC. Reinicia la placa entre arranques con el puente USB en pausa, conéctalo de nuevo y verifica un `sessionId` distinto en la exportación. Trabaja con los sensores y el firmware de captura disponibles. La captura puede comenzar antes de instalar el piloto, ya que las etiquetas provienen de la bitácora de campo.
2. Registra cada arranque, `sessionId`, código del sitio, observador, referencia de foto o bitácora, orden real, montaje, horas exactas de traslado y de estabilización, ventilación, cielo, lluvia observada e interrupciones. Tras cada traslado, deja sin etiqueta el periodo de estabilización. Si las lecturas tardan más en asentarse o la recepción se acumula en ráfagas, anota el incidente y amplía el periodo estable.
3. Conserva los CSV exportados. Prepara un `etiquetas-exposicion.csv` con encabezado `session,start,end,label,event,observer,evidence` usando `greenhouse` y `outdoor` y fechas ISO 8601 con `-05:00`. Usa para ambas exposiciones de cada arranque el mismo código de evento de campo, diferente en cada arranque. Registra exclusivamente los intervalos estables observados. Mantén S01 como desarrollo previo fuera de esta evaluación.
4. Si hay lluvia, anótala en un archivo separado en el mismo lugar exterior, con comienzo y fin observados y evidencia. Usa `rain` y `no_rain` solo cuando el observador confirme la condición. Un episodio continuo conserva el mismo código aunque se reinicie la placa. Los intervalos de transición o sin observación quedan sin etiqueta. Para evaluar lluvia hacen falta al menos dos eventos independientes y diez ventanas utilizables de **cada clase en cada partición**. Amplía la campaña si la lluvia observada no alcanza esa cobertura.
5. Usa cortes 09:00 y 13:00. Cada sesión queda en una sola partición y el entrenador aplica 30 minutos de margen tras cada corte. Audita primero la cobertura. Después de cerrar la configuración con validación, ejecuta la evaluación de prueba y conserva ambos resultados. Es una evaluación preliminar de un día y sitio, que debe ampliarse para medir generalización.

```powershell
$campo = @('--db','data/agroedge.sqlite','--station','TOCA-ESP32-01','--target','exposure',
           '--labels','data/etiquetas-exposicion.csv','--train-end','2026-11-24T09:00:00-05:00',
           '--validation-end','2026-11-24T13:00:00-05:00')
& $py scripts/tinyml_dataset.py @campo --audit-only
```

Cuando la auditoría confirme cobertura, retira `--audit-only` para exportar el modelo y los vectores de prueba. Mantén la captura, sus mediciones y la evidencia de etiquetas originales fuera de Git. Para capturas futuras sincroniza los intervalos del PC con las secuencias USB antes de revisar los resultados.

### Tiempo del microcontrolador

El firmware actual usa `millis()` para el muestreo nominal cada cinco segundos, pero el dataset registra la hora UTC de recepción. Una ráfaga USB puede ocultar la cadencia real. La mejora compatible para la siguiente versión es enviar un campo opcional `sampleUptimeUs` tomado con `esp_timer_get_time()` al comenzar la lectura I²C. Guárdalo junto con `sessionId`, secuencia y UTC de recepción. Comprueba incrementos de alrededor de cinco segundos dentro de cada arranque, corta ventanas ante una secuencia perdida o un retroceso, y usa el desfase respecto a la recepción para señalar colas. El contador vuelve a empezar tras un reinicio y no proporciona UTC. Ancla la hora absoluta mediante una sincronización medida si necesitas compararla con observaciones meteorológicas. Hasta contar con esa señal se conserva el filtro de 4–8 s y la exclusión de ráfagas. [ESP Timer para ESP32-S3](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/esp_timer.html)

## Open-Meteo · Datos externos vinculados por lectura

Se consultaron los tres productos para Toca, Boyacá, en `5.56112, -73.18294`, el 23 de noviembre. La SQLite derivada `contexto.sqlite` registra producto, modelo, unidades, ubicación devuelta, hora válida, hora de recuperación, URL y SHA-256 del JSON. El CSV vincula cada producto al ID de la lectura USB usando la última hora ya completada en UTC. Se excluyeron del enlace 351 lecturas con hora de recepción incierta.

| Producto | Resultado del 23 de noviembre | Uso |
| --- | --- | --- |
| [Historical Forecast](https://open-meteo.com/en/docs/historical-forecast-api) | 24 horas con datos. 1.378 lecturas vinculadas. | Pronóstico archivado. El historial compuesto no acredita qué dato se conocía al decidir. |
| [Previous Runs](https://open-meteo.com/en/docs/previous-runs-api) | 24 horas con datos GFS `_previous_day1`. 1.378 lecturas vinculadas. | Pronóstico de horizonte nominal de 24 h. Para características operativas, conserva la corrida concreta y comprueba publicación y disponibilidad anteriores a la decisión. |
| [Historical Weather](https://open-meteo.com/en/docs/historical-weather-api) | 24 horas de ERA5 con campos nulos. 1.378 lecturas elegibles sin contexto de ese producto. | Estimación de reanálisis para contextualizar en retrospectiva. Reconsulta tras el retraso de publicación. |

Los productos quedan marcados como `retrospective_context_only` y fuera del vector del piloto. La presión de la celda se etiqueta como presión superficial de la cuadrícula y se conserva su altitud. Es una variable distinta de la presión del BMP280 en el punto de muestreo. La precipitación es la del producto externo, útil para comparar contextos horarios y planear nuevas observaciones de campo. Para un modelo asistido por pronósticos, guarda simultáneamente emisión, recuperación y hora válida, haz la unión solo con lo disponible al cerrar la ventana y compara contra el modelo local con las mismas particiones. El modelo de placa usa únicamente mediciones locales. [Atribución Open-Meteo, CC BY 4.0](https://open-meteo.com/en/terms)

```powershell
& $py -m scripts.enrich_open_meteo $s01 'C:/AgroEdge/Dataset/2026-11-23_Sesion_01_contexto_open_meteo_v1'
# Para reproducir sin red, agrega --raw-dir con la carpeta que contiene los tres JSON archivados.
```

## R5 · Pronóstico horario capturado de la web

Se eligió la tabla pública de Eltiempoen.net para Toca tras comprobar el HTML, el nombre y URL canónicos del municipio, `robots.txt` y la atribución declarada para los datos de los modelos. El sitio presenta un ensamble de seis modelos accedidos por Open-Meteo. Es una segunda presentación web y comparte insumos con Open-Meteo. El código conserva las unidades, los valores ausentes y la descripción de cielo publicada, sin inferir un porcentaje de nubosidad. [Pronóstico y atribución](https://eltiempoen.net/colombia/el-tiempo-en-toca) · [Política para robots](https://eltiempoen.net/robots.txt)

Se descartó meteoblue para esta captura por sus condiciones de atribución y reutilización NC-ND. El portal de fin de semana del IDEAM mostró un buscador sin una tabla directa de Toca en la URL revisada. El producto de precipitación del WPC consultado cubre Estados Unidos. [Condiciones de meteoblue](https://content.meteoblue.com/en/about-us/legal/terms-conditions) · [Portal IDEAM](https://bart.ideam.gov.co/portal/prono_fin_semana/data/) · [Producto WPC](https://www.wpc.ncep.noaa.gov/pqpf/PDD_WPC_PQPF.pdf)

`scraper/toca_forecast.py` usa Requests con User-Agent identificable y selectores BeautifulSoup `select()`, `find()`, `find_all()` y `get_text()`. Consulta `robots.txt`, mantiene un límite diario persistente, honra `Retry-After` y detiene la descarga ante un bloqueo. La captura HTTPS del 23 a las 21:40 guardó 48 horas en `data/pronostico-toca.sqlite`. El segundo intento devolvió `EN_ESPERA`; la próxima consulta elegible era el 24 a las 20:40 en Bogotá. La prueba automatizada verifica ejecución en un intervalo permitido y persistencia del límite al reabrir SQLite. `GET /api/forecast/secondary` entregó las 48 horas de la captura real, y `/api/agroclima` entregó el boletín ENSO existente. El dashboard lee la captura al abrir **Pronóstico** y muestra las horas vigentes con atribución.

```powershell
& $py scraper/toca_forecast.py --dir data fetch
& $py scraper/toca_forecast.py --dir .venv/toca-replay capture 'C:/AgroEdge/output/evidencia/pronostico-toca-2026-11-23.html' --at '2026-11-23T21:36:28-05:00'
```

La tarea **AgroEdge IA - Boletin R5** de NOAA estaba lista para las 16:30 diarias y su ejecución manual del día 23 devolvió código `0`. La primera ejecución programada figura para el martes 24 a las 16:30. La captura local de Toca se verificó por separado con el comando anterior. [Scraper NOAA y tarea programada](r5-verificacion.md)

En Chrome, una instancia Next.js de ensayo abrió **Pronóstico agrícola** y mostró 27 horas vigentes con enlace de atribución. `C:/AgroEdge/output/evidencia/pronostico-toca-verificacion-2026-11-23.json` conserva el resultado del navegador, las 48 filas de la API y el identificador del boletín NOAA leído durante la prueba. Pasaron 26 pruebas Python, 11 pruebas Node, la comprobación TypeScript, la compilación de producción, las rutas HTTP de regresión, el render de NOAA y la prueba de índices Java. El ajuste del piloto reprodujo sus tres hashes. El contexto derivado pasó la verificación SQLite en solo lectura y la auditoría de 5.187 enlaces y tres JSON originales.

## R7 · Estimación energética del prototipo ya medido

Las tablas 5-7 y 5-9 del datasheet ESP32-S3 v2.2, páginas 66–68, dan corrientes típicas de referencia. En los tres escenarios de cálculo se usan 3,3 V, 240 MHz y los relojes de periféricos habilitados. Se aplica `P = V × I` y `E = P × t` a la latencia media experimental de búsqueda de clase del prototipo, 0,443179 µs. [Espressif ESP32-S3 Series Datasheet v2.2](https://documentation.espressif.com/esp32_s3_datasheet_en.pdf)

| Escenario del chip | Corriente | Potencia | Energía estimada por búsqueda |
| --- | ---: | ---: | ---: |
| Un núcleo, instrucciones de 32 bits | 65,9 mA | 217,47 mW | 0,096378 µJ |
| Dos núcleos, instrucciones de 32 bits | 81,3 mA | 268,29 mW | 0,118901 µJ |
| Dos núcleos, instrucciones de 128 bits | 107,9 mA | 356,07 mW | 0,157803 µJ |
| Pico de transmisión Wi-Fi | 340 mA | 1.122 mW | — |

Al usar 0,443 µs redondeados, el primer y tercer escenario dan 0,096339 y 0,157739 µJ. Son estimaciones teóricas de la búsqueda de clase del chip basadas en su latencia medida. El pico Wi-Fi se presenta por separado. El consumo completo de la placa puede variar por PSRAM, sensores, regulador y puente USB. Recalcula con el JSON de banco del modelo definitivo cuando esté en placa.

```powershell
$evidencia = 'C:/AgroEdge/output/evidencia'
& $py scripts/estimate_esp32_energy.py "$evidencia/esp32-banco-2026-11-23.json" "$evidencia/esp32-energia-prototipo-humedad.json"
```

## Estado técnico

| Requisito | Avance y pendiente |
| --- | --- |
| R1 | Necesidad agroclimática delimitada. Falta confirmar beneficiario y uso en Toca con evidencia consentida. |
| R2 | Tres variables físicas, USB y recepción TinyML del prototipo comprobados. Wi-Fi conserva su contrato de ingestión probado por HTTP. Falta validar en red con la placa. |
| R3 | Piloto entrenado con datos propios y compilado. Quedan paridad en placa y resultados de sesiones independientes. |
| R4 | Dataset v2 trazable y campaña para separar exposición y lluvia observada. Pendiente capturar las nuevas sesiones. |
| R5 | NOAA y pronóstico de Toca verificados mediante HTTP y SQLite. Pendiente verificar el resultado de la primera ejecución programada de NOAA. |
| R6 | Buffer y búsqueda int8 reutilizados. Cliente Java e índices del boletín conservados. |
| R7 | Banco físico del prototipo y estimaciones de energía reproducibles. Quedan el banco del modelo entrenado en placa y la medición eléctrica cuando haya instrumental. |
| R8 | Bitácoras técnicas reproducibles. El manuscrito existente sigue en pausa hasta solicitud expresa. |
