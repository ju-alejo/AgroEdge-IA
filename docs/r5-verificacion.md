# Verificación de AgroEdge IA

## Versión 0.2.1

El 22 de noviembre de 2026 se instalaron BeautifulSoup 4.14.3 y Soup Sieve 2.8.3 desde archivos locales con `pip --no-index`. Las nueve pruebas de R5 pasaron en Windows.

| Comprobación | Resultado |
| --- | --- |
| Extracción | El HTML original de NOAA produjo la fecha **12 de noviembre de 2026**, el estado **Advertencia de El Niño**, la sinopsis y la procedencia **NOAA / Climate Prediction Center** con el enlace oficial. |
| SQLite | Al procesar dos veces el mismo HTML se registraron `NUEVA` y `DUPLICADA`. La base temporal conservó una edición y dos entradas en la bitácora. |
| Panel Next.js | `GET /api/agroclima` devolvió HTTP 200 y recuperó desde SQLite la edición recién procesada. El componente React mostró la fecha, el estado, la sinopsis y el enlace. [Vista renderizada con los datos de la prueba](r5-panel-verificado.html) |

La comprobación del panel se hizo sobre la ruta compilada y el componente React, sin abrir un navegador interactivo. La extracción utilizó el HTML de NOAA adjunto, cuya huella SHA-256 coincide con la que aparece más abajo. La compilación de producción, las siete pruebas de dominio y la integración de las rutas compiladas también habían pasado en Windows. La sección **Reproducir las pruebas** contiene los comandos.

## Registro original de la versión 0.2.0

Pruebas ejecutadas en Windows el 21 de noviembre de 2026, hora de Bogotá, con Node.js 24.14.0, Next.js 16.3.4, Python 3.14 y Requests 2.34.2. El punto de partida fue el código de entrega de AgroEdge IA 0.1.1. Todas las bases utilizadas en estas pruebas se crearon en carpetas independientes. El ZIP de actualización carece de bases operativas de mediciones.

| Comprobación | Resultado observado |
| --- | --- |
| 1. Extraer HTML real | Se consultó la página publicada por NOAA y se procesó el archivo HTML que la usuaria guardó desde su navegador. El archivo tiene 15 647 bytes. El comentario de procedencia del navegador identifica la URL del CPC. Python extrajo el título de la discusión, la publicación del **12 de noviembre de 2026**, el estado **Advertencia de El Niño**, su sinopsis, el emisor y el enlace. La sinopsis procede del párrafo marcado en el HTML. |
| 2. Almacenar y recuperar | La primera ejecución por CLI devolvió `NUEVA`. Tras cerrar Python y abrir otra conexión se recuperó una revisión con sus campos, el HTML, las huellas y la marca de captura desde archivo. |
| 3. Repetir | La segunda ejecución sobre los mismos bytes devolvió `DUPLICADA`. En SQLite quedó una revisión y dos entradas en la bitácora. El primer procesamiento fue a las 21:56:04 y el segundo a las 21:56:24 de Bogotá. Se probó también una modificación controlada en un archivo temporal para comprobar el versionado ante una corrección. |
| 4. Mostrar el boletín en AgroEdge | El HTML del dashboard de producción contiene el boletín archivado de arranque. La prueba crea otra base con dos extracciones, invoca la ruta compilada `GET /api/agroclima` y renderiza el componente React del dashboard con esa respuesta. Comprobó título del panel, fecha, estado, sinopsis, fuente, enlace y procedencia de la copia; la respuesta local contiene una sola edición y `bundled=false`. La evidencia renderizada incluida en esta edición corresponde a la prueba posterior de 0.2.1. |
| 5. Repetir según la política | Se ejecutaron dos ciclos del bucle `watch` con reloj controlado y el HTML auténtico. El primer ciclo insertó una edición y el siguiente la reconoció como duplicada. Otra prueba recorrió tres instantes con transporte controlado y obtuvo `NUEVA → EN_ESPERA → DUPLICADA`. En el instante intermedio no se solicitó ninguna página. Se verificaron reglas robots, demoras, bloqueo y `Retry-After`. El registro de la tarea diaria se previsualizó mediante `-WhatIf`. |
| Sincronizar | Se exportó la base a JSON, se importó en una segunda carpeta y se repitió la operación. La primera importación incorporó una revisión y la segunda incorporó cero. Una prueba alteró la huella de una entrada y verificó la reversión del lote entero. |
| Regresiones | Pasaron nueve pruebas Python R5 y siete pruebas de dominio de la aplicación anterior. También pasaron TypeScript, la compilación de producción y la integración de rutas compiladas con simulación, fixture serial, TinyML de prueba, CSV, XLSX y persistencia. El servidor de producción arrancó en un puerto local de prueba. Se conservaron los adaptadores, el contrato y el código de Open-Meteo. |

