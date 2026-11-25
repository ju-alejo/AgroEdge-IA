# Validación funcional de AgroEdge IA

**Versión:** 1.0. **Fecha de revisión documental:** 25 de noviembre de 2026.  
**Estado:** documento terminado para publicación por Sergio Andrés Guerrero Alba.  
**Modalidad de esta revisión:** contraste de documentación, registros técnicos, manifiestos y resultados archivados. No se realizó una nueva adquisición física, recarga de firmware ni sesión de uso atribuida a Sergio.

## 1. Sistema y versiones de referencia

AgroEdge IA integra una estación ESP32-S3 con sensores AHT20 y BMP280, un puente USB en Python, una aplicación local Next.js con interfaz React y persistencia SQLite. Registra temperatura ambiental, humedad relativa del aire y presión atmosférica; presenta historial, gráficas, calidad de datos, exportaciones y clasificación TinyML de perfiles de exposición. También muestra fuentes meteorológicas externas con su procedencia y fecha [F1–F4].

| Referencia | Identificación y alcance |
| --- | --- |
| Paquete definitivo de evidencias | `AgroEdge_IA_Evidencias_Informe_Final.zip`; corte técnico del 24/11/2026, versión 0.2.1, commit `d045786a1b0dd12cf3b312f07d1910b114a40c60`. |
| Distribución de código verificada | `JuanCastillo_SergioGuerrero_codigo.zip`; su `evidencias/Verificacion_Distribucion.json` registra el commit `3ac2a434f824dd7a3e7592bdb13b1fa13330de8b` y la base funcional anterior. Conserva pruebas de distribución y evidencia histórica. |
| Modelo final | `exposure-tflm-2c4870d61d3f`, TensorFlow Lite Micro int8, 1.160 bytes. |
| Firmware instalado durante el banco archivado | Imagen de aplicación de 401.088 bytes; SHA-256 `1a3b357c4876c3a445255819aa66a3ddc3d013b1457adb94abca833522118de5`. |
| Compilación de verificación de la distribución | Imagen de 401.296 bytes; SHA-256 `74a97899c60a38185846b95fc0b835e4879dced55156892f1ad9b1cb12d5ff7c`. El registro indica que no se cargó a la ESP32 durante esa comprobación. |

Ambas imágenes contienen el modelo final exacto, según la verificación archivada [F3]. El banco físico corresponde a la imagen instalada que se conserva como evidencia; no se atribuyen sus mediciones a la recompilación posterior. La distribución también incluye documentos históricos con estados anteriores: para el cierre de funciones se utiliza el registro de distribución y la evidencia final del 24 de noviembre.

## 2. Funciones y criterios de interpretación

| Función | Comportamiento documentado | Criterio de revisión |
| --- | --- | --- |
| Adquisición USB | Recepción de JSON serial del dispositivo a través del puente Python. | Identificar estación, sesión, secuencia y procedencia `REAL/USB`; conservar la hora `RECEIPT` cuando no hay reloj propio. |
| Historial y gráficas | Consulta por origen, estación, sesión, fecha y calidad. | Comparar conteos y límites de recepción con la exportación y la auditoría de la misma sesión. |
| Calidad de datos | Conservación de valores ausentes, inválidos y desviaciones estadísticas, con sus motivos. | Distinguir `MISSING`, `INVALID`, `ANOMALY` y `VALID`; una alarma estadística no demuestra avería del sensor. |
| Persistencia y duplicados | SQLite conserva lecturas e inferencias; los reintentos idénticos no crean una lectura adicional. | Cotejar identidad, secuencia, conflictos y recuperación después de reabrir una base de ensayo. |
| Exportación e importación | CSV y XLSX con unidades, selección de columnas y metadatos. | Verificar correspondencia con el historial filtrado y preservación de procedencia; probar importación exclusivamente en una copia aislada. |
| Simulación y pruebas de transporte | Datos generados o fixtures separados de la adquisición real. | Mantener `SIMULATION/SIMULATED` y la identificación del transporte de prueba; excluirlos de entrenamiento y evidencia física. |
| Clasificación TinyML | Perfiles estimados de invernadero y exterior, versión de modelo, estado, puntuación y tiempo de ejecución. | Contrastar la salida con la observación física independiente. La puntuación final es un margen al umbral, no una probabilidad calibrada. |
| Pronóstico externo | Open-Meteo mediante API y pronóstico de Toca de Eltiempoen.net mediante HTML. | Mostrar proveedor, fecha de captura, periodo de validez y valores ausentes sin sustituirlos por cero. |
| Contexto ENSO | Boletín NOAA con revisiones y deduplicación. | Interpretarlo como contexto estacional; no como observación instantánea de la estación ni etiqueta del modelo. |
| Cliente Java | Consulta e indexación de boletines mediante `HashMap` y `TreeMap`. | Revisar la comprobación de revisiones, fechas, duplicados y conflictos. No presentarlo como el backend principal de la aplicación. |

