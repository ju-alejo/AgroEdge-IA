# Evidencias de evaluación

El ZIP de código reúne las rutas siguientes junto con el proyecto. Las bases, los respaldos y los registros de campo se distribuyen fuera del historial de Git. Los archivos de resultados y las capturas reproducen los resultados ya registrados para `d045786` y `exposure-tflm-2c4870d61d3f`.

## Auditoría, piloto y campaña final

| Ruta en el ZIP | Contenido |
| --- | --- |
| `datasets/2026-11-23_piloto/` | Exportación original, observaciones, reprocesamiento v1 y v2 y contexto Open-Meteo. El piloto queda separado de las particiones definitivas. |
| `datasets/2026-11-24_exportaciones/` | Exportaciones CSV/XLSX originales, observaciones y gráficas de las seis sesiones de entrenamiento, validación y prueba. |
| `campana_final/auditoria.json` y `sesiones.csv` | 2.823 lecturas auditadas. Coherencia de las exportaciones con el respaldo SQLite y conteos por sesión. |
| `campana_final/etiquetado/` | Etiquetas de exposición observadas, cobertura y cortes de las tres particiones. |
| `campana_final/modelo-tflm/` | Modelo congelado descrito, comparación float32/int8, evaluación, ventanas, vectores, diagnóstico de saturación, compilación, banco y estimación energética. El FlatBuffer int8 y su encabezado se ubican en `hardware/esp32_tinyml/`. |

## Modelo en placa y demostraciones

- `campana_final/modelo-tflm/benchmark-fisico.json` registra las 256 inferencias medidas, los recursos y la paridad de los 63 vectores. `integracion-usb/` conserva seis clasificaciones reales recibidas y la captura del panel.
- `demostraciones/` contiene la recepción USB en el invernadero y el exterior, los registros del traslado y las vistas del pronóstico antes y después de la actualización. Las lecturas de demostración quedan fuera de las particiones experimentales.
- `figuras.csv` identifica observaciones, fechas y pies de las imágenes seleccionadas. Las gráficas de las tres particiones se conservan junto a sus datos auditados.

## Meteorología, pruebas e historial

- `meteorologia/` conserva las evidencias de NOAA, la incidencia inicial de la tarea Eltiempoen.net y la actualización HTTPS exitosa de las 21:10 del 24 de noviembre. `Bases_de_consulta/` contiene las copias SQLite de ambas fuentes para revisión local.
- `verificacion/` contiene la reproducción del problema LF/CRLF, los resultados de las pruebas en una extracción aislada y la comprobación de compilaciones e integridad. `Verificacion_Distribucion.json` indica el resultado de cada procedimiento.
- `Historial_Git.txt` identifica la procedencia de los cambios según el historial real. `SHA256SUMS.txt`, en la raíz del ZIP, permite cotejar los bytes de la distribución.

Las SQLite empacadas son copias de evidencia. Para ensayar la adquisición, utiliza otra base de mediciones. Las capturas HTML archivadas se pueden inspeccionar como texto fuera de línea.
