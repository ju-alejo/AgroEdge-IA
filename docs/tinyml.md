# AgroEdge IA · Firmware candidato y verificación local

La [bitácora de la Fase A](fase-a-2026-11-23.md) contiene el último corte de lecturas, el respaldo del firmware operativo y el procedimiento de prueba para el perfil USB-UART actualmente conectado.

La [primera campaña experimental](campana-01-2026-11-23.md) documenta el respaldo físico, las 1.729 lecturas y el tratamiento de las ráfagas y del cambio de ambiente.

## Estación y alcance

La estación mide temperatura del aire, humedad relativa y presión atmosférica. El pronóstico horario de Open-Meteo y el boletín ENSO de NOAA llegan al dashboard por separado. El ESP32 clasifica con las lecturas locales y puede hacerlo sin Internet. En el dashboard, la decisión de riego sigue requiriendo observación del lote y necesidades del cultivo. [Open-Meteo](https://open-meteo.com/en/docs) · [Discusión ENSO del CPC](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc_Sp.shtml) · [FAO 56](https://www.fao.org/4/X0490E/X0490E00.htm)

La Mesa Agroclimática de Boyacá y los boletines del IDEAM documentan la utilidad regional de la información agroclimática. Para R1 falta verificar la necesidad del beneficiario de Toca. Registra con su consentimiento el cultivo y etapa, práctica de riego, decisiones que toma ante lluvia, fuentes de información y una aceptación concreta del panel. Conserva una entrevista fechada y un registro del sitio sin nombres ni coordenadas privadas en Git. [Gobernación de Boyacá](https://www.boyaca.gov.co/secretariaagricultura/mesa-agroclimatica-de-boyaca/) · [IDEAM](https://www.ideam.gov.co/sala-de-prensa/boletines)

## Compilar y probar el candidato

`hardware/esp32_tinyml` usa AHT20 a `0x38` y BMP280 a `0x77` por I²C, SDA GPIO8, SCL GPIO9 y alimentación de 3,3 V. Instala Adafruit BMP280, Adafruit BusIO y Adafruit Unified Sensor. El AHT20 se consulta con `Wire`, espera acotada y verificación CRC. El BMP280 entrega pascales y el firmware envía hPa al dividir por 100. [Hoja de datos AHT20](https://asairsensors.com/wp-content/uploads/2021/09/Data-Sheet-AHT20-Humidity-and-Temperature-Sensor-ASAIR-V1.0.03.pdf) · [BMP280](https://github.com/adafruit/Adafruit_BMP280_Library)

Los ejemplos BME280 de `hardware/arduino_serial` y `hardware/esp32_http` siguen disponibles para su hardware original. Compila el candidato con Arduino ESP32 4.0.0. Selecciona ESP32S3 Dev Module, 16 MB de Flash, PSRAM OPI y partición 16M con 3 MB de aplicación. Usa USB CDC activado si conectas el USB nativo y desactivado si conectas el USB-UART de la placa. Para el USB nativo, el comando equivalente es el siguiente. [Espressif CDC](https://docs.espressif.com/projects/arduino-esp32/en/latest/tutorials/cdc_dfu_flash.html) · [Configuración Flash/PSRAM](https://docs.espressif.com/projects/arduino-esp32/en/latest/troubleshooting.html)

```powershell
arduino-cli compile --fqbn 'esp32:esp32:esp32s3:FlashSize=16M,PSRAM=opi,PartitionScheme=app3M_fat9M_16MB,USBMode=hwcdc,CDCOnBoot=cdc' --build-path '.venv/arduino-tinyml' hardware/esp32_tinyml
python hardware/bridge.py --list
```

Antes de cambiar el firmware de la unidad operativa, conserva una copia del sketch funcional con la configuración de placa y las bibliotecas, o respalda su imagen de Flash. Si tienes una unidad de prueba, verifica en esa unidad la conexión, seis lecturas consecutivas y luego el panel **Clasificación TinyML**. Para probar la ruta con la estación operativa después del respaldo, usa una base de ensayo propia, cierra el monitor serial y conecta el puerto que Windows enumere.

```powershell
$env:AGROEDGE_DB = Join-Path (Get-Location) 'data\ensayo-esp32.sqlite'
npm.cmd start
```

Selecciona USB a 115200. Confirma que suben las secuencias, aparece el modelo `humidity-prototype-1` y se conserva el origen. Verifica que una muestra incompleta limpia la ventana y que un reinicio produce una sesión distinta. Contrasta la presión con una referencia de **presión de estación** a altitud comparable. La base revisada contiene 12 lecturas USB válidas de una sesión con presión constante a 638,15 hPa durante 56 segundos. Comprueba esa señal antes de emplearla como evidencia de variación meteorológica.

## Captura, etiquetado y entrenamiento

El modelo preliminar utiliza tres centroides definidos en el código para representar humedades ambientales de 35, 60 y 85 %. Sirve para verificar la ejecución y el transporte. El objetivo experimental del manuscrito previo sigue siendo reconocer patrones asociados con precipitación **observada** en el mismo sitio y durante la ventana. Para ese objetivo, el entrenamiento calcula centroides a partir de datos propios etiquetados. La puntuación es el margen relativo de distancia entre la mejor y la segunda clase, con desempate por orden de clase. Open-Meteo y NOAA quedan fuera del vector de entrenamiento.

1. Coloca la estación en un sitio ventilado y protegido de radiación y lluvia directas. Registra código de estación, sesión, ubicación autorizada, hora de inicio y fin, montaje, referencia de instrumentos y condiciones. Sincroniza el reloj del PC y registra las interrupciones. Cada muestra llega cada cinco segundos y el backend guarda la hora UTC de recepción cuando falta reloj de dispositivo.
2. Un observador en el mismo sitio registra intervalos completos de lluvia visible (`rain`) y ausencia observada (`no_rain`), con hora sincronizada y evidencia local. Usa el mismo código `event` para un fenómeno meteorológico que continúe entre sesiones. Deja sin etiqueta los cambios, la visibilidad insuficiente y los intervalos sin observación. La anotación nunca se deriva del dashboard, de umbrales de los sensores ni del pronóstico.
3. Guarda el CSV de anotaciones en `data/` con encabezado `session,start,end,label,event,observer,evidence`. Usa fecha ISO 8601 con zona horaria en `start` y `end`, e identificadores privados de observador y evidencia. Define los dos cortes cronológicos antes de consultar resultados. Comienza una captura nueva fuera del margen de 30 minutos en cada corte. Usa al menos dos eventos independientes y diez ventanas utilizables por clase en cada partición como piso del piloto. Captura más eventos para estimar generalización.
4. El script lee SQLite en modo de solo lectura. Selecciona la estación USB y las filas con huella de ingestión. Descarta de la evaluación las muestras incompletas, inválidas y atípicas marcadas por la aplicación, y corta la continuidad ante una secuencia faltante o un intervalo de recepción fuera de cuatro a ocho segundos. Revisa los atípicos con evidencia y registra su frecuencia para detectar sesgo de exclusión. Cada ventana etiquetada contiene seis lecturas sin compartir filas con otras ventanas evaluadas. La ventana debe quedar completamente contenida en un intervalo observado. Las sesiones se asignan completas, con un margen entre particiones, y se rechaza cualquier evento presente en más de una.

```powershell
python scripts/tinyml_dataset.py --station TOCA-ESP32-01
# Define los dos cortes ISO desde el registro de captura. La base puede ser la de ensayo.
python scripts/tinyml_dataset.py --db data/ensayo-esp32.sqlite --station TOCA-ESP32-01 --labels data/etiquetas.csv --train-end $corteEntrenamiento --validation-end $corteValidacion
```

El registro versionado en `data/datasets/` conserva las huellas de las lecturas y las anotaciones, las filas usadas por ventana, las particiones y el alcance temporal. El informe compara la clase mayoritaria del entrenamiento, el modelo float y el modelo int8 en validación y prueba. Incluye matriz de confusión, exactitud, precisión, recall y F1 por clase y macro-F1. Una precisión indefinida se guarda como `null`. Si las clases o eventos son insuficientes el script se detiene antes de exportar pesos. Revisa primero validación. Si se cambian características o hiperparámetros después de abrir los resultados de prueba, reserva un conjunto de prueba nuevo.

El vector usa media de temperatura y humedad y diferencia entre primera y última presión. Los pasos de cuantización son 1 °C, 1 punto porcentual de humedad y 0,05 hPa, con redondeo al entero más próximo, mitades alejadas de cero y saturación int8. La distancia euclídea al cuadrado en este espacio se acumula en un entero de 32 bits. Así se ejecuta el modelo ligero en C++ con tres bytes de pesos por clase, sin intérprete ni arena. Comprueba la diferencia de métricas float/int8 y exige concordancia de salidas int8 al reproducir los vectores de prueba en placa. Valida el candidato antes de sustituir `model.h` por el artefacto entrenado.

## Estructuras y componente Java

El buffer circular almacena seis `Sample` y actualiza dos sumas con cada inserción. Inserción, consulta de extremos y extracción de características toman O(1) en tiempo y O(W) de espacio para W muestras. La clasificación es O(C × F) para C clases y F características. Sus pesos ocupan O(C × F) de Flash.

El scraper preserva su índice persistente B-tree, que busca una revisión de NOAA en O(log N) para N revisiones. El cliente Java inspecciona las ediciones que el dashboard ya consume. `Bulletin` valida campos y conserva procedencia, `BulletinIndex` usa `HashMap` por revisión y `TreeMap` por fecha y `BulletinTool` consulta `/api/agroclima` en localhost. Con N boletines y D fechas distintas, construir el índice toma O(N log(D+1)) esperado, consultar una revisión O(1) esperado y consultar K resultados de un rango de fechas O(log(D+1) + K). El cliente utiliza O(N) memoria y la API local ofrece las últimas 12 revisiones. [Estructuras del scraper](r5.md#estructuras-y-coste) · [Gson](https://google.github.io/gson/)

```powershell
New-Item -ItemType Directory -Force .venv/java/classes | Out-Null
Invoke-WebRequest 'https://repo.maven.apache.org/maven2/com/google/code/gson/gson/2.15.0/gson-2.15.0.jar' -OutFile .venv/java/gson-2.15.0.jar
javac -encoding UTF-8 -cp .venv/java/gson-2.15.0.jar -d .venv/java/classes java/r5/src/*.java java/r5/test/*.java
java -ea -cp '.venv/java/classes;.venv/java/gson-2.15.0.jar' BulletinIndexTest
java -cp '.venv/java/classes;.venv/java/gson-2.15.0.jar' BulletinTool 5173 2026-11-01 2026-11-30
```

## Recursos y evidencia de laboratorio

| Medición de compilación del candidato | Bytes | Denominador | Utilización |
| --- | ---: | ---: | ---: |
| Programa, salida de Arduino | 361 425 | Partición de aplicación 3 145 728 | 11,49 % |
| Binario de aplicación generado | 361 584 | Flash física nominal 16 777 216 | 2,16 % |
| RAM estática, salida de Arduino | 24 956 | Presupuesto de la compilación 327 680 | 7,62 % |
| Pesos preliminares int8 | 9 | 36 bytes para los mismos pesos float32 | 25 % |

Con el puente USB y el monitor serial cerrados, solicita el benchmark de 256 ejecuciones después de 16 de calentamiento. Sustituye el puerto por el enumerado y añade `--vectors data/datasets/<version>/test-vectors.json` una vez instalado el modelo entrenado correspondiente. Guarda aparte la compilación con placa, núcleo, reloj y puerto utilizados.

```powershell
python hardware/verify_tinyml.py --port COM8 --out data/esp32-benchmark.json
```

El benchmark guarda la media, desviación estándar y máximo de ciclos de la búsqueda de clase, el tiempo del lote, el rendimiento con sobrecarga del benchmark y el estado de heap, stack y PSRAM. Divide los ciclos por MHz para obtener microsegundos si el reloj se mantiene fijo. El stack reporta el mínimo libre de la tarea que ejecuta la inferencia. Mantén por separado la RAM estática y el pico de heap. Los ciclos observados incluyen la sobrecarga del contador, la llamada y las posibles interrupciones. Evalúa aparte el tiempo de I²C y transporte USB. Hace falta medir físicamente la energía. Con un medidor de corriente suficientemente rápido registra tensión y corriente en la entrada de alimentación, mide reposo y un lote de inferencias y divide la diferencia de energía por la cantidad de ejecuciones. Si se usa un multímetro lento, reporta consumo medio de estados sostenidos y declara la resolución obtenida.

Un Raspberry Pi Pico RP2040 ofrece 264 KiB de SRAM, 2 MiB de Flash, I²C y USB. Es una alternativa plausible para el núcleo de clasificación, dados los pesos y el tamaño estático actuales. La cifra completa del firmware ESP32 no es una medición del Pico. Repite la compilación y compara recursos, latencia y energía antes de justificar si hacen falta dos núcleos, PSRAM o conectividad inalámbrica. [Espressif ESP32-S3](https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32s3/esp32-dev-kits-en-master-esp32s3.pdf) · [Raspberry Pi Pico](https://www.raspberrypi.com/products/raspberry-pi-pico/)

## Preparación web e informe

Mantén el puente y la cola durable de envíos en el equipo con el puerto COM. Para una futura versión accesible por URL, publica un servicio de ingestión HTTPS autenticado por dispositivo, con rotación de credenciales, reintentos e idempotencia por `(origen, estación, sesión, secuencia)`. Usa una base administrada para consultas remotas, conserva hora de adquisición y recepción y protege la interfaz de lecturas con autenticación. La página puede consumir ese servicio con acceso de solo lectura. Prueba pérdida de conexión, recuperación de cola, límites y permisos en un entorno local antes de migrar. La subida de archivos del lote y la publicación requieren aprobación expresa.

El [borrador IEEE en inglés](ieee/agroedge.tex) recoge la arquitectura y las mediciones de compilación. Para la versión de 6–10 páginas quedan por incorporar el diagnóstico del beneficiario, la evaluación del conjunto propio, el ensayo en placa y la medición de consumo.

## Verificación del 23 de noviembre de 2026

| Comando o prueba | Resultado |
| --- | --- |
| `npm.cmd test` en el commit `a85c35f` | Siete pruebas superadas |
| `npm.cmd test`, `npm.cmd run check`, `npm.cmd run build` | Ocho pruebas, TypeScript y compilación de producción superados |
| `npm.cmd run test:app` | Integración HTTP en base aislada, con fixture serial, inferencia USB, exportación y persistencia |
| `python -m unittest discover -s tests -v` | 12 pruebas superadas, nueve de NOAA y tres del entrenamiento con datos de prueba |
| `arduino-cli compile` | Binario y tamaño estático para ESP32-S3 verificados |
| `BulletinIndexTest` y `BulletinTool` | Duplicación y orden verificados en pruebas, y revisión NOAA consultada desde el dashboard local |
| `python hardware/bridge.py --list` y `arduino-cli board list` | Windows no enumeró puertos ni placa. Ensayo, inferencia y métricas de ejecución en placa pendientes |

La descarga y la programación de NOAA se registraron en la [verificación R5](r5-verificacion.md#verificación-en-windows--23-de-noviembre-de-2026). El ensayo prioritario es conectar la placa, asegurar la recuperación del sketch funcional y verificar las seis primeras lecturas del candidato en una base de ensayo.