Fuentes: [F1–F4]. El apoyo al riego usa información ambiental y meteorológica para contrastarla con la observación en el lote. La aplicación no incorpora un sensor de humedad del suelo ni acredita control automático del riego o predicción local de lluvia mediante TinyML.

## 3. Procedimiento de revisión funcional reproducible

El procedimiento siguiente describe cómo repetir la revisión sin alterar la evidencia. La tabla de la sección 4 ya está resuelta con las comprobaciones existentes; no es un formulario pendiente de diligenciar.

1. **Identificar la versión.** Consultar `06_Version_Congelada/version.json` en el paquete de evidencias y `evidencias/Verificacion_Distribucion.json` en la distribución de código. Registrar qué versión corresponde a cada resultado y cotejar `SHA256SUMS.txt` dentro de cada ZIP mediante lectura, sin volver a comprimirlos.
2. **Trabajar en una extracción independiente.** Utilizar una carpeta nueva y bases copiadas o temporales para las operaciones de adquisición, importación, simulación o replay. Para examinar una base archivada autónoma, abrirla con SQLite en modo de solo lectura; en esta revisión se utilizó una URI con `mode=ro&immutable=1` sobre el respaldo cerrado. Las bases originales de campo permanecen fuera del flujo de escritura.
3. **Separar los orígenes.** Consultar primero una sesión archivada de USB y luego los fixtures de simulación. Verificar los campos de procedencia, estación, sesión y tiempo. La prueba del contrato HTTP Wi-Fi acredita el transporte con fixtures; para afirmar adquisición física Wi-Fi se necesita evidencia distinta de la USB.
4. **Conciliar historial y exportaciones.** Comparar el número de lecturas, los identificadores, las secuencias, las unidades y la primera y última recepción de C–F. Verificar las copias CSV/XLSX frente a la auditoría y al respaldo. Mantener visibles las lecturas de traslado, estabilización y anomalía en la evidencia conservada.
5. **Revisar calidad y clasificación por separado.** Consultar `incidencia-C.json` para las alarmas y `etiquetado/cobertura.csv` para los intervalos de exposición. Contrastar la evaluación del modelo final con sus ventanas, no con las clasificaciones del prototipo que acompañaban la captura original.
6. **Comprobar TinyML con la evidencia correspondiente.** Revisar los 63 vectores del banco, la paridad con el PC, las seis clasificaciones USB de la base de ensayo y las capturas de demostración. Distinguir banco aislado, integración funcional, evaluación de campo y demostración manual. No es necesario reentrenar ni recargar la placa para consultar estos resultados.
7. **Revisar las fuentes externas.** Usar HTML, JSON, logs y bases de consulta archivadas para comprobar proveedor, revisión, captura, periodos y tratamiento de ausencias. No interpretar la revisión de archivos históricos como una actualización meteorológica actual ni como una nueva llamada a los proveedores.
8. **Cotejar las pruebas de distribución.** Consultar los logs de Python, Node, TypeScript, compilación, rutas, Java y R5. Si fuera necesario repetirlos, ejecutarlos en la extracción aislada según el README y conservar los nuevos resultados separados. La presente revisión consulta los logs existentes y no afirma una nueva ejecución de esas suites.

## 4. Matriz de comprobaciones documentales completada

En esta tabla, **verificado documentalmente** significa que existe evidencia archivada y que fue contrastada durante la preparación de este documento. Los resultados de pruebas, adquisiciones y demostraciones originales se atribuyen al equipo, salvo las observaciones de campo identificadas en las bitácoras. No se certifica que Sergio haya ejecutado personalmente cada prueba.

