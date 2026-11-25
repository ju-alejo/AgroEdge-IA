# Índice técnico y procedimientos

- [Mapa de producto, instalación y adquisición USB](../README.md)
- [Matriz de requisitos R1–R8](../MATRIZ_DE_REQUISITOS.md)
- [Firmware definitivo y FQBN](../hardware/esp32_tinyml/README.md)
- [Mapa de datasets, resultados, capturas y trazas](../evidencias/README.md)
- [Contrato USB/Wi-Fi, formatos y endpoints](integracion.md)
- [Campañas, análisis de etiquetas y validación](cierre-tecnico-2026-11-24.md)
- [Detector de cambios de régimen](detector-regimen.md)
- [Extracción de NOAA, Toca y separación de Open-Meteo](r5.md) y [verificación R5](r5-verificacion.md)
- [Licencias y atribuciones](ATRIBUCIONES.md)

## Identificadores reproducibles

El modelo de referencia es `exposure-tflm-2c4870d61d3f`. El archivo `hardware/esp32_tinyml/modelo/exposure-int8.tflite` y su encabezado generado forman la entrada obligatoria del sketch. La huella del FlatBuffer es `2c4870d61d3ff2e82ff1972d112372b69e370c5cb7c352df54ab6d7d3534333d`. El artefacto originalmente cargado, identificado en `compilacion-esp32.json`, tiene huella `1a3b357c4876c3a445255819aa66a3ddc3d013b1457adb94abca833522118de5`. La compilación de la distribución se verifica por separado sin escribir la placa.

El fixture NOAA `tests/fixtures/noaa-enso-es-2026-11-12.html` tiene 15.647 bytes y 282 finales LF. La huella esperada es `56ca036e321bf1e84609f0f48d208205aa4c7f39e1ae6d24f86b681f0e7a6323`. La distribución anterior reproducía el fallo con 15.929 bytes y 282 finales CRLF. `.gitattributes` fija LF para esta entrada. Los extractores conservan sus expectativas originales y comprueban el contenido archivado sin consultar las fuentes externas.

## Estructuras de datos

- [`SampleWindow`](../hardware/esp32_tinyml/classifier.h) utiliza un arreglo circular de seis lecturas y sumas incrementales, con actualización O(1) y memoria O(W) para W muestras.
- [`Store`](../lib/store.ts) usa claves únicas para ID e identidad de transporte, estación, sesión y secuencia. Sus índices por origen y tiempo sirven al historial y a las exportaciones. El [detector](../lib/anomaly.ts) se apoya en las referencias de sesión almacenadas.
- [SQLite NOAA](../scraper/store.py) y [SQLite Toca](../scraper/toca_forecast.py) conservan revisiones por huella del contenido. [La política de Toca](../scraper/toca_policy.py) separa el intervalo interno de las restricciones externas y registra la excepción consumida.
- [`BulletinIndex`](../java/r5/src/BulletinIndex.java) usa `HashMap` por revisión y `TreeMap` por día. Busca una revisión en O(1) esperado; un intervalo cuesta O(log D + K) para D fechas distintas y K boletines devueltos.

## Cliente Java

Usa JDK 17 y Gson 2.15.0. Obtén `gson-2.15.0.jar` del repositorio de artefactos Maven Central y establece `$gson` con su ruta local. Desde la raíz del código:

```powershell
$gson = (Resolve-Path 'C:/ruta/gson-2.15.0.jar').Path
$clases = Join-Path ([IO.Path]::GetTempPath()) ('agroedge-java-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $clases | Out-Null
javac -encoding UTF-8 -cp $gson -d $clases java/r5/src/*.java java/r5/test/*.java
java -ea -cp "$clases;$gson" BulletinIndexTest
```

`BulletinTool` consulta la API local `/api/agroclima` cuando hay una instancia de AgroEdge IA disponible. `BulletinIndexTest` cubre revisiones, fechas, duplicados y conflictos con datos de prueba y se ejecuta sin red.

## Verificación de una extracción

Compara `SHA256SUMS.txt` desde la raíz de la distribución. Este comando comprueba los archivos incluidos en el manifiesto:

```powershell
Get-Content -Encoding UTF8 SHA256SUMS.txt | ForEach-Object {
    if ($_ -notmatch '^([a-f0-9]{64})  (.+)$') { throw "Entrada inválida: $_" }
    $esperado = $Matches[1]
    $archivo = $Matches[2]
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $archivo).Hash -ne $esperado) {
        throw "La huella no coincide: $archivo"
    }
}
```

Los informes de una extracción de prueba se incluyen bajo `evidencias/verificacion`. Para repetir auditoría y ventaneo, usa los respaldos en modo de solo lectura y genera los derivados en una carpeta aparte. [Comandos de reproducción del cierre](cierre-tecnico-2026-11-24.md#reproducción)
