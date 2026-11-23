# Verificación de AgroEdge IA

## Versión 0.1.1 · 21 de noviembre de 2026

- Compilación de producción, revisión TypeScript y siete pruebas automatizadas aprobadas en Windows con Node.js 24.14.0. Los dos ejemplos exportados en la versión 0.1.0 se importan y se reconocen como duplicados entre sí.
- Se probó la última lectura dentro de un intervalo, incluido el límite final exclusivo. También se comprobó que USB y Wi-Fi rechazan registros marcados como simulados. Un reintento de una prueba por su mismo transporte se reconoce como duplicado.
- Las rutas compiladas procesaron el fixture serial, la autenticación, las inferencias de prueba, las exportaciones y la reapertura de SQLite. El servidor de producción arrancó, pero el entorno de prueba bloqueó la conexión a `127.0.0.1`. Por eso se ejecutó la prueba directa `npm.cmd run test:app -- --routes`. La revisión interactiva y la conexión con los dispositivos físicos siguen pendientes.

## Versión 0.1.0 · 19 de noviembre de 2026

Pruebas realizadas en Windows con Node.js 24.14.0.

| Función | Resultado |
| --- | --- |
| TypeScript, compilación y arranque | Comprobados con Next.js 16.3.4. El panel compilado respondió HTTP 200 en el equipo local. |
| Generación simulada | Probados semilla, continuidad, cambio de escenario, inicio, pausa, reanudación, cambio de velocidad, detención y reinicio con preservación de sesiones. |
| Historial y persistencia | Probados registro normal, fechas UTC, separación de orígenes, deduplicación, conflicto de secuencia, detección de salto, nulos y anomalías. Los registros permanecen después de reabrir SQLite y reiniciar el servidor. |
| CSV y Excel | Descargas reales probadas desde el endpoint de exportación para SIMULATION, USB y WIFI en una base temporal de prueba. Probados filtros, orden, columnas proyectadas, los tres delimitadores y la importación con deduplicación. Excel contiene las hojas Mediciones y Metadatos. |
| Importación incompatible | Probados encabezados y unidades incorrectos, tipos y fechas incompatibles y conflicto que revierte la importación completa. |
| Puente USB | El parser Python procesó un archivo de líneas seriales y el endpoint de prueba marcó los datos como SIMULATED. El puerto COM físico y la reconexión con el dispositivo requieren validación en el laboratorio. |
| Recepción Wi-Fi | Probados HTTP local, autenticación, duplicados y almacenamiento. El fixture visible queda como SIMULATED. El envío desde el ESP32 y la conectividad de la red del laboratorio requieren validación física. |
| TinyML | Probada la recepción del objeto de clasificación y el rechazo de una fuente incompatible. Los datos de prueba con forma ESP32 solo se usaron en la base temporal. Pendiente un modelo entrenado y ejecutado en el microcontrolador. |
| Pronóstico | Se comprobó una respuesta real de Open-Meteo con 48 valores horarios. El cálculo de acumulación e indisponibilidad de variables se verificó con una respuesta controlada. |
| Inspección de interfaz | Se verificó la respuesta HTML del panel compilado. La inspección interactiva en navegador quedó pendiente porque el control del navegador no pudo confirmar la URL local en Windows. |
| Integración Java | Contrato y rutas definidos. Pendiente conectar el servicio Java definitivo del proyecto. |

Los ejemplos de la carpeta `examples` son exclusivamente de simulación. Los valores enviados a los endpoints reales en la prueba automatizada se almacenaron solo en una base SQLite temporal aislada que se eliminó al terminar la prueba.

**Procedencia del código original.** Copia local del archivo `DataCity_AI_Beta.zip`, SHA-256 `5a188f93d76a87006a6dc506803bb2c6abf5481ead9f7aca165d341928302ef6`. La copia de seguridad y la publicación original permanecen intactas.

