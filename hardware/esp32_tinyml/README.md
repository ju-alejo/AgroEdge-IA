# Firmware definitivo de AgroEdge IA

El sketch `esp32_tinyml.ino` compila el modelo **`exposure-tflm-2c4870d61d3f`** mediante TensorFlow Lite Micro. El FlatBuffer de 1.160 bytes se conserva en [`modelo/exposure-int8.tflite`](modelo/exposure-int8.tflite) y está embebido en [`tflm_model_data.h`](tflm_model_data.h). Si el encabezado falta o declara otra versión, la compilación falla de forma explícita. El prototipo de centroides se consulta en [`examples/tinyml`](../../examples/tinyml/humidity-prototype-1.h) como referencia histórica.

## Perfil probado

| Parámetro | Valor |
| --- | --- |
| Placa | ESP32-S3 Dev Module, ESP32-S3 `esp32s3` |
| Núcleo Arduino | ESP32 by Espressif Systems 4.0.0 |
| CPU y ejecución Arduino | 240 MHz. Tareas Arduino y eventos en núcleo 1 |
| Flash configurada | 4 MiB, QIO, esquema `default`, partición de aplicación de 1.310.720 B |
| PSRAM | Deshabilitada en el perfil validado |
| Hardware físico observado | 16 MiB de Flash y 8 MiB de PSRAM integrada. El perfil anterior es el usado en el ensayo |
| Sensores | AHT20 `0x38` y BMP280 `0x77`, a 3,3 V, SDA GPIO8, SCL GPIO9 y tierra común |
| Puerto de datos | Conector USB-UART, CDC on boot deshabilitado. 115200 baudios, 8N1, JSON UTF-8 por línea |
| Velocidad configurada del cargador | 921600 baudios |

El [perfil de compilación](perfil-compilacion.json) fija el FQBN, el modelo y las dependencias. AHT20 se lee directamente con `Wire`, incluido en el núcleo ESP32. Se usan Chirale_TensorFLowLite 2.0.0, Adafruit BMP280 Library 3.0.0, Adafruit BusIO 1.17.4 y Adafruit Unified Sensor 1.1.15. El ZIP de código incluye fuentes de esas bibliotecas en `hardware/dependencias/`, con sus licencias. El núcleo ESP32 y su toolchain se instalan por separado con Arduino CLI. Al usar una copia de Git, instala las mismas versiones de biblioteca o extrae el directorio de dependencias del ZIP.

## Compilar

Desde la raíz de la distribución, con la plataforma `esp32:esp32@4.0.0` instalada:

```powershell
$perfil = Get-Content hardware/esp32_tinyml/perfil-compilacion.json -Raw | ConvertFrom-Json
$bibliotecas = (Resolve-Path hardware/dependencias).Path
$salida = Join-Path ([IO.Path]::GetTempPath()) ('agroedge-build-' + [Guid]::NewGuid().ToString('N'))
arduino-cli compile --fqbn $perfil.fqbn --libraries $bibliotecas --build-path $salida hardware/esp32_tinyml
Get-FileHash hardware/esp32_tinyml/modelo/exposure-int8.tflite -Algorithm SHA256
```

SHA-256 esperado del FlatBuffer:

```text
2c4870d61d3ff2e82ff1972d112372b69e370c5cb7c352df54ab6d7d3534333d
```

## Cargar en una placa de ensayo autorizada

Esta operación escribe la Flash. Verifica la placa y el puerto con `arduino-cli board list`, conserva el respaldo del firmware existente y cierra el puente USB y el monitor serial antes de abrir el puerto para carga. Usa el directorio de compilación de la sección anterior. `COM8` es el puerto histórico de la estación; reemplázalo por el que informe tu equipo.

```powershell
$puerto = 'COM8'  # Usa el puerto que enumeró tu equipo.
arduino-cli upload --port $puerto --fqbn $perfil.fqbn --input-dir $salida hardware/esp32_tinyml
```

Tras la carga, abre AgroEdge IA y selecciona adquisición USB a 115200 baudios. La sexta lectura válida completa la primera ventana. La clasificación identifica el modelo y la procedencia `ESP32`. La paridad, el banco de 256 invocaciones y las capturas del dispositivo ya verificado están en la [evidencia experimental](../../evidencias/README.md). El procedimiento de distribución compila el sketch sin ejecutar la carga.