| ID | Comprobación | Resultado sustentado | Evidencia y modalidad |
| --- | --- | --- | --- |
| VF-01 | Integridad de los paquetes | Verificado documentalmente: 325 entradas del manifiesto del paquete de evidencias y 807 de la distribución de código, sin discrepancias SHA-256 en esta revisión. | Manifiesto global de [F2] y de [F3]; comprobación de integridad efectuada para estos documentos. |
| VF-02 | Captura de campo USB | Verificado documentalmente: 2.823 lecturas auditadas en seis sesiones; C–D suman 911 y E–F, 884. | `03_Campana_Final/auditoria.json` y `sesiones.csv` [F2]; captura original del equipo. |
| VF-03 | Identidad, tiempo y continuidad | Verificado documentalmente: C–F conservan `RECEIPT`, mediana de 5,006 s, sin duplicados ni saltos internos; los prefijos ausentes anteriores a la conexión permanecen documentados. | Auditoría de campaña [F2]. El detalle se recoge en `registro-campo.md`. |
| VF-04 | Conciliación CSV/XLSX y respaldo | Verificado documentalmente: cinco pares de exportación conciliados con las sesiones; las copias C–F y las bitácoras coinciden por hash con el paquete. | Auditoría [F2] y conciliaciones de `Verificacion_Distribucion.json` [F3]; cotejo adicional de archivos C–F en esta revisión. |
| VF-05 | Integridad SQLite de campaña | Verificado en lectura: `PRAGMA integrity_check` devolvió `ok` sobre `agroedge-respaldo.sqlite`, abierto en modo de solo lectura e inmutable. | Respaldo local correspondiente a `03_Campana_Final/agroedge-respaldo.sqlite` [F2]. |
| VF-06 | Calidad e incidencia C | Verificado documentalmente: 58 marcas estadísticas consecutivas entre 15:52:36,242 y 15:57:21,577; causa y fin físico exacto no determinados. | `03_Campana_Final/incidencia-C.json` y bitácora de validación [F2]. |
| VF-07 | Historial, exportaciones, importación y duplicados | Verificado documentalmente: el log Node registra 11 pruebas aprobadas, incluidas calidad, persistencia, aislamiento, CSV/XLSX, duplicados y compatibilidad de exportaciones. | `evidencias/verificacion/node.log` [F3]; pruebas archivadas en extracción aislada. |
| VF-08 | Simulación y contrato de transporte | Verificado documentalmente: el log de rutas compiladas confirma simulación, fixture serial, TinyML, CSV, XLSX, duplicados y persistencia. Wi-Fi corresponde a contrato/fixtures, no a adquisición física demostrada. | `evidencias/verificacion/integracion.log` y `docs/integracion.md` [F3, F4]. |
| VF-09 | Inferencia física y paridad | Verificado documentalmente: 63 vectores con concordancia de clase y salida int8 entre PC y ESP32-S3; seis clasificaciones reales USB persistidas en la base de ensayo. | `03_Campana_Final/modelo-tflm/benchmark-fisico.json` e `integracion-usb/verificacion-sqlite.json` [F2]. |
| VF-10 | Visualización TinyML | Verificado documentalmente: capturas de perfil de invernadero y exterior conciliadas con registros de la demostración del 24/11 por la noche. | `04_Demostraciones/Demostracion_Final/verificacion-demostracion-2026-11-24.json`, `R3_TinyML_Invernadero.png` y `R3_TinyML_Exterior.png` [F2]. Demostración ajena a las sesiones C–F. |
| VF-11 | Evaluación del modelo final | Verificado documentalmente: 76,7 % de exactitud balanceada en validación y 63/63 aciertos en prueba, con 43 componentes de humedad saturados en prueba. | `03_Campana_Final/modelo-tflm/evaluacion-prueba.json` y `diagnostico-saturacion-prueba.json` [F2]. Resultado de una campaña y una estación. |
| VF-12 | NOAA y componente de contexto | Verificado documentalmente: ejecución histórica y deduplicación registradas; el log de distribución confirma dashboard compilado, HTML, SQLite, API y componente React. | `05_Meteorologia/R5-verificacion-2026-11-24.json` [F2] y `evidencias/verificacion/r5-panel.log` [F3]. |
| VF-13 | Pronóstico HTML de Toca | Verificado documentalmente: captura HTTPS del 24/11 a las 21:10:33 de Colombia, 48 periodos extraídos y 27 vigentes al observar el panel; la ruta archivada respondió HTTP 200. | `05_Meteorologia/Actualizacion_Toca_2026-11-24/` [F2] y `evidencias/verificacion/r5-toca.log` [F3]. Resultado histórico, no disponibilidad actual. |
| VF-14 | Open-Meteo y acumulados | Verificado documentalmente: la demostración presenta horizontes de 24/48 h; las pruebas Node comprueban precipitación de la hora precedente y rechazo de horizontes incompletos. | Conciliación de demostración [F2] y `evidencias/verificacion/node.log` [F3]. Acceso mediante API, distinto del scraping HTML. |
| VF-15 | Pruebas Python | Verificado documentalmente: 33 pruebas aprobadas en el log de distribución. | `evidencias/verificacion/python.log` [F3]; ejecución archivada, no repetida en esta revisión. |
| VF-16 | Java | Verificado documentalmente: revisión de índices por revisión y fecha, duplicados y conflictos aprobada. | `evidencias/verificacion/java.log` [F3]. Alcance: cliente e índice R5. |
| VF-17 | TypeScript, compilación y firmware de distribución | Verificado documentalmente: los procedimientos de TypeScript, compilación Next.js, compilación de firmware y rechazo de firmware sin modelo figuran como correctos. | `evidencias/Verificacion_Distribucion.json` y sus logs asociados [F3]. No se cargó firmware durante esa verificación. |