**Huella SHA-256 del HTML guardado**

```text
56ca036e321bf1e84609f0f48d208205aa4c7f39e1ae6d24f86b681f0e7a6323
```

**Huella de la revisión editorial extraída**

```text
faf0fd27e824d3497cb107603392756239b285754a9fa727ec017a1f07f115e6
```

El HTML original utilizado está en `tests/fixtures/noaa-enso-es-2026-11-12.html`. El archivo incluye referencias a recursos gráficos externos del original; el parser solo necesita los bytes del HTML. El resumen JSON que alimenta el primer arranque se generó a partir de la fila almacenada y se contrasta con la extracción en la prueba de integración.

## Reproducir las pruebas

Desde la raíz del proyecto con las dependencias del README instaladas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_r5.py -v
npm.cmd test
npm.cmd run check
npm.cmd run build
npm.cmd run test:app -- --routes
$env:AGROEDGE_PYTHON = (Resolve-Path .venv\Scripts\python.exe).Path
node scripts/verificar-panel-r5.mjs
```

Para guardar otra evidencia puntual de la vista renderizada en un archivo nuevo:

```powershell
node scripts/verificar-panel-r5.mjs --html=mi-evidencia-r5.html
```

La prueba de interfaz usa una base temporal propia. `AGROEDGE_PYTHON` indica a Node qué intérprete tiene instaladas las dependencias del scraper.

## Alcance de la validación

La adquisición realizada en esta revisión combina una página auténtica consultada en el navegador y el análisis reproducible de la copia de ese HTML en Python. Al ejecutar `fetch` en el entorno de desarrollo, la resolución DNS hacia NOAA falló antes de obtener `robots.txt`. El proceso registró un error HTTPS y conservó las ediciones anteriores. La prueba de conectividad directa desde Requests hacia NOAA queda pendiente en un equipo con salida a Internet. Una ejecución correcta se identifica por el medio `HTTPS`, el campo `live_seen` y el resultado registrado. La captura entregada conserva `live_seen=null`.

La verificación de la vista utilizó el HTML de producción y el componente React renderizado con la respuesta real de la ruta compilada. Microsoft Edge abrió la evidencia estática y su DOM contenía el estado ENSO extraído. Al intentar abrir el servidor local de prueba desde Edge, el entorno devolvió `ERR_NETWORK_ACCESS_DENIED`. La verificación interactiva de extremo a extremo con la aplicación local queda pendiente. En una instalación con acceso normal se puede ejecutar `npm.cmd run dev`, abrir el panel principal, procesar el HTML y comprobar que la etiqueta de edición incluida cambia al dato recuperado de SQLite en el plazo de un minuto.

La programación se probó con reloj controlado. La tarea de Windows y el flujo de GitHub se entregan listos para su activación posterior. El equipo físico, la consulta en vivo a Open-Meteo y una ejecución alojada en GitHub quedan fuera de las validaciones realizadas en esta actualización. Los adaptadores USB y Wi-Fi se comprobaron con los ensayos de regresión de 0.1.1.

[R5 y guía de integración](r5.md) · [Página oficial contrastada](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc_Sp.shtml)

## Verificación en Windows · 23 de noviembre de 2026

- `python -m unittest discover -s tests -p test_r5.py -v` superó nueve pruebas, entre ellas dos ciclos del recolector con reloj controlado, deduplicación, respeto de `robots.txt` y aislamiento de la base de mediciones.
- `python scraper/agroclima.py --dir .venv/r5-verificacion fetch` obtuvo por HTTPS la edición del 12 de noviembre de 2026, con estado **Advertencia de El Niño**, sinopsis y procedencia NOAA/CPC. Se obtuvo la revisión `faf0fd27e824d3497cb107603392756239b285754a9fa727ec017a1f07f115e6`. Un segundo comando devolvió `EN_ESPERA` con próxima consulta desde el 24 de noviembre a las 16:19, hora de Bogotá.
- Tras `PRAGMA quick_check`, se copió la base R5 de verificación a `data/agroclima.sqlite` mediante el respaldo de SQLite y creación exclusiva del destino. La API `GET /api/agroclima` leyó la revisión local, con `bundled=false` y `live_seen` informado. `BulletinTool` encontró la misma revisión en la API por hash.
- La tarea local **AgroEdge IA - Boletin R5** quedó programada diariamente a las 16:30, hora de Bogotá. Su inicio manual el 23 de noviembre devolvió código `0` dentro de la ventana de espera. La primera consulta programada está prevista el 24 de noviembre y queda pendiente verificar su resultado con `Get-ScheduledTaskInfo` y `scraper/agroclima.py status`.
- El adaptador de Open-Meteo recuperó por HTTPS el pronóstico para el punto de referencia de Toca y devolvió ambos horizontes de 24 y 48 horas. La previsión se mantiene en su ruta independiente.

## Ejecución automática y deduplicación · 24 de noviembre de 2026

La tarea **AgroEdge IA - Boletin R5** se ejecutó a las 16:30:01 de Bogotá con `LastTaskResult=0`. La siguiente ejecución quedó para el 25 de noviembre a las 16:30:00. Se contrastaron el Programador de tareas, el registro `status` y la captura del usuario. Las dos consultas HTTPS recuperaron el boletín del 12 de noviembre. SQLite conserva una sola edición y dos ejecuciones.

| Fecha de recuperación UTC | Resultado | Ediciones acumuladas |
| --- | --- | ---: |
| 23 de noviembre, 22:19:18 | `NUEVA` | 1 |
| 24 de noviembre, 21:30:06 | `DUPLICADA` | 1 |

Ambas ejecuciones tienen revisión `faf0fd27e824d3497cb107603392756239b285754a9fa727ec017a1f07f115e6` y SHA-256 del HTML `7d3f2388a01d7d6015ecadf38edf2f98252a480eac03494878fb1188cbd01b10`. La captura `R5_NOAA_Deduplicacion_2026-11-24.png` y `R5-verificacion-2026-11-24.json` están en `C:/AgroEdge/output/evidencia/R5_WebScraping`.

Se registró la tarea independiente **AgroEdge IA - Pronostico Toca R5** a las 20:45 de Bogotá. La primera ventana elegible de la base era el 24 a las 20:40:34. El Programador confirmó la primera ejecución prevista para el 24 a las 20:45. El scraper conserva el límite persistente, comprobación de `robots.txt`, atribución y respeto de `Retry-After`. El registro de esa primera ejecución queda pendiente hasta que se cumpla el horario.

La reproducción de la captura HTML del 23 en una SQLite de ensayo produjo `NUEVA` y `REPETIDA`, con la misma revisión `e84c8bd42792275ae17476a8e84feefda810910bebc31d72a920f3de7a459c63` y 48 horas. La prueba usó el HTML archivado y el 24 quedó reservado para la siguiente consulta HTTPS elegible.

```powershell
Get-ScheduledTaskInfo -TaskName 'AgroEdge IA - Boletin R5','AgroEdge IA - Pronostico Toca R5'
& .venv/r5-python/Scripts/python.exe scraper/agroclima.py status
```

### Demostración del pronóstico agrícola antes de las 20:45

El 24 de noviembre se verificaron visualmente los dos paneles en **Pronóstico agrícola**. Open-Meteo mostraba sus horizontes de 24 y 48 horas, con hora de consulta **20:27:51** en Bogotá. Eltiempoen.net mostraba cuatro filas vigentes para Toca, de las **20:00, 21:00, 22:00 y 23:00**, de la captura HTTPS del 23 de noviembre a las **21:40:34**. El panel incluía su procedencia y atribución. El filtro de vigencia explica por qué quedaban cuatro horas de la captura previa. La evidencia corresponde al estado anterior al horario automático de las 20:45. Ambos paneles se conservaron como contexto meteorológico externo. [Vista de ambos paneles](C:/AgroEdge/output/evidencia/Demostracion_Final/R5_Pronostico_Agricola_Antes_Actualizacion.png) · [Detalle y procedencia de Toca](C:/AgroEdge/output/evidencia/Demostracion_Final/R5_Eltiempoen_Procedencia_y_Datos.png)
