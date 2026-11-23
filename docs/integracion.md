# Integración AgroEdge IA

## Medición HTTP

El ESP32 o Java envía un `POST` con `Content-Type: application/json` y `Authorization: Bearer <token>`. Usa `/api/measurements/wifi` para Wi-Fi y `/api/measurements/usb` si Java actúa como lector serial. El puente USB incluido entrega los registros directamente al mismo validador de la aplicación.

Ejemplo de **estructura**, con valores ilustrativos. Sustituye las mediciones, IDs y fechas por los obtenidos del dispositivo. Envía `classification` solo cuando el ESP32 haya ejecutado el modelo.

```json
{
  "schemaVersion": 1,
  "stationId": "TOCA-01",
  "sessionId": "arranque-01",
  "sequence": 1,
  "acquiredAt": "2026-11-19T19:00:00Z",
  "temperature": 15.2,
  "humidity": 72.4,
  "pressure": 735.1,
  "origin": "WIFI",
  "classification": {
    "source": "ESP32",
    "state": "OK",
    "label": "CLASE_CONFIGURADA",
    "score": 0.54,
    "modelVersion": "modelo-v1",
    "inferredAt": "2026-11-19T19:00:00Z"
  }
}
```

| Campo | Contrato |
| --- | --- |
| `schemaVersion` | Entero `1`. |
| `stationId`, `sessionId` | Identificadores de hasta 100 caracteres ASCII. Inicial alfanumérica. Además se admiten punto, guion, guion bajo y dos puntos. Usa un ID de sesión distinto por arranque cuando se reinicia la secuencia. |
| `sequence` | Entero positivo desde 1, creciente por estación y sesión. Si se reenvía una lectura, conserva la secuencia y el mismo JSON. |
| `id` | Opcional. Con el mismo alfabeto de los identificadores. Si se omite, se genera un ID estable a partir del origen, la estación, la sesión y la secuencia. |
| `acquiredAt` | ISO 8601 con segundos y zona explícita. UTC recomendado. Wi-Fi lo requiere. Para USB sin RTC, se puede omitir o enviar `null`; la estación usa la hora de recepción y señala `timeSource: "RECEIPT"`. |
| `temperature`, `humidity`, `pressure` | Números en °C, % y hPa. Rango del validador: −40 a 85 °C, 0 a 100 %, 300 a 1100 hPa. Envía `null` si un valor falta. Si la biblioteca devuelve presión en Pa, divide por 100 antes de enviar. |
| `origin` | Opcional al enviar. Si está presente, coincide con el transporte del endpoint. |
| `dataKind`, `testTransport` | Los determina el servidor. Los endpoints reales rechazan `dataKind: "SIMULATED"` y cualquier `testTransport` declarado. |
| `classification` | Opcional o `null`. `source: "ESP32"` y `state: "OK"` requieren clase, puntuación de 0 a 1, versión e instante ISO 8601. Para `state: "ERROR"` envía `label: null`, `score: null`, versión e instante. |

El servidor añade `receivedAt`, `timeSource`, `dataKind`, `quality`, `missingBefore` e `issues`. Convierte fechas explícitas a UTC. Una lectura con algún valor ausente se conserva como `MISSING`; un tipo o valor fuera de rango se conserva como `INVALID`. En ambos casos el campo afectado queda nulo y los demás se preservan. `ANOMALY` marca una desviación estadística a partir de al menos 15 lecturas válidas previas de la misma sesión y estación, con umbral de 3.5 desviaciones y un mínimo de dispersión por variable. `missingBefore` registra los saltos de secuencia observados al llegar la muestra. Una llegada tardía se conserva con su propio ID.

**Respuestas.** HTTP 201 con `{"status":"stored","reading":{...}}` al guardar. HTTP 200 con `{"status":"duplicate","reading":{...}}` ante reintento idéntico. HTTP 409 al reutilizar ID o secuencia con datos distintos. HTTP 400 ante esquema, fecha, fuente, inferencia o cuerpo incompatible. HTTP 403 si el token es incorrecto o falta. El límite del cuerpo JSON es 16 KiB.

## Protocolo serial

UART serial USB, 115200 baudios por defecto, 8 bits, sin paridad, 1 bit de parada. Envía **un objeto JSON UTF-8 por línea** con LF o CRLF y sin prefijos. El puente puede informar líneas que no son JSON y reabrir el puerto si se desconecta. Con un dispositivo sin reloj, mantén fija la secuencia en cada reenvío de la misma muestra para evitar una segunda entrada con diferente hora.

## Endpoints para Java y la interfaz

Actualmente Next.js tiene el único servicio HTTP y SQLite conserva la información. Java puede comenzar enviando registros a los endpoints autenticados. Cuando Java implemente su propia recepción, almacenamiento y consultas, deberá exponer este contrato y asumir esa responsabilidad en lugar del almacén local de referencia.

| Método y ruta | Uso |
| --- | --- |
| `POST /api/measurements/wifi` | Recepción autenticada del ESP32 o del servicio Java. |
| `POST /api/measurements/usb` | Recepción autenticada si Java se encarga de leer el serial. |
| `GET /api/measurements?origin=USB&order=desc&page=0` | `rows`, `total`, `page`, `size`. Filtros opcionales `station`, `session`, `quality`, `from` inclusivo, `to` exclusivo, en ISO 8601. |
| `GET /api/sessions?origin=WIFI` | Resumen por estación y sesión con conteo y fechas UTC. |
| `GET /api/snapshot?origin=SIMULATION` | Estado, medición reciente, serie, resumen de sesiones, inferencia más reciente, alertas y estadísticas. `latest` conserva la última lectura de la estación o sesión. `latestInPeriod` devuelve la última lectura que cumple todos los filtros aplicados o `null`. |
| `GET /api/forecast` | Pronóstico horario externo y periodos de 24/48 h. HTTP 503 si no se puede consultar. |
| `POST /api/simulation` | `action` de tipo `start`, `pause`, `stop`, `reset` o `speed` y `config` con `seed`, `scenario`, `intervalMs`, `variation` y `tinyML`. |
| `GET /api/export?origin=USB&format=xlsx&order=asc` | CSV o XLSX del conjunto filtrado, hasta 25 000 filas. Opcionales `columns` (claves separadas por coma) y `delimiter` (`comma`, `semicolon`, `tab`). |
| `POST /api/import?format=csv` | Bytes del archivo. Valida nombres, unidades, tipos y fechas antes de agregar registros. Devuelve `inserted` y `duplicates`. Límite 25 MiB y 25 000 filas. |
| `GET /api/usb/ports` · `POST /api/usb` | Listar puertos, iniciar (`action:"start",port,baud`) o detener (`action:"stop"`) el puente. |
| `POST /api/test/usb` · `POST /api/test/wifi` | Pruebas locales habilitadas con `AGROEDGE_ALLOW_TESTS=1`. Guardan exclusivamente `SIMULATION` y `SIMULATED`, con `testTransport`. |

Para repetir los fixtures con el servidor local iniciado y la opción de pruebas habilitada, ejecuta `node scripts/replay-fixtures.mjs` y mira Historial en el modo Simulación. Los archivos de exportación incluidos son de este modo. Al entrenar, filtra `dataKind=REAL` y selecciona solo registros y etiquetas que hayan sido verificados según el protocolo del proyecto. Los ejemplos, las puntuaciones simuladas y las salidas de pruebas de transporte quedan fuera del entrenamiento.