## 5. Límites de los resultados funcionales

Las capturas y las seis inferencias USB de ensayo comprueban integración del modelo con la aplicación. No sustituyen la evaluación por sesiones. Las demostraciones de la noche del 24 pertenecen a otro arranque y quedaron fuera de las ventanas congeladas de entrenamiento, validación y prueba [F2].

El resultado de 63/63 aciertos en prueba corresponde a E–F de un solo día y una estación. La exactitud balanceada en validación fue de 76,7 %. Se saturaron 43 de los 189 componentes de entrada en prueba, todos de humedad; esa condición afecta la interpretación de la diferencia entre float32 e int8. No puede afirmarse exactitud universal, validación en múltiples campañas ni mejora general causada por cuantización.

El banco aislado registró 256 inferencias después de 16 de calentamiento y una latencia media de 8,674 µs. Las latencias mostradas en el panel incluyen otro tramo de trabajo del firmware y se conservan separadas. La energía de 1,886 a 3,088 µJ por inferencia es una estimación del chip con corrientes de referencia y tiempo medido. La medición eléctrica directa del conjunto de placa y sensores no está documentada [F2].

Las pruebas físicas archivadas corresponden a USB. El contrato HTTP Wi-Fi se verificó mediante fixtures de simulación. NOAA es contexto estacional, Open-Meteo y Eltiempoen.net son pronósticos externos, y TinyML estima exposición del dispositivo. Ninguno de estos resultados demuestra ahorro de agua, reducción de costos o eficacia de una decisión automática de riego. Estas delimitaciones describen el alcance cerrado de la evidencia disponible; no son campos pendientes de este documento.

## 6. Contribución de Sergio y alcance de esta revisión

El registro experimental respalda a Sergio como observador de los intervalos confirmados de C–F, con la procedencia descrita en `registro-campo.md`. Las verificaciones de software, banco, modelo y distribución son resultados registrados del equipo. Esta preparación comprobó su coherencia documental y la integridad de las fuentes, sin añadir ejecuciones personales ni cambiar la autoría histórica de Git.

La matriz anterior se entrega completada con los resultados existentes. Puede publicarse como documentación de la evidencia del proyecto, sin presentarla como una declaración de que todas las pruebas fueron ejecutadas personalmente por quien realice la publicación.

## 7. Referencias y trazabilidad

- **[F1]** `C:\AgroEdge\AgroEdge-IA\README.md`, `MATRIZ_DE_REQUISITOS.md` y `docs\cierre-tecnico-2026-11-24.md`. Arquitectura, funciones, resultados y alcance experimental.
- **[F2]** `C:\AgroEdge\output\AgroEdge_IA_Evidencias_Informe_Final.zip`. Secciones `00_Guia/`, `02_Datasets/`, `03_Campana_Final/`, `04_Demostraciones/`, `05_Meteorologia/` y `06_Version_Congelada/`, con los archivos citados en la matriz. SHA-256: `a6162b5dc036b0de37a2adf99dc042e0b22f9f99395346e8929c3098a54c064a`.
- **[F3]** `C:\AgroEdge\output\JuanCastillo_SergioGuerrero_codigo.zip`. Referencias internas `evidencias/Verificacion_Distribucion.json`, `evidencias/verificacion/`, `README.md` y `SHA256SUMS.txt`. SHA-256: `54cba475e72dc3ca85ef2333c5dc08aa5e2b922413aebaa88b8e1dd9c87641ed`.
- **[F4]** `C:\AgroEdge\AgroEdge-IA\docs\integracion.md`, `docs\tinyml.md` y `docs\r5-verificacion.md`. Contratos, modelo y fuentes externas. Para el significado de la puntuación del modelo final prevalecen el cierre técnico y el registro de demostración; el contrato histórico también describe prototipos anteriores.

**Integridad de la preparación:** se consultaron los ZIP mediante lectura y se verificaron sus manifiestos. La única apertura analítica de SQLite se efectuó sobre el respaldo archivado en modo de solo lectura. No se modificaron software, firmware, modelo, datasets, paquetes definitivos ni configuración de autoría. No se realizaron commits ni `git push`.
